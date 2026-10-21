#!/usr/bin/env python3
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""Estimate the tokens an eval run will use, from a run that was already measured.

    python3 estimate.py .claude/hillclimb/<flow> probe --tasks 19 --reps 2 --heavy 3
    python3 estimate.py .claude/hillclimb/<flow> baseline --reps 2
    python3 estimate.py .claude/hillclimb/<flow> baseline --reps 2 --actual v1

The first argument after the flow dir is the measured run to base the estimate
on. Per row of its results.jsonl this script reads prompt_id (or id / case_id),
in_tokens, out_tokens and status.

If the measured run covers every task, the estimate is the sum of each task's
mean. If it covers only some (a probe), the script cannot know what the other
tasks cost, so it prints a range: every task as small as the smallest one
measured, up to every task as large as the largest. One heavy task can be many
times a light one, so probe the task you expect to be heaviest as well. Then
--heavy N (how many tasks you expect to be like the largest one) gives one
likely figure inside the range. It is only as good as that count.

It counts tokens only. It never guesses a price, and it does not see what a
coding assistant uses while it reads and edits around the run.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from coupling_map import clean as _clean

FIELDS = ("in_tokens", "out_tokens")


def load(flow: Path, variant: str) -> dict[str, list[dict]]:
    path = flow / variant / "results.jsonl"
    if not path.exists():
        sys.exit(f"No results at {path}. Run the eval for '{variant}' first.")
    tasks: dict[str, list[dict]] = defaultdict(list)
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("status", "ok") != "ok" or any(row.get(f) is None for f in FIELDS):
            continue
        tasks[next((_clean(row[k]) for k in ("prompt_id", "id", "case_id") if row.get(k) is not None), None)].append(row)
    if not tasks:
        sys.exit(f"{path} has no rows with in_tokens and out_tokens.")
    return tasks


def _round(n: float) -> str:
    """Two significant figures: an estimate should not look more exact than it is."""
    if n <= 0:
        return "0"
    digits = len(str(int(n)))
    step = 10 ** max(digits - 2, 0)
    return f"{int(round(n / step) * step):,}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("flow", type=Path, help="folder with one subfolder per variant")
    parser.add_argument("source", help="the measured variant to base the estimate on")
    parser.add_argument("--tasks", type=int, help="tasks in the planned run (default: the tasks the source covers)")
    parser.add_argument("--reps", type=int, default=1, help="reps per task in the planned run")
    parser.add_argument("--heavy", type=int,
                        help="with a partial source: how many tasks you expect to be like the largest one measured")
    parser.add_argument("--only", help="estimate a run of just these task ids from the source, separated by "
                                       "commas: for more reps of a few tasks")
    parser.add_argument("--actual", help="a finished variant to show next to the estimate")
    args = parser.parse_args()

    measured = load(args.flow, args.source)
    if args.only is not None:
        wanted = [_clean(task) for task in args.only.split(",") if task.strip()]
        missing = sorted(set(wanted) - set(measured))
        if missing or not wanted:
            sys.exit(f"--only: '{args.source}' has no measured rows for {', '.join(missing) or 'an empty list'}.")
        measured = {task: rows for task, rows in measured.items() if task in wanted}
    covered = len(measured)
    tasks = args.tasks or covered
    if tasks < covered:
        sys.exit(f"--tasks {tasks} is fewer than the {covered} tasks '{args.source}' covers.")
    if args.heavy is not None and not 0 <= args.heavy <= tasks:
        sys.exit(f"--heavy must be between 0 and {tasks}.")
    conversations = tasks * args.reps
    rows = sum(len(r) for r in measured.values())
    means = {f: {t: statistics.fmean(r[f] for r in rs) for t, rs in measured.items()} for f in FIELDS}

    print(f"# Estimate: {tasks} tasks x {args.reps} reps = {conversations} conversations\n")
    print(f"Based on `{args.source}`: {rows} measured conversations covering {covered} of {tasks} tasks.\n")
    estimate = {}
    if covered == tasks:
        estimate = {f: sum(means[f].values()) * args.reps for f in FIELDS}
        print(f"- input tokens: about {_round(estimate['in_tokens'])}")
        print(f"- output tokens: about {_round(estimate['out_tokens'])}")
        heavy = sorted(means["in_tokens"].items(), key=lambda kv: -kv[1])[:2]
        share = sum(v for _, v in heavy) / (sum(means["in_tokens"].values()) or 1)
        if covered > 2 and share >= 0.5:
            names = " and ".join(t for t, _ in heavy)
            print(f"- {names} carry {share:.0%} of the input tokens. Dropping reps there changes the total most.")
        if rows == covered:
            print("- One rep per task was measured, so this does not show how much a task varies.")
    else:
        for field, label in zip(FIELDS, ("input", "output")):
            low, high = min(means[field].values()), max(means[field].values())
            if covered == 1:
                print(f"- {label} tokens: about {_round(low * conversations)} if every task is the size of the "
                      "one measured")
                continue
            if field == "out_tokens":
                # How much a task writes has little to do with how much it reads, so the tasks
                # picked as lightest and heaviest by input say nothing about the top end here.
                print(f"- output tokens: at least about {_round(low * conversations)}. No upper figure: "
                      "the measured tasks were picked by how much they read, not how much they write")
                continue
            line = f"- {label} tokens: between about {_round(low * conversations)} and {_round(high * conversations)}"
            if args.heavy is not None:
                estimate[field] = (args.heavy * high + (tasks - args.heavy) * low) * args.reps
                line += f", likely about {_round(estimate[field])}"
            print(line)
        if covered == 1:
            print(f"\nThis is not an estimate of the whole run. {tasks - covered} tasks have not been measured, "
                  "and a task that reads a large input can cost many times a small one. Probe the task you "
                  "expect to be heaviest to get an upper figure.")
        else:
            print(f"\nThis is a range. {tasks - covered} tasks have not been measured. The lower figure assumes "
                  "every task is as small as the smallest one measured, the upper that every task is as large "
                  "as the largest.")
            if args.heavy is not None:
                print(f"The likely figure assumes {args.heavy} tasks like the largest and the rest like the "
                      "smallest. That count is a judgment, not a measurement.")

    if args.actual:
        actual_rows = [r for rs in load(args.flow, args.actual).values() for r in rs]
        print(f"\n## Against `{args.actual}` ({len(actual_rows)} conversations)\n")
        print("| | estimate | actual |")
        print("| --- | ---: | ---: |")
        for field, label in zip(FIELDS, ("input tokens", "output tokens")):
            guess = f"{_round(estimate[field])}" if field in estimate else "range only"
            print(f"| {label} | {guess} | {sum(r[field] for r in actual_rows):,} |")

    print("\nNot counted: what a coding assistant uses while it reads and edits around the run. "
          "No prices are applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
