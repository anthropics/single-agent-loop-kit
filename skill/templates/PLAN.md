# Single loop plan

Audit date:
Repo and commit (or "not a git repo"):

## Status

- [ ] Verdicts agreed with the person (end of step 0)
- [ ] Main eval agreed and baseline measured (end of step 1)

A new session picks up at the first unticked box here, then at the first unticked item in
the worklist.

## Verdicts

| Agent | Verdict | Why, in one sentence | Evidence | Confidence |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

Glue that goes away as subagents fold (routers, classifiers, planners, context passing):

-

## Prompt notes

What the fold step will need from each prompt: hard limits that belong in tools, persona
to drop, instructions about other agents, router rules that conflict.

-

## Evals

Filled in during step 1.

| Eval | What it measures | What to do with it |
| --- | --- | --- |
|  |  |  |

Main metric:

Gaps noticed:

Chains with no task (from `chain_coverage.py`):

Break map: which tasks would notice each kind of break. "none" is a gap to raise.

| What could break | Tasks that would notice | Gap, and the task to add |
| --- | --- | --- |
| Dropped handoff |  |  |
| Lost rule |  |  |
| Shortcut |  |  |
| Wrong pick |  |  |
| Unwanted write |  |  |
| Lost thread |  |  |
| Unhappy path |  |  |

Baseline (variant `baseline`): tasks complete, latency per task, tokens per task, model
calls per task, and how far the score moved between reps.

## Worklist

Merges first, then folds, then as-tool changes. Highest traffic first inside each group.
One line per change. Each variant is compared with the last one that was kept. A reverted
variant keeps its number and is skipped. Variants are numbered in the order the changes
are made, so leave the variant blank until a change starts. If the person takes the list
out of order, say so here.

- [ ] 1. `<change>` · variant: · compared with: · result:
- [ ] 2. `<change>` · variant: · compared with: · result:

## Changes

One section per change, filled in as it is made. Copy this block.

### Item <n>: `<change>` (variant `<vN>`, branch or commit)

Comparison with `<last kept variant>`: the table from `compare.py`, and tokens used next
to the estimate.

- Tasks that changed score, each with its cause from the trace:
- Tasks that changed route but not score, and what the new route costs:
- What was edited in the main agent's prompt and tool list:
- Checked with no model (unit tests, direct tool calls):
- Reruns, if any: variant names, the commit each side ran on, and each task over all reps:
- Skipped or not measured:
- Decision (who, when): keep / fix / revert
- Left open after the decision:

## Open questions for owners

-

## Left as it is, and why

-
