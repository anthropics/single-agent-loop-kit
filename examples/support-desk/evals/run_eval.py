#!/usr/bin/env python3
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""Run the golden tasks against the app and grade task completion.

    KIT_MODEL=<your model id> python3 evals/run_eval.py --variant baseline
    KIT_MODEL=<your model id> python3 evals/run_eval.py --variant v1 --app single_loop
    KIT_MODEL=fake            python3 evals/run_eval.py --variant smoke     # offline, no spend

Each task gets a fresh backend. Grading looks at what the agent did (the
backend's action log) and what it told the customer, never at which subagent
was called, so the same eval keeps working after subagents are merged or folded.

Results land in .claude/hillclimb/support-desk/<variant>/ as results.jsonl plus
one trace per case. That is the layout `/claude-api build-eval` and
`/claude-api hillclimb` use, so their report and this kit's compare script
both read it.
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.backend import Backend  # noqa: E402
from app.llm import Meter, model_name  # noqa: E402


def _arg_matches(expected, actual) -> bool:
    if isinstance(expected, str) and isinstance(actual, str):
        return expected.lower() in actual.lower()
    return expected == actual


def _wanted(want: dict, action: dict) -> bool:
    return (action["name"] == want["name"]
            and all(_arg_matches(v, action["args"].get(k)) for k, v in want.get("args", {}).items()))


def grade(checks: dict, answer: str, actions: list[dict]) -> list[dict]:
    """One entry per check, so a failure says which check failed."""
    out = []
    for pattern in checks.get("answer_includes", []):
        out.append({"check": f"answer includes /{pattern}/", "ok": bool(re.search(pattern, answer, re.I))})
    for want in checks.get("actions", []):
        hit = any(_wanted(want, a) for a in actions)
        out.append({"check": f"did {want['name']} {json.dumps(want.get('args', {}))}", "ok": hit})
    for name in checks.get("forbidden_actions", []):
        out.append({"check": f"did not {name}", "ok": all(a["name"] != name for a in actions)})
    for pattern in checks.get("answer_excludes", []):
        out.append({"check": f"answer leaves out /{pattern}/", "ok": not re.search(pattern, answer, re.I)})
    if checks.get("only_expected_writes"):   # any write the task did not ask for fails it
        extra = sorted({a["name"] for a in actions
                        if not any(_wanted(want, a) for want in checks.get("actions", []))})
        out.append({"check": "made no other writes" + (f" (made {', '.join(extra)})" if extra else ""),
                    "ok": not extra})
    return out


def run_case(case: dict, new_conversation) -> tuple[dict, list]:
    backend, meter = Backend(), Meter()
    signed_in = {"customer_id": case["customer"]} if "customer" in case else {}   # nobody, if the task names no one
    conversation = new_conversation(backend, meter, **signed_in)
    started = time.monotonic()
    replies = [conversation.send(turn) for turn in case["turns"]]
    latency = time.monotonic() - started
    checks = grade(case["checks"], "\n".join(replies), backend.actions)
    passed = all(c["ok"] for c in checks)
    row = {
        "prompt_id": case["id"],
        "prompt": "\n".join(case["turns"]),
        "tags": case["tags"],
        "status": "ok",
        "grade": {"task_complete": 1 if passed else 0},
        "checks": checks,
        "answer": replies[-1],
        "latency_s": round(latency, 2),
        "in_tokens": meter.input_tokens,
        "out_tokens": meter.output_tokens,
        "model_calls": meter.calls,
        "tool_calls": sum(1 for t in conversation.trace if t["role"] == "tool_call"),
        "by_agent": meter.by_agent,
        "actions": backend.actions,
        "model": model_name(),
    }
    return row, conversation.trace


def _git_commit() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True)
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT,
                               capture_output=True, text=True).stdout.strip()
    except OSError:
        return None
    return (out.stdout.strip() + ("+uncommitted" if dirty else "")) if out.returncode == 0 else None


