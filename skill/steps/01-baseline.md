# Step 1: Baseline

Get a score for the system as it is today, so every later change has something to beat.
Reuse the team's evals first. Build only what is missing, which can be all of it.

## Find what already exists

Look for eval directories, test suites that call the agent, CI jobs, golden sets, labelled
transcripts and dashboards. For each one, note what it measures and whether it tests the
whole system end to end or one subagent.

| What you find | What to do with it |
| --- | --- |
| End-to-end task completion: did the request actually get done | Use it as the main metric |
| A rubric on the final answer | Use it. It is a good starting point for answer quality |
| Per-subagent evals | Keep them. After a fold they become the skill's own eval: point them at the main agent |
| Tags or groups inside one shared set | Treat each group as that subagent's slice. Read it on its own after the fold |
| Routing accuracy: did the right subagent get picked | Leave it as it is while there is a router, but do not use it to compare designs. A single loop has no route to grade |
| A dataset with no runner | Note it. Only build a runner if it would become part of the main metric |

Write the list into `single-loop/PLAN.md` under "Evals", along with any gaps you noticed
(a rule nothing checks, a common path with no task). If you found an end-to-end eval, ask
the person which eval is the main metric. Settle that before any money is spent.

Finding nothing is a normal place to start, not a reason to stop. Write "none found, built
in this step" under "Evals" and go on to the next section.

## Fill the gaps

The comparison needs one shared end-to-end set. Ten good tasks is enough to start. If the
existing evals do not give you that, whether there are none or only ones that test a part,
this step builds it with the person.

**Ask first.** Before writing any task or runner, tell the person what is missing and ask
for two things in one message, then end your turn and wait:

1. **A way to run the system on a test request without touching production.** The entry
   point to call, and test accounts, a sandbox or stand-ins for anything that reads or
   writes real customer data (refunds, emails, tickets, lookups). If the repo already has
   these, name what you found and ask whether it is safe to use.
2. **Real requests.** Ten to twenty transcripts, tickets or logged requests. If there are
   none to share, ask for the most common requests for each subagent instead.

Write the answers under "Evals" in `PLAN.md`: the entry point, what makes it safe and who
said so, and where the tasks come from. A later session needs them.

**Then build.** Hand off to `/claude-api build-eval`. Tell it what you found, so it adapts
and extends anything that exists instead of starting again, and pass on the person's
answers and the rules here. Ask for a set that:

- covers each subagent roughly in proportion to its traffic
- has a task for each chain of subagents the inventory lists (`chains_with`) and the
  coupling map shows in production, since shared context matters most there and "Check the
  chains" below will ask for them anyway
- includes multi-turn tasks if the product is conversational
- grades the outcome (what changed in the systems, what the user was told), not the path
  (which agent or tool ran). Path checks break the moment the design changes.

Real transcripts are the best source of tasks. Recorded production events that can be
replayed are the best source of realistic state. Rewrite each real request onto the test
accounts and records before it becomes a task: real names, order numbers and addresses do
not go into task files or traces, and they would not exist in a sandbox anyway.

**Get the tasks agreed.** For each task, draft what done means: what should have changed
in the systems and what the user must have been told. Then show the person the list, one
line per task with what it grades, and ask them to correct it. End your turn and wait.
Do not settle an expected outcome on your own: a wrong one scores every later change
against the wrong answer. The agreed set is the main metric. Record it in `PLAN.md`.

**Where this stops.** Two things cannot be built from here. If the system cannot be run
on a test request outside production, there is nothing safe to score against. If nobody
can say what a correct outcome is for the common requests, there is nothing to grade. In
either case say so plainly, write it at the top of `PLAN.md` as what blocks the plan, leave
the audit as a reading of the code, and make no change. A change without a score is an
opinion.

## Make the runner fit this job

Whatever runs the eval needs to:

- call the app's real entry point, so routing, retries and context assembly are all exercised
- record, per task: pass or score, wall-clock latency, input and output tokens, the
  number of model calls, and which agents ran (`by_agent`). The chain check below needs
  that last one
- take a variant name and write to `.claude/hillclimb/<flow>/<variant>/results.jsonl`,
  one JSON row per task and rep. `<flow>` is any short name for this eval, and that folder
  is the "flow dir" `compare.py` takes. `/claude-api build-eval` writes this layout, and
  `scripts/compare.py` and `/claude-api hillclimb` read it.

Before a new runner meets a model, run it once with no model in the loop: call each
stand-in for a write directly and check that nothing real changed. The probe should not be
the first time a stand-in is exercised.

If the team already has a results format they like, keep it and write a small adapter that
emits those rows. `python3 <skill folder>/scripts/compare.py --help` lists the fields it reads.

## Two questions, one eval

Every comparison answers two questions: did the change make things better, and did it
break something. The score, latency and token numbers answer the first. The second only
gets answered where the eval has a task placed to notice the break. The next two sections,
after the baseline, check that it does.

## Run the baseline

1. Ask before spending anything, starting with the probe: which eval you will use, which
   two tasks you will probe, and a yes to those few conversations.
2. **Probe first.** Run the cheapest task and the task you expect to be heaviest as their
   own variant (`probe`), two reps of the cheap one and one of the heavy one. The inventory's
   `context_read` column says which agent reads the most, and its tasks are the heavy ones.
   The probe proves what a full run would otherwise discover twenty tasks in: the credential
   works, the network or sandbox lets the app reach the model, and the model accepts the
   app's requests. If it errors, stop and sort that out with the person. Do not try other
   models or request shapes on your own.

   It also gives the first measured token counts. Run
   `python3 <skill folder>/scripts/estimate.py <flow dir> probe --tasks <n> --reps <r> --heavy <k>`,
   where `k` is how many tasks you expect to be like the heavy one. Then check in. Found:
   the probe worked, and the range the script printed. Recommend: the run size, the likely
   figure, and that it rests on two tasks and your count of heavy ones. Need: a yes to the
   baseline. Give the range, not only the likely figure. A probe of one light task scaled
   up can be several times too low.
