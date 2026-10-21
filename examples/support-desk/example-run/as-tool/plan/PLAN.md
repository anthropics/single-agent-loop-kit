# Single loop plan

Audit date: 2026-10-09
Repo and commit: examples/support-desk at 0610370 ("Starting point")

Edited after the run: the measured results, the token estimates and the result lines were
removed from this plan. `../README.md` has the commands that print the results from the
recorded logs.

## Status

- [x] Verdicts agreed with the person (end of step 0). Agreed 2026-10-09, including `diagnostics` as `as-tool` with the log-filter question still open.
- [x] Main eval agreed and baseline measured (end of step 1). Agreed 2026-10-09: `evals/golden.jsonl` as it stands, without the two gap tasks.

A new session picks up at the first unticked box here, then at the first unticked item in
the worklist.

## Verdicts

Traffic and token numbers are from `traces/traces.jsonl` (200 traces, 322 subagent calls,
2026-09-01 to 2026-09-02) through `coupling_map.py`. The backing record is
`single-loop/inventory.tsv`.

| Agent | Verdict | Why, in one sentence | Evidence | Confidence |
| --- | --- | --- | --- | --- |
| router | `main` | It routes every request and already writes the final reply, so it is what becomes the single loop. | `app/orchestrator.py:65-92`; `router.md:25` | high |
| orders | `merge:shipping` | Shipping never runs without it, and its only job in that chain is to hand over a tracking id. | shipping follows orders in 96 of 96 traces with shipping (48% of all traces); `orders.md:3-5` | high |
| shipping | `merge:orders` | It cannot start without the orders result and reads under a thousand tokens. | `shipping.md:3-4`; `router.md:17`; ~760 input tokens per call | high |
| returns | `fold` | A four-step procedure over three API calls with nothing that needs its own context. | `returns.md:4-8`; ~2,700 input tokens per call; 25% of traces | high |
| account | `fold` | Two sentences of prompt over three API calls. | `account.md:3-4`; ~1,060 input tokens per call; 15% of traces | high |
| diagnostics | `as-tool` | It reads a 900-line device log and hands back five sentences, which the main agent has no use for in full. | ~31,200 median input tokens per call (range 26k to 36k), 31% of subagent time at 12% of traces; `backend.py:90-106,183-186`; `diagnostics.md:5` | medium |
| claims | `keep` | The insurer runs it, and requires the claim record to be the customer's own conversation with its agent. | `app/subagents.py:67-70`; `claims.md:1-3`; multi-turn handoff at `orchestrator.py:54-58,86-91` | high |

Why diagnostics is medium: the context test passes on today's numbers, but only 7 of the
900 log lines matter (5 ERR, 2 WARN, `backend.py:99-102`). If `fetch_device_logs` could
filter by level, the read drops to a few hundred tokens and the better plan is `fold` with
a better tool. That is an owner question, listed below.

Glue that goes away as subagents fold (routers, classifiers, planners, context passing):

- The `delegate` tool and its agent enum: `app/orchestrator.py:10`, `:13-24`, and the dispatch at `:77-78`.
- The brief the router writes for each specialist, and the summary stitching in `router.md:25`.
- `run_subagent` (`app/subagents.py:50-60`), once nothing but diagnostics calls it.
- Per-agent tool ownership: `TOOLS_BY_AGENT` (`app/tools.py:27-64`) and the `declared` check (`app/subagents.py:37-41`). Three agents each wrap `get_order` (`tools.py:29,37,57`).
- Ordering rules that exist only to pass context between agents: `router.md:17`, `shipping.md:3-4`.

Stays: `handoff_to_claims` and `ClaimsSession` (`orchestrator.py:25-33,86-91`; `subagents.py:63-90`).

## Prompt notes

What the fold step will need from each prompt: hard limits that belong in tools, persona
to drop, instructions about other agents, router rules that conflict.

Hard limits that belong in a tool:

- `returns.md:15` "NEVER create a return unless check_return_eligibility returned eligible: true". `create_return` does not enforce it (`backend.py:153-159`); the prompt is the only guard. The policy at `returns.md:10-13` repeats what `check_return_eligibility` already computes (`backend.py:139-151`).
- `account.md:4` and `router.md:20` "never reveal a full address". `get_account` and `update_shipping_address` both return the full address (`backend.py:166,173`), so the rule holds only as long as two prompts hold it.

Persona and tone to drop (the main prompt owns voice):

- `returns.md:1-2`: "Remy, the cheerful Returns Concierge" and the "Greetings, valued customer!" opener. The router rewrites every reply, so it never reaches the customer today.
- `account.md:1` "ACCOUNT AGENT.", and the "You are the X specialist" openers in orders, shipping and diagnostics.

Instructions about other agents (go away with the agents):

