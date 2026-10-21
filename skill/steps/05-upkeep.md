# Step 5: Upkeep

A single agent that many teams add to needs a few habits to stay good. Run through this
after the first fold, and again whenever the plan is finished or the model changes.

## Shrink the system prompt

The rules and descriptions that named a folded subagent came out with its fold and were
scored with it. What is left for this step is what no single fold owned: ordering rules
between agents that are gone, rules that contradict each other, lines written for an older
model. Then run `/claude-api prompt-audit` on the system prompt, the skills and the tool
descriptions. It flags instructions written for older models and proposes a diff. Each
team can run it on their own skills too.

Delete by default. When behaviour is off, the fix is rarely one more sentence in the
system prompt. It is usually a clearer skill or a better tool result.

Everything in this step that edits the system prompt, removes a skill or rewrites a tool
description changes what every task sees. Gather one round of it into one change: its own
variant, a comparison with the last kept variant, and a check-in with the size of the run
before it and keep, fix or revert after it.

## Keep the skill library healthy

- `/skill-doctor` shows what each skill costs in context and how often it is used. Remove
  the ones nobody loads.
- `/skill-creator` drafts new skills and audits existing ones for descriptions that are
  vague or overlap.
- For each skill, keep the with and without test from step 3. Rerun it at every model
  upgrade and retire skills the model no longer needs.

## Tune, then trim cost

- `/claude-api hillclimb` iterates on a skill or tool description against the eval. Give
  it one target at a time.
- `/claude-api cost-optimize` profiles where the tokens go and proposes savings one change
  at a time. Run it once the design has stopped moving.

## Settle who owns what

Copy `templates/CONTRIBUTING-skills.md` into the repo and adapt it. The short version:

- One small central team owns the system prompt, the shared end-to-end eval, and the
  review of anything new.
- Each domain team owns its skills and tools, names a person responsible for them, and
  ships an eval with each skill.
- Nothing new ships without a run of the shared eval.

## Check in

Check in with what was deleted, what the audit proposed, the comparison for the round, and the ownership file. The
plan is finished when every row is ticked or has a written reason for staying as it is.