3. **Pin the model.** Write the exact model id in `PLAN.md` and use it for every variant.
   A comparison across two models measures the models, not the change.
4. Run the unchanged system as variant `baseline`, with two or three reps per task. One rep
   cannot tell you how much the score moves by chance. Keep a record next to the results
   of how the run was made: model, commit, arguments, start and end time. Results folders
   outlive the session that made them.
5. Record in `PLAN.md`: tasks complete, latency, tokens and model calls per task, the
   noise band (how far the score moved between reps), and the tokens the run used next to
   the estimate you gave. From here on, estimate every run from the baseline
   (`estimate.py <flow dir> baseline --reps <r>`), which covers every task and is far closer
   than the probe.
6. Read every failing task. Decide whether the app failed or the eval is wrong. Fix eval
   bugs now. Changing the eval later makes earlier numbers useless. A bug in a check is
   yours to fix. An expected outcome is not: if you think one is wrong, list it at the
   check-in after the baseline with what the system did instead, and let the person decide.
   Otherwise the eval drifts toward whatever the system does today, bugs included.

## Check the chains

Every change in this plan alters how agents hand work to each other, and the usual way it
goes wrong is a dropped handoff: the second agent never gets what the first one found.
The eval only catches that on a chain it has a task for. So before any change, check that
it has one for every chain production uses:

```bash
python3 <skill folder>/scripts/chain_coverage.py <traces file> .claude/hillclimb/<flow> baseline --exclude <router>
```

It lists each set of agents that run together in production, the tasks that ran that
whole set in the baseline, and whether they pass. Then, for every chain of two or more
agents, open its tasks and check what they grade:

- **the end of the chain**: the change in the systems (the action log, the record written),
  or for a read-only chain the fact the customer needed
- **each fact that had to survive a handoff**: the id, date or amount one agent found and
  the next one needed. Name them from a production trace of that chain

A task that only checks wording, or only the first agent's part, does not cover the
chain. Neither does a task that fails today, until you have written down what it fails on.

## Check what else could break

A dropped handoff is the commonest break. These are the others worth expecting. For each,
find the tasks that would notice, and write the answer in the "Break map" table in
`PLAN.md`: the tasks, or "none".

| What breaks | After which change | The task that notices, and what it grades |
| --- | --- | --- |
| **Lost rule.** A hard limit or a "never say" rule in a subagent's prompt gets weaker when it moves | Any, folds most | A request the rule forbids, graded on the write not happening or the thing not being said. One per rule. A rule moved into a tool also gets a direct call with no model |
| **Shortcut.** The main agent answers from a tool it now holds, where a specialist used to gather more | Fold, merge | A plain task in each neighbouring domain, graded on a fact only the full lookup supplies. Grade the fact, not the lookup. Two reps or more, since it tends to show in one |
| **Wrong pick.** With fewer routes, the main agent reaches for the wrong skill or tool, or none | Fold, as-tool | One plain task per domain, and a few asks worded loosely enough to belong to two, graded on the outcome |
| **Unwanted write.** The main agent can now change things only a specialist could | Fold, merge | Every task lists the writes it expects, and the grader fails any other write. `compare.py` also lists tasks whose writes changed |
| **Lost thread.** A specialist carried a conversation over several turns | Fold, merge | A multi-turn task in each domain that takes more than one turn, graded at the end |
| **Unhappy path.** The subagent's prompt said what to do with a missing id, an unknown record or a tool error | Any | A task with the fact missing or wrong, graded on asking or saying so, and on no write |
| **Cost creep.** The main agent's context fills with what a subagent kept to itself, or its prompt and tool list grow | Any | No task. Watch input tokens per task and the by-agent table in `compare.py` |
| **Route drift.** An edit to the main agent's prompt or tools sends unrelated tasks through an extra agent | Any | No task. Read "Paths that changed" in `compare.py` |

Only rows that apply need a task: no multi-turn domain, no lost-thread task. Do not grade
the path (which agent or tool ran) to close a gap. It breaks at the next change.

For each chain with no task, each break with no task, or a task that does not grade the end, write one (or have
`/claude-api build-eval` extend the set) and list it in `PLAN.md`. Do not add them yet.
They go in the check-in below, and once the person agrees, run them on the unchanged
system so they have a baseline row before anything changes. If there is no trace export,
take the chains from the router's rules and the prompts that mention other agents, and
say they are inferred.

## Check in

Check in, using the layout in `SKILL.md`. Found: the score, latency, model calls and tokens
per task, the tokens the run used against the estimate, each failing task with its
cause from the trace in one line, and every chain or break the eval does not cover, with
the task you would add for it. Put the ones the next change touches first. Recommend: the
first change from the worklist and why that one, what the baseline says about it (for
example, which failing task it should fix), and the token estimate for each eval run that
change needs, so one answer covers the change and those runs. If chains are uncovered, the recommendation is to add those tasks and
run them on the unchanged system first, with their estimate. Need: one question.
Without gaps, "Make that change, on this eval? yes / the eval is missing something". With
gaps, "Add these tasks first? add / go ahead without".

Do not start changing the system until they answer. Then tick "Main eval agreed and
baseline measured" in the plan's status list.