def _record_run(out: Path, entry: dict) -> None:
    """Append this invocation to run.json, so a results folder says how it was made."""
    path = out / "run.json"
    runs = json.loads(path.read_text())["runs"] if path.exists() else []
    path.write_text(json.dumps({"runs": runs + [entry]}, indent=2) + "\n")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def wilson(passes: int, n: int) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    z, p = 1.96, passes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--variant", default="baseline", help="baseline, v1, v2, ... (one per change)")
    parser.add_argument("--app", default="app",
                        help="package to test: app (router plus subagents) or single_loop")
    parser.add_argument("--reps", type=int, default=1, help="runs per task; use 3 or more to see noise")
    parser.add_argument("--only", help="run only these task ids, separated by commas, for example t01,t10")
    parser.add_argument("--cases", default=str(ROOT / "evals" / "golden.jsonl"))
    parser.add_argument("--fresh", action="store_true",
                        help="start this variant over. Without it, tasks that already have a row are skipped, "
                             "even if the code, the checks or the model changed since")
    parser.add_argument("--out", default=str(ROOT / ".claude" / "hillclimb" / "support-desk"))
    args = parser.parse_args()
    sys.stdout.reconfigure(line_buffering=True)   # show each task as it finishes, even when piped to a file

    cases = [json.loads(line) for line in Path(args.cases).read_text().splitlines() if line.strip()]
    for case in cases:   # an id becomes part of a trace file name, so it must not be able to name a path
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", str(case.get("id", ""))):
            sys.exit(f"{args.cases}: task id {case.get('id')!r} is not usable. "
                     "Use letters, digits, dots, dashes and underscores only.")
    if args.only is not None:   # checked before anything is created or deleted
        wanted = [task.strip() for task in args.only.split(",") if task.strip()]
        unknown = sorted(set(wanted) - {c["id"] for c in cases})
        if not wanted:
            sys.exit("--only needs at least one task id, for example --only t01,t10.")
        if unknown:
            sys.exit(f"--only: no task with id {', '.join(unknown)} in {args.cases}.")
        cases = [c for c in cases if c["id"] in wanted]

    new_conversation = importlib.import_module(args.app).new_conversation
    out = Path(args.out) / args.variant
    if args.fresh and out.exists():
        shutil.rmtree(out)
    (out / "traces").mkdir(parents=True, exist_ok=True)
    results_path, errors_path = out / "results.jsonl", out / "errors.jsonl"

    done = set()
    if results_path.exists():
        for line in results_path.read_text().splitlines():
            row = json.loads(line)
            done.add((row["prompt_id"], row["rep"]))

    cases_path = Path(args.cases).resolve()
    run = {"started_at": _now(), "ended_at": None, "model": model_name(), "app": args.app,
           "reps": args.reps, "only": args.only,
           "cases": str(cases_path.relative_to(ROOT)) if cases_path.is_relative_to(ROOT) else cases_path.name,
           "git_commit": _git_commit(), "skills_off": os.environ.get("KIT_SKILLS_OFF") or None,
           "rows_written": 0, "errors": 0}
    kept = sum((case["id"], rep) in done for case in cases for rep in range(args.reps))
    if kept:
        print(f"  {kept} rows from an earlier run of {args.variant} are kept and not rerun. "
              "Pass --fresh to start this variant over.")
    for case in cases:
        for rep in range(args.reps):
            if (case["id"], rep) in done:
                continue
            try:
                row, trace = run_case(case, new_conversation)
            except Exception as exc:  # harness or serving failure: not a score
                with errors_path.open("a") as f:
                    f.write(json.dumps({"prompt_id": case["id"], "rep": rep, "class": "harness_error",
                                        "error": repr(exc), "trace": traceback.format_exc()}) + "\n")
                print(f"  {case['id']} rep{rep}: ERROR {exc!r}")
                run["errors"] += 1
                continue
            row["rep"] = rep
            (out / "traces" / f"{case['id']}_rep{rep}.json").write_text(json.dumps(trace, indent=2))
            with results_path.open("a") as f:
                f.write(json.dumps(row) + "\n")
            run["rows_written"] += 1
            if row["model"] == "fake":  # keyword rules, not a model: a grade here would mislead
                mark = "ran "
            else:
                mark = "pass" if row["grade"]["task_complete"] else "FAIL"
            print(f"  {case['id']} rep{rep}: {mark}  {row['latency_s']}s  "
                  f"{row['model_calls']} model calls  {row['in_tokens']}+{row['out_tokens']} tokens")

    run["ended_at"] = _now()
    _record_run(out, run)

    rows = [json.loads(line) for line in results_path.read_text().splitlines()] if results_path.exists() else []
    scored = {(row["prompt_id"], row["rep"]) for row in rows}
    errors = 0
    if errors_path.exists():   # an error a rerun got past is no longer an error
        failed = {(e["prompt_id"], e["rep"]) for e in map(json.loads, errors_path.read_text().splitlines())}
        errors = len(failed - scored)
    if rows and rows[0]["model"] == "fake":
        verdict = "The plumbing works." if not errors else f"See {errors_path}."
        print(f"\n{args.variant}: {len(rows)} tasks ran on the offline stand-in model, "
              f"{errors} harness errors. {verdict}\n"
              "The stand-in follows keyword rules, so nothing here is scored. "
              f"Set KIT_MODEL to a real model id for scores. Results in {out}")
        return 0
    passes = sum(r["grade"]["task_complete"] for r in rows)
    low, high = wilson(passes, len(rows))
    print(f"\n{args.variant}: {passes}/{len(rows)} tasks complete "
          f"(95% CI {low:.0%} to {high:.0%}), {errors} harness errors. Results in {out}")
    print(f"Used {sum(r['in_tokens'] for r in rows):,} input and {sum(r['out_tokens'] for r in rows):,} "
          f"output tokens over {len(rows)} conversations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
