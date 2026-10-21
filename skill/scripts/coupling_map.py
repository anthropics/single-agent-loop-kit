#!/usr/bin/env python3
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""Show which subagents carry the traffic and which ones always run together.

Input is a JSONL file with one line per subagent call:

    {"trace_id": "t-001", "ts": "2026-09-01T10:00:02Z", "agent": "orders", "duration_ms": 1800}

Only trace_id, ts and agent are required. ts can be an ISO string or a number;
it is only used to order calls inside a trace. duration_ms and input_tokens are
used when present. Use --trace-key/--agent-key/--ts-key if your export names the
fields differently.

    python3 coupling_map.py traces.jsonl
    python3 coupling_map.py traces.jsonl --exclude router --min-coupling 0.6

A pair is a merge candidate when one agent runs right after the other in at
least --min-coupling of the traces that contain the rarer of the two, and the
pair shows up in at least --min-share of all traces.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone


def clean(value) -> str:
    """A value from the input as one line of plain text. Whoever reads the report, often a coding agent,
    must not be able to mistake a name in the data for a new line, heading or table cell of the report."""
    return re.sub(r"([\\|`])", r"\\\1", " ".join(str(value).split()))


def _when(ts) -> tuple:
    """A sort key for a timestamp: a number, or ISO 8601 text with any precision or offset."""
    if isinstance(ts, (int, float)):
        return (0, float(ts), "")
    try:
        moment = datetime.fromisoformat(str(ts).strip().replace("Z", "+00:00"))
    except ValueError:
        return (1, 0.0, str(ts))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return (0, moment.timestamp(), "")


def load(path: str, trace_key: str, agent_key: str, ts_key: str, exclude: set[str]) -> dict[str, list[dict]]:
    traces: dict[str, list[dict]] = defaultdict(list)
    with open(path) as f:
        for number, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                if row[agent_key] in exclude:
                    continue
                traces[str(row[trace_key])].append(
                    {"agent": row[agent_key], "ts": row[ts_key],
                     "duration_ms": row.get("duration_ms"), "input_tokens": row.get("input_tokens")})
            except (json.JSONDecodeError, KeyError) as exc:
                sys.exit(f"{path}:{number}: cannot read this line ({exc!r}). "
                         f"Each line needs {trace_key}, {agent_key} and {ts_key}.")
    for calls in traces.values():
        calls.sort(key=lambda c: _when(c["ts"]))
    return traces


def analyse(traces: dict[str, list[dict]], min_coupling: float, min_share: float) -> dict:
    total = len(traces)
    calls, in_traces, chains, sequences = Counter(), Counter(), Counter(), Counter()
    durations, tokens = defaultdict(list), defaultdict(list)
    for sequence in traces.values():
        names = [c["agent"] for c in sequence]
        calls.update(names)
        in_traces.update(set(names))
        chains.update({(a, b) for a, b in zip(names, names[1:]) if a != b})
        sequences[" -> ".join(names)] += 1
        for c in sequence:
            if c["duration_ms"] is not None:
                durations[c["agent"]].append(c["duration_ms"])
            if c["input_tokens"] is not None:
                tokens[c["agent"]].append(c["input_tokens"])

    time_total = sum(sum(v) for v in durations.values())
    volume = [{
        "agent": agent,
        "calls": calls[agent],
        "trace_share": in_traces[agent] / total,
        "median_ms": statistics.median(durations[agent]) if durations[agent] else None,
        "time_share": sum(durations[agent]) / time_total if time_total else None,
        "median_input_tokens": statistics.median(tokens[agent]) if tokens[agent] else None,
    } for agent in sorted(calls, key=lambda a: (-in_traces[a], a))]

    pairs = []
    for (a, b), n in sorted(chains.items(), key=lambda kv: (-kv[1], kv[0])):
        rarer = a if in_traces[a] <= in_traces[b] else b
        pairs.append({"first": a, "then": b, "traces": n, "rarer": rarer, "rarer_traces": in_traces[rarer],
                      "coupling": n / in_traces[rarer], "share": n / total})

    stamps = sorted(str(c["ts"]) for sequence in traces.values() for c in sequence)

    candidates = [p for p in pairs if p["coupling"] >= min_coupling and p["share"] >= min_share]
    return {"traces": total, "calls": sum(calls.values()), "first_ts": stamps[0], "last_ts": stamps[-1],
            "volume": volume, "sequences": sequences.most_common(8), "pairs": pairs, "candidates": candidates}


