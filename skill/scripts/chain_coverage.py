#!/usr/bin/env python3
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""Check that the eval has a task for every handoff chain production uses.

    python3 chain_coverage.py traces.jsonl .claude/hillclimb/<flow> baseline --exclude router
    python3 chain_coverage.py traces.jsonl .claude/hillclimb/<flow> baseline --exclude router --agent returns

A chain is the set of subagents one production trace called. Merging, folding or
turning a subagent into a tool changes how those agents pass work to each other,
and the classic failure is a dropped handoff: the second agent never gets what
the first one found. The eval can only catch that on a chain it has a task for.

The traces file is the same export `coupling_map.py` reads. The eval side comes
from the results.jsonl of a run of the unchanged system, which must record which
agents each task called:

    prompt_id (or id / case_id), grade {metric: number}, by_agent {agent: {...}}

A task covers a chain when it called every agent in it. Use the baseline run:
once a subagent is folded it no longer shows up in by_agent.

This script shows which tasks run each chain and whether they pass today. It
cannot see what a task checks. Read each covering task and make sure it grades
the end of the chain: what changed in the systems, and each fact that had to
survive the handoff.

Exit status is 1 when a chain has no task, so it can gate a change.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from coupling_map import clean, load as load_traces


def load_tasks(flow: Path, variant: str, exclude: set[str]) -> dict[str, dict]:
    path = flow / variant / "results.jsonl"
    if not path.exists():
        sys.exit(f"No results at {path}. Run the eval for '{variant}' first.")
    tasks: dict[str, dict] = defaultdict(lambda: {"agents": set(), "passes": 0, "reps": 0})
    seen_by_agent = False
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("status", "ok") != "ok":
            continue
        task = tasks[next((clean(row[k]) for k in ("prompt_id", "id", "case_id") if row.get(k) is not None), None)]
        if isinstance(row.get("by_agent"), dict):
            seen_by_agent = True
            task["agents"] |= set(row["by_agent"]) - exclude
        grade = row.get("grade") or {}
        task["reps"] += 1
        task["passes"] += 1 if grade and float(next(iter(grade.values()))) >= 1 else 0
    if not seen_by_agent:
        sys.exit(f"{path} has no by_agent field, so this script cannot tell which agents a task called. "
                 "Have the runner record it, or map tasks to chains by hand from their tags.")
    return tasks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("traces", help="production trace export, one subagent call per line")
    parser.add_argument("flow", type=Path, help="folder with one subfolder per eval variant")
    parser.add_argument("variant", help="a run of the unchanged system, usually baseline")
    parser.add_argument("--exclude", action="append", default=[],
                        help="agent to leave out, usually the router or main agent (repeatable)")
    parser.add_argument("--agent", action="append", default=[],
                        help="only chains that include this agent: the ones a change to it touches (repeatable)")
    parser.add_argument("--min-traces", type=int, default=2,
                        help="ignore chains seen in fewer production traces than this (default 2)")
    parser.add_argument("--trace-key", default="trace_id")
    parser.add_argument("--agent-key", default="agent")
    parser.add_argument("--ts-key", default="ts")
    args = parser.parse_args()

    exclude = set(args.exclude)
    traces = load_traces(args.traces, args.trace_key, args.agent_key, args.ts_key, exclude)
    tasks = load_tasks(args.flow, args.variant, exclude)

    chains: Counter = Counter()
    example: dict[frozenset, str] = {}
    for calls in traces.values():
        order = list(dict.fromkeys(c["agent"] for c in calls))
        chain = frozenset(order)
        chains[chain] += 1
        example.setdefault(chain, " -> ".join(order))
    wanted = set(args.agent)
    rows = [(chain, count) for chain, count in chains.most_common()
            if count >= args.min_traces and (not wanted or chain & wanted)]

    if not rows:   # an empty table must not read as "everything is covered"
        seen = ", ".join(sorted({clean(agent) for chain in chains for agent in chain})) or "none"
        sys.exit("No chain matches"
                 + (f" --agent {', '.join(sorted(wanted))}" if wanted else "")
                 + f" with at least {args.min_traces} traces, so there is nothing to check. "
                 f"Agents in the traces: {seen}.")

    print(f"# Chain coverage: production traces against `{clean(args.variant)}`\n")
    print(f"{len(traces)} traces, {len(tasks)} eval tasks."
          + (f" Only chains that include {', '.join(sorted(wanted))}." if wanted else "") + "\n")
    print("| chain | agents | traces | % of traces | tasks that run it | passing today |")
    print("| --- | ---: | ---: | ---: | --- | --- |")
    gaps, failing = [], []
    for chain, count in rows:
        covering = sorted(t for t, info in tasks.items() if chain <= info["agents"])
        passing = [t for t in covering if tasks[t]["passes"] == tasks[t]["reps"]]
        name = clean(example[chain])
        if not covering:
            gaps.append(name)
            shown, status = "**none**", "-"
        else:
            shown = ", ".join(covering)
            status = ", ".join(f"{t} {tasks[t]['passes']}/{tasks[t]['reps']}" for t in covering)
            if len(chain) > 1 and not passing:
                failing.append(name)
        print(f"| {name} | {len(chain)} | {count} | {count / len(traces):.0%} | {shown} | {status} |")

    print()
    if gaps:
        print("**No task runs: " + "; ".join(gaps) + ".** A change to any agent in those chains could drop a "
              "handoff and the eval would not show it. Add a task for each before making the change.")
    else:
        print("Every chain listed has at least one task.")
    if failing:
        print("\nNo covering task passes today for: " + "; ".join(failing) + ". A task that already fails "
              "cannot show a change made things worse. Note what it fails on, so a later pass or fail can be read.")
    print("\nFor each chain of two or more agents, open its tasks and check what they grade: what changed in "
          "the systems at the end of the chain, and each fact that had to survive the handoff. A task that "
          "only checks wording, or only the first agent's part, does not cover the chain.")
    return 1 if gaps else 0


if __name__ == "__main__":
    raise SystemExit(main())
