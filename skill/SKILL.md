---
name: single-agent-loop
description: Move a multi-agent system (router, planner, subagents) toward one agent loop with skills and tools, one measured change at a time. Use when asked to audit subagents, decide which to fold, merge, keep or call as tools, fold a subagent into a skill, or check whether a fold held up.
---

# Single agent loop

This skill takes a codebase where a router or orchestrator delegates to specialist
subagents and moves it, in stages, toward one agent loop that loads skills and tools on
demand. Every change is measured against the same eval before and after, and a subagent
only goes away when the numbers say the replacement holds.

Keeping a subagent is a fine outcome. The goal is a system you have evidence for, not the
smallest possible number of agents.

## The steps

Read only the file for the step you are on.

| Step | File | Done when |
| --- | --- | --- |
| 0. Audit | `steps/00-audit.md` | The person has seen the inventory and agreed the verdicts |
| 1. Baseline | `steps/01-baseline.md` | The current system has a score the person trusts |
| 2. Merge | `steps/02-merge.md` | One pair is merged and compared |
| 3. Fold | `steps/03-fold.md` | One subagent is folded and compared |
| 4. Keep as a tool | `steps/04-as-tool.md` | One kept subagent is called as a tool and compared |
| 5. Upkeep | `steps/05-upkeep.md` | The prompt, skills and ownership rules are tidy |

Steps 2 to 4 repeat, once per row of the plan.

## How to run it

Start at step 0, unless `single-loop/PLAN.md` already exists in the repo. If it does, read
it and pick up at the first unticked box in its status list, then the first unticked item
in its worklist.

For each change in the plan:

1. Make the one change on its own branch or commit. If the folder is not a git
   repository, run `git init` and commit the starting state first, with the person's
   okay. Commit `single-loop/` with it, so the plan travels with the code. If the repo
   ignores that folder, say so at the first check-in. Keep eval results and traces out of
   git unless the team wants them shared.
2. Run the eval as the next variant. Variants are numbered in the order changes are made,
   not by their place in the worklist: the first change made is `v1`.
3. Run `scripts/compare.py` against the last variant that was kept.
4. Check in (see below) with the comparison and whether you would keep, fix or revert, or
   rerun when the result is unclear (see "When a result is unclear"). The person makes
   that call.
5. Tick the item in `single-loop/PLAN.md` and fill in its section under "Changes" with
   the numbers and the decision.

## Check-ins

The person decides and you recommend. They know things the code does not: who owns an
agent, which failures hurt, what is about to change. Stop at the same four points every
time:

1. **After the audit**, before anything is built on the verdicts.
2. **Before a paid run no earlier check-in covered**, with its size: how many
   conversations, an estimate of the tokens, and what that estimate is based on. In
   practice this is the baseline. After that, stops 3 and 4 name the next change together
   with every eval run it needs and their estimates. A merge or an as-tool change needs
   one run, the new variant. A fold that produces a skill needs two: the new variant, and
   the with and without skill check on that domain's tasks. You can say that without
   opening the next step's file. Anything a result leads to afterwards (more reps, a run
   without a skill that turned out not to be needed) is a new spend with its own yes. A yes there covers building that change and those runs, once each. It does not
   cover a rerun, or keeping the change. Do not stop a second time between building a
   change and running the evals the person already agreed. Do write one line before the
   run starts, without waiting for an answer: what you exercised with no model (unit
   tests, an offline run) and what the paid run will be the first to exercise.
3. **After the baseline**, before the first change.
4. **After each change**, once it is compared, before the next one starts. A change is one
   row of the worklist: one subagent folded, one pair merged, one subagent turned into a
   tool. That is one check-in per change, not one per edit inside it.

Step 1 can add questions before the first paid run, when it has to build an eval: what it
needs to build one, and a sign-off on the tasks it wrote. Those are stops too. End your
turn and wait for the answer. They do not use the layout below, since they ask for
material, not a decision.

At each one of the four, end your turn with a check-in in this layout. The question is
the last line: nothing comes before the heading or after the question. Keep it to about
fifteen lines with at most one small table. The check-in after a change has more to carry
and may run to about twenty-five. The detail lives in `single-loop/PLAN.md`.

