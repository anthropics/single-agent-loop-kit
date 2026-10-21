# Example: Tamberwick Home support desk

A small, runnable multi-agent system to try the kit on. Everything about Tamberwick Home is
made up.

| Path | What it is |
| --- | --- |
| `app/` | The system as it starts: a router plus six subagents, each with its own prompt, tools and context |
| `evals/golden.jsonl` | Nineteen end-to-end tasks, graded on what the agent did and what it told the customer. t01 to t12 cover each domain. t13 to t19, tagged `break-check`, are there to notice a change breaking something. Each task names the customer who is signed in (`customer`) |
| `evals/routing_accuracy.jsonl` | An older eval that only checks which subagent was picked |
| `evals/run_eval.py` | The eval runner. `--help` shows the options |
| `traces/traces.jsonl` | 200 synthetic production traces, one line per subagent call |
| `single_loop/` | One end state: the same agent as a single loop |
| `RUNBOOK.md` | How to run the kit on this example |
| `ANSWER-KEY.md` | The verdict each subagent was built to deserve. Read it after the audit |
| `example-run/` | Two real runs of the runbook: plan, results, traces and the diff for a fold, and in `as-tool/` for a subagent called as a tool. Read it after the audit |

The backend in `app/backend.py` is in memory and deterministic, so every run sees the same
orders, shipments and device logs.

`app/` is the "before" system. It is there to be audited, with its gaps left in, so do not
copy it as a starting point.
