# Step 4: Keep a subagent, called as a tool

Use this for a row whose verdict is `as-tool`, and for any subagent that lost its fold
comparison. The subagent keeps its own context. What changes is how it is reached: the
main agent calls it like any other tool, gets a structured result back, and stays in
charge of the conversation.

This needs no rewrite of the subagent, which makes it a safe early step.

## Before you change anything

Run `python3 <skill folder>/scripts/chain_coverage.py <traces file> .claude/hillclimb/<flow> baseline --exclude <router> --agent <name>`
for the subagent. Every chain it lists needs a baseline task that runs the
whole chain and grades its end, as step 1 describes. Then read the "Break map" in `PLAN.md`
for the rows this kind of change can cause. If a chain or a break this change touches has
no task, stop and say so. A chain needs its task before the change. A gap in the break map
is the person's call, as "No change without a task on its chains" in `SKILL.md` says. A
change measured on an eval that cannot see its chains has not been measured.

## Make the change

1. **Replace the handoff with a tool.** Name it for what it does (`diagnose_device`, not
   `call_diagnostics_agent`) and describe when to use it. Fill in `templates/tool_spec.md`
   for it first. Its "Returns" is the one exception to that template: this tool hands back
   the response shape of item 3, a conclusion with its evidence, not raw data. The tool runs the subagent in a fresh context with one brief and returns
   when the subagent is done. Do not put a real id in the description or the schema as an
   example. The main agent can quote it to a user. Describe the format, or use an id that
   cannot exist.
2. **Edit the main agent's prompt and targets, and keep the edit small.** Take the
   subagent out of the list of agents the main agent can hand off to, and out of every
   rule that names it, so the tool is the only way to reach it in the variant you score.
   Add at most a sentence on when to call the tool. The description on the tool should do
   most of that work. This is the one part of the change every task shares, so list each
   line you touched in `change.md`. If the main agent is still a router that is told
   never to answer the user itself, because no fold has happened yet, a required field can
   force it to ask the user for something. Allow exactly that, in one sentence, and say
   so in `change.md`.
3. **Give every such subagent the same response shape.** Use
   `templates/subagent_response.schema.json`: the conclusion, the data it was based on,
   the actions it took, and its confidence or caveats. Events for the UI travel on a
   separate channel, not in this object.
4. **Tell the subagent who it is talking to.** It should be told it is called by another
   agent and never speaks to the user. That text can be added when the tool calls it, from
   one shared file. If the subagent's own prompt gives it a persona, greetings or a way of
   addressing the user, take those lines out, since they contradict it and can end up
   inside the conclusion. Otherwise leave the prompt as its owner wrote it.
5. **Let the main agent check the conclusion** against data it can read cheaply, before it
   repeats the conclusion to the user. If the main agent has no data tools, it has only
   the evidence inside the result to go on. Leave it that way, since giving it a data tool
   is a second change, and list this under what you skipped.
6. **Make the brief a set of required fields.** Whatever the subagent cannot work without
   (the serial number, the order id) is a required parameter of the tool, passed through as
   given. Free text is for the question only. A fact that lives in a free-text brief is a
   fact the main agent can leave out.
7. **Check the result in code.** The tool validates what the subagent returned against the
   schema before handing it to the main agent: every field present, the right types, no
   extras. An empty reply is an error. A reply that does not fit but says something is
   passed on marked low confidence, with a caveat that it was not checked. Do not pass a
   malformed or empty result along as if it were an answer.

For a `keep` row (full handoff), leave the subagent alone. Make sure that when control
comes back, the main agent is told what happened, so the rest of the conversation has that
context.

## Measure

1. Run the eval as the next variant and write `change.md` in the variant directory (first
   line: what changed).
2. Compare with the last variant that was kept:

   ```bash
   python3 <skill folder>/scripts/compare.py .claude/hillclimb/<flow> <last kept variant> <this variant>
   ```

3. **Read what went in and what came out.** For every task that calls the tool, open the
   trace even if it passed. Going in: did the call carry every fact the subagent needed?
   Coming out: did the conclusion, with its caveats, reach the customer's reply unchanged?
   Count the caveats in the result and in the reply. Those are the two handoffs this
   change adds, and a wording check can pass while one of them drops something.
4. **Test the two failure paths directly,** with no model in the loop: a call with a
   required field missing is refused, and a result that does not fit the schema comes back
   flagged. Keep both as unit tests.
5. **Read the neighbours' tasks, not only this subagent's.** Tasks that chain it with
   others (it runs, then another agent uses what it found) are where a structured result
   either helps or loses detail the old free-text summary carried. Then look at tasks that
   never used this subagent: the main agent has a new tool and an edited prompt. It should
   not start calling the tool where it did not delegate before, and "Paths that changed"
   in the comparison shows whether any of them now takes a different route. Look at the
   main agent's input tokens per call too: a longer prompt and one more tool definition
   are paid on every call of every task.
6. **Prove any rule you moved.** Usually none moves here, since the subagent keeps its
   prompt and its tools. If the wrapper tool took on a hard limit (a required approval, a
   cap on what the subagent may change), call the tool directly with a case that must be
   refused, and keep that as a unit test.

## Decide

This section is what you recommend at the check-in. The person makes the call.

- **Holds:** recommend keeping it. Once the person agrees, delete what only the old
  handoff used. Leave anything the new tool or another subagent still runs on.
- **Unclear:** worse by a single rep on a task that never calls the tool, with no cause in
  the trace. Recommend more reps, as "When a result is unclear" in `SKILL.md` describes.
- **Worse:** read the traces first. The usual causes are a tool description that does not
  say when to call it, a required fact left out of the call, or a result the main agent
  repeats without its caveats. Recommend the fix, and if the person agrees, make it and
  rerun as the next variant.
- **Still worse after a fix:** recommend reverting to the handoff and note in `PLAN.md`
  what it lost on.

## What this does not fix

Write these in `PLAN.md` so they are revisited, for example at the next model upgrade:

- The subagent still has its own prompt, its own owner and its own evals.
- Each call still hands back a summary, and summaries lose detail.
- Each call is a nested model loop, which adds latency.
- The structured result is usually larger than the summary it replaces, and the main agent
  reads all of it.

## Check in

Check in, using the layout in `SKILL.md`. Found: the comparison table, every
task that changed with its cause from the trace, and anything you skipped. Recommend: keep,
fix or revert, or more reps when the result is unclear, with the reason, and the next item
on the worklist with its token estimate from the baseline (`estimate.py`, shown next to
what this run used). Also under Found: any task whose route changed, and what you edited
in the main agent's prompt. Need: one question, "Keep it and go on to <next item>? keep
and go on / keep and stop / fix / revert".

The person decides. Then tick the item in `PLAN.md` with the numbers and their decision.
