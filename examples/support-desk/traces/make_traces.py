#!/usr/bin/env python3
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""Generate the synthetic production traces for the Tamberwick Home example.

These are made up. They stand in for the export you would pull from your own
tracing system: one line per subagent call. The mix is fixed by a seed so the
file is reproducible:  python3 make_traces.py > traces.jsonl
"""

import json
import random
from datetime import datetime, timedelta, timezone

PATTERNS = [  # (subagents called in order, share of traffic)
    (["orders", "shipping"], 0.38),
    (["returns"], 0.16),
    (["account"], 0.12),
    (["orders"], 0.08),
    (["diagnostics"], 0.08),
    (["orders", "shipping", "returns"], 0.06),
    (["claims"], 0.05),
    (["diagnostics", "orders", "shipping"], 0.04),
    (["account", "returns"], 0.03),  # a misroute, then a re-delegation
]
PROFILE = {  # agent: (typical ms, typical input tokens)
    "orders": (1800, 900), "shipping": (2100, 800), "returns": (4500, 2600),
    "account": (2000, 1100), "diagnostics": (14000, 31000), "claims": (9000, 3400),
}


def main() -> None:
    rng = random.Random(7)
    clock = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)
    sequences = [agents for agents, share in PATTERNS for _ in range(round(share * 200))]
    rng.shuffle(sequences)
    for number, agents in enumerate(sequences, 1):
        clock += timedelta(seconds=rng.randint(30, 600))
        at = clock
        for agent in agents:
            ms, tokens = PROFILE[agent]
            duration = int(ms * rng.uniform(0.7, 1.4))
            print(json.dumps({
                "trace_id": f"t-{number:04d}",
                "ts": at.isoformat().replace("+00:00", "Z"),
                "agent": agent,
                "caller": "router",
                "duration_ms": duration,
                "input_tokens": int(tokens * rng.uniform(0.8, 1.2)),
            }))
            at += timedelta(milliseconds=duration + rng.randint(300, 900))


if __name__ == "__main__":
    main()