```text
## Check-in: <which stop, for example "after the baseline">

**Found**
- <first, a direct answer to anything the person asked since the last check-in>
- <two to four lines: the numbers or verdicts, and anything that surprised you>
- <anything you did that the plan did not ask for: a file you edited, where the code is>

**Recommend**
- <one next action, and the reason in a sentence. If it leads to a paid run, its size and token estimate>
- <the other choice worth knowing about, if there is one, and what it costs>

**Need from you**
- <one question with its answers spelled out, for example "Fold returns next? yes / merge orders and shipping first">
```

One question means one decision, answerable in a word or two. After a change it is
"Keep it and go on to <next item>? keep and go on / keep and stop / fix / revert". When
you are recommending more reps or another paid run first, ask that instead, with its size:
"Rerun t01 and t10 first, 16 conversations? rerun / keep / revert". A second open choice
goes under Recommend as the other option. Questions only an
owner can answer do not fit here: say how many there are, that they are in `PLAN.md`
under "Open questions for owners", and ask only the one that blocks the next step, if any.

Rules for check-ins:

- A stop means stop. Do not start the next piece of work in the same turn, not even
  reading for it.
- One answer covers one stop. A yes to the spend is not a yes to the verdicts.
- A request that lists several steps at once does not remove the stops between them. Only
  the person saying so in plain words does. If they do, still write each check-in to
  `PLAN.md` as you go.
- With a long worklist, the person can ask you to keep going while results are clean. Then
  a change that holds, with no task worse in any rep and no route changed on a task the
  change should not touch, gets its check-in written to `PLAN.md` and you move on. In this
  mode that counts as the person's keep. Stop and check in as usual the moment a task gets
  worse, a route moves on a task the change should not touch, a check is skipped, or a run
  errors. Never offer this before the
  first change has had a full check-in.
- If the person's answer to a check-in also asks you something, answer it in a line
  before you carry on. Do not hold it for the next check-in.
- If the run surprised you (a task got worse, a number moved the wrong way, a check was
  skipped), say it under Found. Do not leave it for a summary at the end.
- If nobody is there to answer, stop at the check-in and leave it as the last thing you
  wrote.

## When a result is unclear

`compare.py` can say a change scores worse and, in the same output, that the task changed
in a single rep and may be noise. If that task is off the changed path and its trace shows
no cause, neither keep, fix nor revert is a recommendation you can stand behind. Recommend
more reps instead, at the check-in, as a paid run with its size and estimate:

1. Pick the tasks: each one whose score changed in a single rep, and each one the change
   should not touch whose route changed. Four more reps of each is a reasonable start.
   `estimate.py <flow dir> <variant> --only <ids> --reps 4` gives the size of each side.
2. Run them on both sides, the last kept variant and the new one, under new variant names
   that pair up: `baseline-rerun-v1` and `v1-rerun`. Do not add more reps of a task to a
   variant that has already been compared. Filling in a task that only has a harness
   error is different, and goes in the variant it belongs to.
3. The old side has to run on the old code. Check out the commit the last kept variant was
   scored on in a second working copy (`git worktree add`), run the eval there, and point
   its output at the same results folder. Record the commit each rerun used. Remove the
   second copy afterwards.
4. Compare the two rerun variants, then report each task over all of its reps on each
   side, the first run included. Check in again with keep, fix or revert. More reps make a
   small effect less likely, not impossible, so say how many reps the answer rests on.

## What holds in every step

- **One change per eval run.** If two things change at once, nobody can say which one
  moved the score.
- **No change without a task on its chains.** Before a merge, fold or tool conversion,
  the eval must have a task for every production chain that includes the agents being
  changed, and that task must grade the end of the chain. `scripts/chain_coverage.py`
  checks the first half. You check the second by reading the task. If you ran it for these
  agents at the baseline and neither the eval nor the traces have changed, cite that run.
  Step 1 also lists the other breaks to expect (a lost rule, a shortcut, a wrong pick, an
  unwanted write) and which tasks would notice each. A chain with no task has no way
  round it. A gap in the break map is the person's call: recommend adding the task first,
  and if they go ahead without it, write the gap in `change.md` and say at the check-in
  that the result says nothing about that break.
