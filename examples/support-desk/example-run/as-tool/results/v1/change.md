Call the `diagnostics` subagent as a tool (`diagnose_device`) with a structured, checked result.

Branch `as-tool-diagnostics`, commit 52251d4, compared with `baseline` (commit 0610370). Step 4 of the single-agent-loop skill. The person chose this change; it is item 4 of the worklist, taken first.

What changed:

- `app/orchestrator.py`: new router tool `diagnose_device` with required `serial` and `question`. A call without a serial number is refused in code. `diagnostics` is no longer in the `delegate` enum.
- `app/subagents.py`: `run_subagent_as_tool` runs the subagent in a fresh context with its own prompt plus `prompts/subagent_response.md`, and checks the result against `app/subagent_response.schema.json`. A result that does not fit is passed on marked low confidence with a caveat. An empty one is an error.
- `app/prompts/router.md`: diagnostics leaves the specialist list; one paragraph says to call the tool and to ask for a missing serial number.
- `app/prompts/diagnostics.md` is unchanged. The old delegate route still works in code and is intact on `main`.
- `tests/test_diagnose_device.py`: the two failure paths and the happy path with no model.

Run: `python3 evals/run_eval.py --variant v1 --reps 2`, 2026-10-09 13:50 to 14:06 UTC, claude-opus-5, 0 harness errors.