def _pct(value) -> str:
    return "" if value is None else f"{value:.0%}"


def _num(value) -> str:
    return "" if value is None else f"{value:,.0f}"


def render(report: dict) -> str:
    total = report["traces"]
    lines = ["# Coupling map", "",
             f"{total} traces, {report['calls']} subagent calls, from {clean(report['first_ts'])} "
             f"to {clean(report['last_ts'])}. "
             "Check that this window is typical before leaning on the numbers.", "",
             *(["Fewer than 50 traces, so read every number below as a hint, not a measurement.", ""]
               if total < 50 else []),
             "## Volume", "",
             "\"In % of traces\" is the share of traces the agent appears in, so the column can add up to "
             "more than 100%. \"% of subagent time\" is its share of all subagent time and adds up to 100%. "
             "Medians are per call.", "",
             "| agent | calls | in % of traces | median ms | % of subagent time | median input tokens |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for v in report["volume"]:
        lines.append(f"| {clean(v['agent'])} | {v['calls']} | {_pct(v['trace_share'])} | {_num(v['median_ms'])} "
                     f"| {_pct(v['time_share'])} | {_num(v['median_input_tokens'])} |")
    lines += ["", "## Most common sequences", "",
              "The subagents each trace called, in order.", "",
              "| sequence | traces | % of traces |", "| --- | ---: | ---: |"]
    for sequence, count in report["sequences"]:
        lines.append(f"| {clean(sequence)} | {count} | {_pct(count / total)} |")
    lines += ["", "## Pairs", "",
              "A row means the second agent ran right after the first in the same trace. Coupling is that "
              "count over the number of traces containing the rarer of the two agents, shown in brackets.", "",
              "| first -> then | traces | coupling | % of traces |", "| --- | ---: | ---: | ---: |"]
    for p in report["pairs"]:
        lines.append(f"| {clean(p['first'])} -> {clean(p['then'])} | {p['traces']} "
                     f"| {_pct(p['coupling'])} (of {p['rarer_traces']} with {clean(p['rarer'])}) | {_pct(p['share'])} |")
    lines += ["", "## Merge candidates", ""]
    if report["candidates"]:
        for p in report["candidates"]:
            first, then = clean(p["first"]), clean(p["then"])
            lines.append(f"- **{first} + {then}**: {then} runs right after {first} in "
                         f"{p['traces']} traces ({_pct(p['share'])} of traces, coupling {_pct(p['coupling'])}).")
    else:
        lines.append("None above the thresholds.")
    lines += ["", "This script only measures traffic. Which subagents to fold, keep or leave alone, and in "
                  "what order, is decided in the audit."]
    return "\n".join(lines) + "\n"


class _Help(argparse.RawDescriptionHelpFormatter, argparse.ArgumentDefaultsHelpFormatter):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=_Help)
    parser.add_argument("traces", help="JSONL file, one subagent call per line")
    parser.add_argument("--trace-key", default="trace_id", help="field holding the trace id")
    parser.add_argument("--agent-key", default="agent", help="field holding the agent name")
    parser.add_argument("--ts-key", default="ts", help="field holding the timestamp")
    parser.add_argument("--exclude", action="append", default=[],
                        help="agent name to ignore, if the router shows up as an agent (repeatable)")
    parser.add_argument("--min-coupling", type=float, default=0.5,
                        help="lowest coupling for a merge candidate")
    parser.add_argument("--min-share", type=float, default=0.05,
                        help="lowest share of all traces for a merge candidate")
    parser.add_argument("--json", action="store_true", help="print the raw numbers as JSON")
    args = parser.parse_args()

    everything = load(args.traces, args.trace_key, args.agent_key, args.ts_key, set())
    present = {call["agent"] for sequence in everything.values() for call in sequence}
    for name in args.exclude:
        if name not in present:
            print(f"Note: --exclude {name} matched no agent in this file.", file=sys.stderr)
    traces = load(args.traces, args.trace_key, args.agent_key, args.ts_key, set(args.exclude))
    if not traces:
        sys.exit("No subagent calls found in that file.")
    report = analyse(traces, args.min_coupling, args.min_share)
    print(json.dumps(report, indent=2) if args.json else render(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