- **Score the system you would keep, and keep the old code until the person says keep.**
  In the variant you run, no model is offered the old path: it is out of every prompt,
  tool list and list of targets that names it, the main agent's and any other subagent's.
  The old code and prompt files stay in the repo, unused, so a revert is one step. Once
  the person says keep, delete them. Deleting then must change nothing a model sees. If
  it would, it is a change of its own, with its own variant.
- **Any edit to the main agent's prompt or tool list reaches every task.** Each sentence
  and each tool definition is paid for on every call, and it can change how unrelated
  tasks are routed. Keep such edits as small as the change allows, and say in `change.md`
  exactly what you edited there.
- **Read routes, not only scores.** After every change, look at "Paths that changed" in
  the `compare.py` output. Pass `--exclude` for the main agent and for the agent the
  change removes, whose route is meant to move, so what is left is what you did not
  intend. Open the traces of those tasks. A task can keep passing while it goes through
  an extra agent. Report a route that moved with what it costs in model calls and tokens,
  and whether the unchanged system does the same from rep to rep. If the section is
  missing because the rows do not record which agents ran, say that routes were not
  checked.
- **Eval runs spend money.** Before a paid run, say how big it is (tasks times reps) and
  give a token estimate from `scripts/estimate.py`, which works from a run that was already
  measured. Say what the estimate rests on and how far to trust it. After the run, show the
  estimate next to what was used. Do not turn tokens into money unless the person gives you
  their prices, and say that the estimate leaves out your own usage while reading and
  editing, which this skill cannot measure.
- **Use what the team already has.** Their evals, their runner, their idioms. Do not bring
  in a framework.
- **Every verdict cites evidence**: a file and line, or a number from the traces. Say when
  something is inferred.
- **Leave alone what the team does not own.** An agent run by another company or behind
  another team's endpoint gets flagged, not edited.

## Scripts and templates

Everything here sits in this skill's folder, next to this file. The scripts are plain
Python 3 with no dependencies. Run them with `--help` for the details.

- `scripts/coupling_map.py traces.jsonl` shows which subagents carry the traffic and which
  ones always run together.
- `scripts/compare.py <flow dir> <before> <after>` puts two eval runs side by side on task
  completion, latency, model calls, tokens and cost, lists the tasks whose writes or
  routes changed, and says whether the change holds.
  The flow dir is the folder with one subfolder per variant, `.claude/hillclimb/<name>/`
  unless the team keeps results somewhere else.
- `scripts/chain_coverage.py <traces> <flow dir> baseline` lists every set of agents that
  run together in production and the eval tasks that cover it, and fails when a chain has
  none.
- `scripts/estimate.py <flow dir> <measured variant> --reps N` estimates the tokens the
  next run will use from one already measured, and with `--actual <variant>` shows the
  estimate next to what a finished run used.

| Template | Used in |
| --- | --- |
| `templates/inventory.tsv`, `templates/PLAN.md` | Step 0 |
| `templates/skill-template.md`, `templates/skill_loader.py` | Step 3 |
| `templates/tool_spec.md` | Steps 3 and 4 |
| `templates/subagent_response.schema.json` | Step 4 |
| `templates/CONTRIBUTING-skills.md` | Step 5 |

## Commands this leans on

The steps hand off to these where they do the job better than anything written here:

- `/claude-api build-eval` builds or adapts an eval set.
- `/claude-api hillclimb` tunes a prompt, skill or tool description against an eval.
- `/claude-api prompt-audit` finds instructions written for older models.
- `/claude-api cost-optimize` profiles spend once the design has settled.
- `/skill-creator` writes and audits skills. It is a plugin:
  `/plugin install skill-creator@claude-plugins-official`.
- `/skill-doctor` shows what each skill costs and how often it is used.

If one of them is not available in the session, say so and do that part by hand from the
step file.
