# Single loop plan

Audit date: 2026-10-08
Repo and commit (or "not a git repo"): not a git repo (examples/support-desk in the kit download)

Edited after the run: the measured results and the result lines were removed from this
plan. `../README.md` has the command that prints them from the recorded logs.

## Status

- [x] Verdicts agreed with the person (end of step 0)
- [x] Main eval agreed and baseline measured (end of step 1)

A new session picks up at the first unticked box here, then at the first unticked item in
the worklist.

## Verdicts

| Agent | Verdict | Why, in one sentence | Evidence | Confidence |
| --- | --- | --- | --- | --- |
| router | main | It sees every request and already writes the final reply; it becomes the single loop. | `app/orchestrator.py:65-92`; `router.md:3,25` | high |
| orders | merge:shipping | Shipping never runs without orders right before it, and shipping needs the tracking id orders returns. | coupling map: orders -> shipping in 96 of 96 shipping traces; `shipping.md:3-4` | high |
| shipping | merge:orders | Same pair, seen from the other side. | same | high |
| returns | fold | A fixed procedure and a policy over three API calls, with ~2.7k tokens read per call; nothing needs its own context. | `returns.md:4-19`; traces median 2,674 input tokens | high |
| account | fold | Two lines of prompt over three API calls, ~1k tokens per call. | `account.md:3-4`; traces median 1,056 | high |
| diagnostics | as-tool | It reads ~31k tokens per call (a 900-line log where ~7 lines matter) and returns a five-sentence answer from one brief. | traces median 31,164 input tokens, 31% of subagent time; `backend.py:90-106`; `diagnostics.md:3-5` | medium |
| claims | keep | Harbor Mutual, an outside insurer, owns the prompt and requires the claim record to be the customer's own conversation with its agent; it is multi-turn with the user. | `subagents.py:62-65`; `claims.md:1-3` | high |

Glue that goes away as subagents fold (routers, classifiers, planners, context passing):

- `delegate` tool and its enum of specialists (`orchestrator.py:10-24`)
- `run_subagent` and the per-agent loop (`subagents.py:45-55`); stays only for diagnostics as a tool
- The "write the final reply from their summaries" step (`router.md:25`) and the brief/summary hops
- Router team-rules about routing order (`router.md:17-19`)
- `routing_accuracy.jsonl` stops meaning anything once there is nothing to route to
- Stays: `handoff_to_claims` and `ClaimsSession` (`orchestrator.py:25-33, 55-63, 86-91`)

## Prompt notes

What the fold step will need from each prompt: hard limits that belong in tools, persona
to drop, instructions about other agents, router rules that conflict.

- **returns**: hard limit `returns.md:15` ("NEVER create a return unless eligible") is only
  enforced by the prompt; `backend.create_return` does not check (`backend.py:154-155`). Move
  it into the tool. The reason list (`returns.md:18-19`) belongs in the tool schema as an enum.
  Drop the "Remy" persona and forced greeting (`returns.md:1-2`). "Think step by step" (`:4`)
  is old-model scaffolding.
- **account**: "never print a full street address" (`account.md:4`, repeated in `router.md:20`)
  is an output rule; consider having the tool return a masked address so it cannot leak.
- **orders**: "Do not speculate about delivery dates. That is the shipping team's job"
  (`orders.md:4-5`) is an instruction about another agent; goes away with the merge.
- **shipping**: "say the orders specialist has to be called first" (`shipping.md:3-4`) is an
  instruction about another agent; the merged agent can look up the order itself.
- **diagnostics**: "WARN lines are informational, ERR lines matter" (`diagnostics.md:3-4`) is
  a filter rule that could live in the log tool.
- **claims**: owned by the insurer; leave untouched.
- **router**: `router.md:3` "MUST NEVER answer yourself" is removed at the first fold.
  Conflicts: `:17` (orders before shipping) vs `:18` (shipping first for timing); `:19` (returns
  first even if they ask something else) fights cross-domain requests like golden t11; `:22`
  ("concise") vs `:23` (mandatory closing line). `:4` "Think step by step" is old scaffolding.
  `:20` duplicates the account rule.

## Evals

Filled in during step 1.

| Eval | What it measures | What to do with it |
| --- | --- | --- |
| `evals/golden.jsonl` + `evals/run_eval.py` | 12 end-to-end tasks graded on backend actions and the reply text, not the route. Tags give per-agent slices: orders+shipping t01-t03, returns t04-t06, account t07-t08, diagnostics t09, claims t10 (multi-turn), cross-domain t11-t12 | Main metric. Read the `returns` slice (t04-t06, t11) on its own after v1 |
| `evals/routing_accuracy.jsonl` | 8 inputs, checks only which subagent is picked first; no runner | Leave as is while the router exists; do not use it to compare designs |

Main metric: golden task completion (agreed with the person on 2026-10-08)

Gaps noticed:
- No task checks that a full street address stays out of the reply (t07 checks only the action).
- No task asks to return an order that has not been delivered (5002, 5006).
- No task where the customer pushes for an ineligible return; t05/t06 ask once politely.
- Traffic is roughly proportional except claims (1 task, 5% of traffic) and diagnostics (2 tasks, 12%), which is fine.

Baseline (variant `baseline`): tasks complete, latency per task, tokens per task, model
calls per task, and how far the score moved between reps.

Measured 2026-10-08 on `KIT_MODEL=claude-opus-5`, 12 tasks x 2 reps.

## Worklist

Merges first, then folds, then as-tool changes. Highest traffic first inside each group.
One line per change. Each variant is compared with the last one that was kept. A reverted
variant keeps its number and is skipped.

Note: the person asked for returns to go first as `v1`, so the order below is the person's,
not the default (default would put the orders+shipping merge first).

- [ ] 1. Fold `returns` into the main agent (skill + tools); router becomes the main agent. Hard requirement: `create_return` refuses ineligible orders in code, checked by a direct tool call that bypasses the model (golden t05/t06 cover the model path) · variant `v1` · compared with `baseline` · result: removed after the run. Not yet run: with/without-skill check. Returns subagent code not deleted yet.
- [ ] 2. Fold `orders` + `shipping` together in one change (both thin, read-only, 3 tools total) · variant `v2` · compared with `<last kept>` · result:
- [ ] 3. Fold `account` · variant `v3` · compared with `<last kept>` · result:
- [ ] 4. Call `diagnostics` as a tool with a structured result · variant `v4` · compared with `<last kept>` · result:

## Open questions for owners

- **Diagnostics**: could `fetch_device_logs` return only ERR/WARN lines, or search the log?
  If yes, diagnostics may be a `fold` with a better tool instead of `as-tool`.
- **Router team rules**: orders-first (`:17`) vs shipping-first (`:18`), and returns-first
  (`:19`) vs mixed requests. Which wins? Most of this disappears once there is no routing.
- **Brand**: is the mandatory closing line (`router.md:23`, 2024) still wanted?
- **Account**: OK to mask the address in `get_account` output rather than rely on the prompt?
- **Router owner** is unknown.
- **Returns**: who signs off on moving the eligibility check into `create_return`?
- **Subagent tool dispatch**: `subagents._run_tools` passes any tool name to the backend, not just the agent's declared tools. Pre-existing; goes away as the remaining subagents fold, or fix it on its own.

## Left as it is, and why

- **claims** (`keep`): run by Harbor Mutual; contract requires the claim transcript to be the
  customer's own conversation with its agent (`subagents.py:62-65`). The handoff stays.
