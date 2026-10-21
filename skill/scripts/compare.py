#!/usr/bin/env python3
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""Put two eval runs side by side: the system before a change and after it.

    python3 compare.py .claude/hillclimb/<flow> baseline v1
    python3 compare.py .claude/hillclimb/<flow> baseline v1 --price-in <dollars> --price-out <dollars>
    python3 compare.py .claude/hillclimb/<flow> baseline v1 --skip-tag break-check

Each variant directory holds a results.jsonl with one row per (case, rep), in
the layout `/claude-api build-eval` writes. Per row this script reads:

    prompt_id (or id / case_id), grade {metric: number}, and when present
    latency_s, in_tokens, out_tokens, model_calls, tags, status, model,
    by_agent {agent: {calls, input_tokens}}, actions [{name, ...}]

actions is the list of writes the app made during the task (returns created,
records changed). When rows carry it, the script lists every task whose writes
differ between the two runs, whether or not its score moved.

Prices are dollars per million tokens. Leave them out and cost is not shown;
the script never guesses a price.

The verdict follows one rule: if the changed version completes fewer tasks than
the version before it, the change does not hold. Everything else it prints is
there so a person can check that call.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from coupling_map import clean as _clean


def _case_id(row: dict, path: Path, raw_ids: dict) -> str | None:
    """The task id as the report prints it. Two ids that only differ in a way the report cannot show stop the run."""
    raw = next((str(row[k]) for k in ("prompt_id", "id", "case_id") if row.get(k) is not None), None)
    if raw is None:
        return None
    if raw_ids.setdefault(_clean(raw), raw) != raw:
        sys.exit(f"{path}: task ids {raw_ids[_clean(raw)]!r} and {raw!r} read the same in a report. Rename one.")
    return _clean(raw)


def load(flow: Path, variant: str, metric: str | None) -> dict:
    path = flow / variant / "results.jsonl"
    if not path.exists():
        sys.exit(f"No results at {path}. Run the eval for '{variant}' first.")
    cases: dict[str, list[dict]] = defaultdict(list)
    skipped = 0
    scored = set()
    raw_ids: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("status", "ok") != "ok":
            skipped += 1
            continue
        case_id = _case_id(row, path, raw_ids)
        grade = row.get("grade") or {}
        key = metric or next(iter(grade), None)
        if key is None or key not in grade:
            sys.exit(f"{path}: row for {case_id} has no grade for metric {key!r}.")
        try:
            score = float(grade[key])
        except (TypeError, ValueError):
            score = math.nan
        if not math.isfinite(score):   # NaN compares false with everything, so it would slip past the verdict
            sys.exit(f"{path}: row for {case_id} has a grade for {key!r} that is not a finite number "
                     f"({grade[key]!r}). Fix the grader and rerun that task before comparing.")
        tags = row.get("tags") or []   # names from the input that the report prints
        row["tags"] = [_clean(tag) for tag in (tags if isinstance(tags, list) else [tags])]
        if row.get("model") is not None:
            row["model"] = _clean(row["model"])
        cases[case_id].append({**row, "_score": score, "_metric": _clean(key)})
        scored.add((case_id, row.get("rep")))
    errors_path = flow / variant / "errors.jsonl"
    errors = 0
    if errors_path.exists():   # an error a later rerun got past is no longer an error
        for line in errors_path.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if (_case_id(row, errors_path, {}), row.get("rep")) not in scored:
                errors += 1
    return {"name": _clean(variant), "cases": cases, "skipped": skipped, "errors": errors}


def _mean(rows: list[dict], field: str):
    values = [r[field] for r in rows if r.get(field) is not None]
    return statistics.fmean(values) if values else None


def summarise(variant: dict, common: list[str], price_in, price_out) -> dict:
    rows = [r for case in common for r in variant["cases"][case]]
    per_case = {case: statistics.fmean(r["_score"] for r in variant["cases"][case]) for case in common}
    tokens_in, tokens_out = _mean(rows, "in_tokens"), _mean(rows, "out_tokens")
    cost = None
    if price_in is not None and price_out is not None and tokens_in is not None and tokens_out is not None:
        cost = (tokens_in * price_in + tokens_out * price_out) / 1_000_000
    return {
        "per_case": per_case,
        "score": statistics.fmean(per_case.values()) if per_case else 0.0,
        "reps": min((len(variant["cases"][c]) for c in common), default=0),
        "latency_s": _mean(rows, "latency_s"),
        "model_calls": _mean(rows, "model_calls"),
        "in_tokens": tokens_in,
        "out_tokens": tokens_out,
        "cost": cost,
        "models": sorted({r.get("model", "?") for r in rows}),
        "by_tag": _by_tag(variant, common),
        "by_agent": _by_agent(rows),
    }


