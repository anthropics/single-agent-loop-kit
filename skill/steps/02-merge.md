# Step 2: Merge two subagents

Use this for a row whose verdict is `merge:<other>`: two subagents that chain on each
other's output, read the same data, or run together in most traces. Merging removes a
handoff, and with it the summary that gets lost in the handoff.

Do one pair at a time.

## Before you change anything

Run `python3 <skill folder>/scripts/chain_coverage.py <traces file> .claude/hillclimb/<flow> baseline --exclude <router> --agent <name>`
for both agents in the pair. Every chain it lists needs a baseline task that runs the
whole chain and grades its end, as step 1 describes. Then read the "Break map" in `PLAN.md`
for the rows this kind of change can cause. If a chain or a break this change touches has
no task, stop and say so. A chain needs its task before the change. A gap in the break map
is the person's call, as "No change without a task on its chains" in `SKILL.md` says. A
change measured on an eval that cannot see its chains has not been measured.

## Make the change

1. **Read both prompts and tool lists side by side.**
2. **Write one prompt.** Keep the procedure and domain knowledge from both. Delete the
   instructions about each other ("you need a tracking id, ask the router to call orders
   first"), since one agent now does both jobs. Where the two prompts contradict each
   other, do not pick a side silently. List the conflict in `PLAN.md` for the owners.
3. **Combine the tools.** Remove duplicate wrappers around the same API. If one tool's
   output is always the other's input, write one tool that does both lookups and returns
   both results. Group tools by what the user wants, not by API.
4. **Update the router.** One entry instead of two. Delete the rules about calling one
   before the other.
5. **Keep the old pair's code and prompts in the repo, out of the router's sight,** until
   the person says keep. The variant you score offers only the merged agent.

If both subagents are thin and the merged agent would obviously be folded next, you can
fold the pair straight into the main agent with step 3 instead. That still counts as one
change with one eval run.

## Measure

1. Run the eval as the next variant.
2. Write `change.md` in the variant directory. The first line says what changed, in one
   sentence. The rest says why.
3. Compare with the last variant that was kept:

   ```bash
   python3 <skill folder>/scripts/compare.py .claude/hillclimb/<flow> <last kept variant> <this variant>
   ```

4. **Read the chain tasks.** For every task that runs both agents of the pair, open the
   trace even if it passed, and check that what the first half found (the id, the date)
   was actually used by the second half. A merge that passes by luck shows up here.
5. **Read the neighbours' tasks.** The merged agent holds both tool sets. Check that tasks
   which used to need only one of the pair did not get slower or start making calls they
   do not need, and that agents which ran before or after the pair still get what they
   were given before. "Paths that changed" in the comparison lists tasks whose route moved.
6. **Prove any rule you moved.** If a hard limit from either prompt went into a tool, call
   the tool directly with a case that must be refused, and keep that as a unit test.

## Decide

This section is what you recommend at the check-in. The person makes the call.

- **Holds:** recommend keeping it. Once kept, delete the old pair's code and prompts, add
  a row for the merged agent to the inventory and give it its own verdict.
- **Unclear:** worse by a single rep on a task the merge should not touch, with no cause
  in the trace. Recommend more reps, as "When a result is unclear" in `SKILL.md` describes.
- **Worse:** read the traces of the tasks that got worse before changing anything. The
  usual causes are a rule lost in the merged prompt, or a tool description that no longer
  says when to use it. Recommend the fix, and if the person agrees, make it and rerun as
  the next variant. A fix is a change like any other: its own variant, its own comparison.
- **Still worse after a fix:** recommend reverting, and note what you learned in `PLAN.md`.

## Check in

Check in, using the layout in `SKILL.md`. Found: the comparison table, every
task that changed with its cause from the trace, and anything you skipped. Recommend: keep,
fix or revert, or more reps when the result is unclear, with the reason, and the next item
on the worklist with its token estimate from the baseline (`estimate.py`, shown next to
what this run used). Also under Found: any task whose route changed, and what you edited
in the main agent's prompt. Need: one question, "Keep it and go on to <next item>? keep
and go on / keep and stop / fix / revert".

The person decides. Then tick the item in `PLAN.md` with the numbers and their decision.