- `orders.md:4-5` "Do not speculate about delivery dates. That is the shipping team's job."
- `shipping.md:3-4` "say ... the orders specialist has to be called first."
- `router.md:3` "You MUST NEVER answer a customer question yourself." Goes with the first fold.
- `router.md:6-11` the specialist list, `router.md:25` the stitching instruction.

Router rules that conflict or have aged:

- `router.md:17` [orders team] "always call orders before shipping" against `router.md:18` [shipping team] "route to shipping first" for delivery timing. Shipping refuses without a tracking id (`shipping.md:3-4`), so the second rule cannot be followed as written. The merge removes both.
- `router.md:19` [returns team] "route to returns even if they also ask about something else" invites dropping the other half of a two-part request (the returns chains: shipping then returns 6%, account then returns 3%).
- `router.md:22` [brand] "warm and concise" against `router.md:23` [brand, 2024] a fixed closing line on every reply.
- `router.md:4` and `returns.md:4` "Think step by step": written for older models.

Worth carrying over as they are: `shipping.md:6` (dates as "October 3"), `diagnostics.md:3-5`
(ERR lines matter, WARN lines are informational, five sentences, no pasted log lines),
`returns.md:18-19` (the allowed return reasons; better as an enum on `create_return`).

Not ours to edit: `claims.md` (Harbor Mutual's prompt).

## Evals

Filled in during step 1.

| Eval | What it measures | What to do with it |
| --- | --- | --- |
| `evals/golden.jsonl` with `evals/run_eval.py` | End to end: 17 tasks through `app.new_conversation`, graded on the backend's action log and on what the customer was told. Tags mark each subagent's slice. t13 to t17 are break checks | Main metric. Reused as it is |
| `evals/routing_accuracy.jsonl` | Which subagent the router picks first, 8 inputs, no runner | Left alone. Not used to compare designs: a single loop has no route to grade |

Main metric: task completion on `evals/golden.jsonl` (the person asked to reuse the eval that is here).

Model, pinned for every variant: `claude-opus-5` (from `KIT_MODEL`, the model the probe ran on).

Probe (variant `probe`, run by the person before the session, commit 0610370): t08 and t09,
one rep each.

The baseline was estimated from the probe (`estimate.py probe --tasks 17 --reps 2 --heavy 2`)
for 34 conversations. Heavy count is 2 (t09 and t12, the two tasks that give a serial
number). Rests on two measured tasks.

Gaps noticed:

- No multi-turn diagnostics task (the customer gives the serial number on a second turn). Task to add if wanted: turn 1 is t16's message, turn 2 is "It's SN-VAC-3391.", graded on E42 and the brush-roll fix. It is a heavy task.
- No diagnostics task where the tool errors (a serial number that does not exist, `backend.py:184-185`). Task to add if wanted: "My vacuum SN-VAC-0000 keeps stopping", graded on saying the device was not found, on leaving out E42, and on no writes. It is a light task.
- Nothing grades the rules inside `diagnostics.md:3-5` directly (WARN lines are informational, five sentences, no pasted log lines). t09 and t12 pass as long as E42 and the fix are in the reply.
- t01 to t12 do not set `only_expected_writes`, so an extra write on those tasks is only seen through `compare.py`'s list of tasks whose writes changed.
- t16: the grader only requires asking for an identifier and leaving out E42.

Chains with no task (from `chain_coverage.py --exclude router`): none. All nine production
chains have a task. The two that include diagnostics: `diagnostics` alone (t09, t12, t16)
and `diagnostics -> orders -> shipping` (t12). t12 grades both ends of its chain:
the error code from diagnostics, and the October 6 ETA, which only shipping has and which
needs the tracking id from orders to survive the handoff.

Break map: which tasks would notice each kind of break. "none" is a gap to raise.

| What could break | Tasks that would notice | Gap, and the task to add |
| --- | --- | --- |
| Dropped handoff | t01, t02 (tracking id from orders to shipping); t12 (diagnostics, orders, shipping); t13 (account, returns); t11 (orders, shipping, returns) | result line removed after the run |
| Lost rule | t05, t06 (no return outside policy); t14 (no full address); t16 (no error code without a log) | none for the WARN, five-sentence and no-log-lines rules in `diagnostics.md` |
| Shortcut | t01, t02 (the ETA only tracking has); t09, t12 (the fix only `lookup_error_code` has) | |
| Wrong pick | t15 (a broken kettle the customer wants returned, not diagnosed); t16; one plain task per domain in t01 to t10 | |
| Unwanted write | t13 to t17 (`only_expected_writes`); t03, t05, t06 (`forbidden_actions`) | t01 to t12 rely on `compare.py` listing changed writes |
| Lost thread | t10 (claims, three turns); t17 (returns, two turns) | none for diagnostics. Task to add: serial number given on turn 2 |
| Unhappy path | t16 (no serial number); t03 (no tracking id yet); t05, t06 (not eligible) | none for a serial number that does not exist |

Baseline (variant `baseline`, 2026-10-09 13:25 to 13:42 UTC, `claude-opus-5`, commit 0610370,
`python3 evals/run_eval.py --variant baseline --reps 2`, 0 harness errors).

## Worklist

Merges first, then folds, then as-tool changes. Highest traffic first inside each group.
One line per change. Each variant is compared with the last one that was kept. A reverted
variant keeps its number and is skipped.

The list below is in the default order. Variant numbers are given out in the order the
changes are actually made, so they are filled in as each change starts.

- [ ] 1. Merge `orders` + `shipping` into one subagent (56% of traces; expected verdict for the merged agent: `fold`) · variant: · compared with: · result:
- [ ] 2. Fold `returns` into a skill plus tools (25% of traces). As the first fold, it also turns the router into the main agent · variant: · compared with: · result:
- [ ] 3. Fold `account` (15% of traces) · variant: · compared with: · result:
- [x] 4. Call `diagnostics` as a tool with a structured result (12% of traces) · variant `v1` · compared with `baseline` · result: removed after the run. Reruns of t01 and t10 (4 reps each, variants `baseline-t01-t10` and `v1-t01-t10`) were run before the decision. Decision (the person, 2026-10-09): keep. The old delegate route to `diagnostics` is left in the code at their request, so the branch stays exactly what was scored (commit 52251d4). It is not merged to `main`. Details under "Item 4" below.

Order taken in this session: the person chose item 4 (`diagnostics` as a tool) as the one
change for this session, ahead of items 1 to 3. Items 1 to 3 are not started. The next
variant is `v2`, compared with `v1`. That was their pick, not the default order.
It runs as variant `v1`, compared with `baseline`.

Note on item 1: both agents are thin (60 and 80 tokens of prompt, read-only tools), so
folding the pair in one change, without merging first, is a fair alternative. It saves one
eval run and costs the safety of a step in which the main agent does not change.

### Item 4: `diagnostics` as a tool (variant `v1`, branch `as-tool-diagnostics`, commit 52251d4)

Checked with no model (`tests/test_diagnose_device.py`, 5 tests): a call with no serial number is refused before any model call; a result that is prose, misses a field, has a bad confidence value or an extra field comes back marked low confidence with a caveat; an empty result is an error.

Rerun of t01 and t10, asked for by the person at the first check-in (2026-10-09 14:13 to 14:17 UTC, 4 reps of each task, 0 harness errors; the full v1 run also had 0). Written under new variant names so `baseline` and `v1` stay as they were: `baseline-t01-t10` ran from `main` (0610370), `v1-t01-t10` from `as-tool-diagnostics` (52251d4).

Skipped or not measured:

- Step 4 says to let the main agent check the conclusion against data it can read cheaply. The router has no data tools, so it can only check the conclusion against the `evidence` list in the result. Giving it `lookup_error_code` would have been a second change.
- The two gap tasks (serial number on a second turn, a serial number that does not exist) were not added, by agreement.
- No rule moved, so there was none to prove.

Left open after the keep decision:

- The old route is still there: `run_subagent` and the `delegate` dispatch still work for `diagnostics`, though the router's enum no longer offers it (`app/orchestrator.py`). Step 4 says to delete it once the change is kept. The person chose to leave it.
- The two diagnostics gap tasks are still not in the eval.

What this does not fix, to revisit (for example at the next model upgrade):

- The subagent still has its own prompt, its own owner and its own evals.
- Each call still hands back a summary, and summaries lose detail.
- Each call is a nested model loop, which adds latency. It still reads the whole 900-line log.

## Open questions for owners

- Diagnostics team: can `fetch_device_logs` filter by level or return only ERR and WARN lines? If yes, `diagnostics` becomes a `fold` with a better tool, and the as-tool change is a stopgap.
- Orders and shipping teams: `router.md:17` and `router.md:18` contradict each other. Which behaviour is wanted for "when will it arrive" when the customer gives only an order number?
- Returns team: should `create_return` refuse an ineligible order itself, so `returns.md:15` stops being the only guard?
- Account team: can `get_account` and `update_shipping_address` return a masked address?
- Brand: is the 2024 closing line (`router.md:23`) still wanted on every reply?
- Harbor Mutual: confirm the requirement that the claim record be the customer's own conversation with its agent (it is a code comment at `subagents.py:67-70`, not a contract we can read).
- Who owns the router prompt? No owner is recorded anywhere in the repo.
- Is the trace window (two days, 2026-09-01 to 2026-09-02) typical traffic?

## Left as it is, and why

- `claims`: run by Harbor Mutual, not Tamberwick, and it must hold the conversation with the customer itself over several turns. The handoff stays. Flagged, not edited.