def _passes(variant: dict, case: str) -> str:
    """'1/2' when the score is pass or fail per rep, so a flip in one rep is visible."""
    scores = [r["_score"] for r in variant["cases"][case]]
    if all(score in (0.0, 1.0) for score in scores):
        return f"{int(sum(scores))}/{len(scores)}"
    return f"{statistics.fmean(scores):.2f}"


def _by_tag(variant: dict, common: list[str]) -> dict[str, tuple[float, int]]:
    totals: dict[str, list[float]] = defaultdict(list)
    for case in common:
        for row in variant["cases"][case]:
            for tag in row.get("tags") or []:
                totals[tag].append(row["_score"])
    return {tag: (sum(scores), len(scores)) for tag, scores in totals.items()}


def _by_agent(rows: list[dict]) -> dict[str, dict]:
    """Model calls and input tokens per task, split by which agent made them."""
    totals: dict[str, dict] = defaultdict(lambda: {"calls": 0, "input_tokens": 0})
    for row in rows:
        for agent, use in (row.get("by_agent") or {}).items():
            totals[agent]["calls"] += use.get("calls", 0)
            totals[agent]["input_tokens"] += use.get("input_tokens", 0)
    n = len(rows) or 1
    return {agent: {k: v / n for k, v in use.items()} for agent, use in totals.items()}


def _writes(variant: dict, case: str) -> str | None:
    """The writes a task made, per rep, as 'create_return' or 'none'. None if rows do not record them."""
    rows = variant["cases"][case]
    if any(not isinstance(r.get("actions"), list) for r in rows):
        return None
    per_rep = [", ".join(sorted(_clean(a.get("name", a) if isinstance(a, dict) else a) for a in r["actions"])) or "none"
               for r in rows]
    return per_rep[0] if len(set(per_rep)) == 1 else " / ".join(per_rep)


def _paths(variant: dict, case: str):
    """How many of a task's reps called each agent, and the rep count. None if rows do not record by_agent."""
    rows = variant["cases"][case]
    if any(not isinstance(r.get("by_agent"), dict) for r in rows):
        return None
    return Counter(agent for r in rows for agent in r["by_agent"]), len(rows)


def _path_changes(a: dict, b: dict, common: list[str], exclude: set[str]) -> tuple[list, list, list]:
    """Agents called in a different share of a task's reps: clear changes as (task, agent, before, after),
    one-rep differences as text, and the tasks whose rows do not record which agents ran."""
    clear, slight, unknown = [], [], []
    for case in common:
        pa, pb = _paths(a, case), _paths(b, case)
        if pa is None or pb is None:
            unknown.append(case)
            continue
        (ca, na), (cb, nb) = pa, pb
        for agent in sorted((set(ca) | set(cb)) - exclude):
            gap = abs(ca[agent] / na - cb[agent] / nb)
            if not gap:
                continue
            # With one rep per task there is no telling a wobble from a change, so nothing is waved through.
            if min(na, nb) > 1 and round(gap * min(na, nb)) <= 1:
                slight.append(f"{case} ({_clean(agent)})")
            else:
                clear.append((case, _clean(agent), f"{ca[agent]}/{na}", f"{cb[agent]}/{nb}"))
    return clear, slight, unknown


def _fmt(value, pattern="{:,.1f}") -> str:
    return "not measured" if value is None else pattern.format(value)


def _change(before, after) -> str:
    if before is None or after is None or before == 0:
        return ""
    return f"{(after - before) / before:+.0%}"


def render(a: dict, b: dict, sa: dict, sb: dict, common: list[str], only_a: list[str], only_b: list[str],
           exclude: set[str] = frozenset()) -> tuple[str, bool]:
    n = len(common)
    lines = [f"# {a['name']} vs {b['name']}", "",
             f"{n} tasks in both runs. Metric: {next(iter(a['cases'].values()))[0]['_metric']}.", "",
             f"| | {a['name']} | {b['name']} | change |", "| --- | ---: | ---: | ---: |",
             f"| tasks complete | {sa['score'] * n:.1f}/{n} ({sa['score']:.0%}) "
             f"| {sb['score'] * n:.1f}/{n} ({sb['score']:.0%}) | {(sb['score'] - sa['score']) * n:+.1f} |"]
    for label, field, pattern in [("latency per task (s)", "latency_s", "{:,.1f}"),
                                  ("model calls per task", "model_calls", "{:,.1f}"),
                                  ("input tokens per task", "in_tokens", "{:,.0f}"),
                                  ("output tokens per task", "out_tokens", "{:,.0f}"),
                                  ("cost per task ($)", "cost", "{:,.4f}")]:
        if field == "cost" and sa["cost"] is None and sb["cost"] is None:
            continue
        lines.append(f"| {label} | {_fmt(sa[field], pattern)} | {_fmt(sb[field], pattern)} "
                     f"| {_change(sa[field], sb[field])} |")

    worse = [c for c in common if sb["per_case"][c] < sa["per_case"][c]]
    better = [c for c in common if sb["per_case"][c] > sa["per_case"][c]]
    one_rep_flips = []
    if worse or better:
        lines += ["", "## Tasks that changed", "", f"| task | {a['name']} | {b['name']} | tags |",
                  "| --- | ---: | ---: | --- |"]
        for case in worse + better:
            tags = ", ".join(a["cases"][case][0].get("tags", []))
            lines.append(f"| {case} | {_passes(a, case)} | {_passes(b, case)} | {tags} |")
            reps = min(len(a["cases"][case]), len(b["cases"][case]))
            if reps > 1 and round(abs(sb["per_case"][case] - sa["per_case"][case]) * reps) <= 1:
                one_rep_flips.append(case)

    writes_changed = [(c, _writes(a, c), _writes(b, c)) for c in common]
    writes_changed = [(c, wa, wb) for c, wa, wb in writes_changed if wa is not None and wb is not None and wa != wb]
    if writes_changed:
        lines += ["", "## Writes that changed", "",
                  "What each task changed in the systems, per rep. A slash separates reps that differ.", "",
                  f"| task | {a['name']} | {b['name']} |", "| --- | --- | --- |"]
        lines += [f"| {case} | {wa} | {wb} |" for case, wa, wb in writes_changed]

    paths_changed, paths_one_rep, paths_unknown = _path_changes(a, b, common, set(exclude))
    if paths_changed or paths_one_rep:
        lines += ["", "## Paths that changed", "",
                  "Reps of a task in which an agent was called. A task can keep its score and still take "
                  "a different route."]
        if paths_changed:
            lines += ["", f"| task | agent | {a['name']} | {b['name']} |", "| --- | --- | ---: | ---: |"]
            lines += [f"| {case} | {agent} | {before} | {after} |" for case, agent, before, after in paths_changed]
        if paths_one_rep:
            lines += ["", f"One rep apart, which the unchanged system often does by itself: {', '.join(paths_one_rep)}."]

    tags = sorted(set(sa["by_tag"]) | set(sb["by_tag"]))
    if tags:
        lines += ["", "## By tag", "", f"| tag | {a['name']} | {b['name']} |", "| --- | ---: | ---: |"]
        for tag in tags:
            cells = [f"{passed:g}/{total}" if total else "" for passed, total in
                     (sa["by_tag"].get(tag, (0, 0)), sb["by_tag"].get(tag, (0, 0)))]
            lines.append(f"| {tag} | {cells[0]} | {cells[1]} |")

    agents = sorted(set(sa["by_agent"]) | set(sb["by_agent"]))
    if agents:
        lines += ["", "## By agent, per task", "",
                  f"| agent | calls, {a['name']} | calls, {b['name']} "
                  f"| input tokens, {a['name']} | input tokens, {b['name']} |",
                  "| --- | ---: | ---: | ---: | ---: |"]
        for agent in agents:
            ua = sa["by_agent"].get(agent, {"calls": 0, "input_tokens": 0})
            ub = sb["by_agent"].get(agent, {"calls": 0, "input_tokens": 0})
            lines.append(f"| {_clean(agent)} | {ua['calls']:.1f} | {ub['calls']:.1f} "
                         f"| {ua['input_tokens']:,.0f} | {ub['input_tokens']:,.0f} |")

    lines += ["", "## Verdict", ""]
    is_worse = sb["score"] < sa["score"] or bool(only_a)
    if only_a:   # a task that crashed in every rep must not drop out of the verdict
        lines.append(f"**No verdict yet.** {', '.join(only_a)} have scored rows in {a['name']} and none in "
                     f"{b['name']}. Check {b['name']}/errors.jsonl, rerun those tasks, then compare again.")
    elif is_worse:
        lines.append(f"**{b['name']} scores worse than {a['name']}.** The change does not hold yet. "
                     f"Read the traces for {', '.join(worse)}, then fix and rerun, or revert and keep the subagent.")
    elif worse:
        lines.append(f"**{b['name']} scores the same or better overall, but got worse on {', '.join(worse)}.** "
                     "Read those traces before keeping the change.")
    else:
        lines.append(f"**{b['name']} holds.** It completes at least as many tasks as {a['name']} "
                     "and no task got worse.")

    notes = []
    if writes_changed:
        notes.append(f"Writes differ on {', '.join(c for c, _, _ in writes_changed)}. Check each one is a write the "
                     "task wanted. A task can pass its checks and still change something it should not.")
    if paths_changed:
        moved = sorted({case for case, _, _, _ in paths_changed})
        notes.append(f"The route changed on {', '.join(moved)}. Where the change was not meant to touch a task, "
                     "read its trace even if the score held, and say what the new route costs.")
    if paths_unknown:
        notes.append(f"Routes were not compared for {', '.join(paths_unknown)}: their rows do not record which "
                     "agents ran (`by_agent`).")
    if sa["models"] == sb["models"]:
        notes.append(f"Model for both runs: {', '.join(sa['models'])}.")
    if one_rep_flips:
        notes.append(f"Changed in a single rep: {', '.join(one_rep_flips)}. That can be noise. "
                     "Treat it as real only if the trace shows a cause.")
    if min(sa["reps"], sb["reps"]) < 2:
        notes.append("One run per task. A difference of a task or two can be noise, so rerun with "
                     "more reps before deciding a close call.")
    if "fake" in sa["models"] + sb["models"]:
        notes.append("At least one run used the offline stand-in model. These numbers say nothing about the app.")
    if sa["models"] != sb["models"]:
        notes.append(f"The runs used different models ({', '.join(sa['models'])} vs {', '.join(sb['models'])}), "
                     "so the change is not the only thing that differs.")
    if only_b:
        notes.append(f"Not compared because {a['name']} has no scored rows for them: {', '.join(only_b)}.")
    for variant in (a, b):
        if variant["errors"] or variant["skipped"]:
            notes.append(f"{variant['name']}: {variant['errors']} harness errors and {variant['skipped']} "
                         "unscored rows are left out of the numbers above.")
    if notes:
        lines += ["", "Notes:", ""] + [f"- {note}" for note in notes]
    return "\n".join(lines) + "\n", is_worse


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("flow", help="directory that holds the variant directories")
    parser.add_argument("before", help="variant name, usually baseline")
    parser.add_argument("after", help="variant name, for example v1")
    parser.add_argument("--metric", help="grade key to compare (default: the first one in the row)")
    parser.add_argument("--price-in", type=float, help="dollars per million input tokens")
    parser.add_argument("--price-out", type=float, help="dollars per million output tokens")
    parser.add_argument("--skip-tag", action="append", default=[],
                        help="leave out tasks with this tag, to compare on an earlier set of tasks (repeatable)")
    parser.add_argument("--exclude", action="append", default=[],
                        help="agent to leave out of 'Paths that changed': the main agent, and the agent the "
                             "change removes or renames, whose route is meant to move (repeatable)")
    parser.add_argument("--fail-if-worse", action="store_true", help="exit 1 when the verdict is 'worse'")
    args = parser.parse_args()

    flow = Path(args.flow)
    a, b = load(flow, args.before, args.metric), load(flow, args.after, args.metric)
    for variant in (a, b):
        variant["cases"] = {case: rows for case, rows in variant["cases"].items()
                            if not set(map(_clean, args.skip_tag)) & set(rows[0].get("tags", []))}
    common = sorted(set(a["cases"]) & set(b["cases"]))
    if not common:
        sys.exit("The two runs share no task ids, so there is nothing to compare.")
    only_a = sorted(set(a["cases"]) - set(b["cases"]))
    only_b = sorted(set(b["cases"]) - set(a["cases"]))
    sa = summarise(a, common, args.price_in, args.price_out)
    sb = summarise(b, common, args.price_in, args.price_out)
    text, is_worse = render(a, b, sa, sb, common, only_a, only_b, set(args.exclude))
    print(text, end="")
    return 1 if (is_worse and args.fail_if_worse) else 0


if __name__ == "__main__":
    raise SystemExit(main())
