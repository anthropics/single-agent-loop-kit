# Step 3: Fold a subagent into the main agent

Use this for a row whose verdict is `fold`. The subagent's knowledge becomes a skill, its
API calls become tools the main agent calls directly, and its route goes away.

Do one subagent at a time.

The first fold also turns the router into the main agent: it may now answer the user and
call tools itself, so its "never answer, always delegate" rules go. That is part of the
same change and the same eval run.

## Before you change anything

Run `python3 <skill folder>/scripts/chain_coverage.py <traces file> .claude/hillclimb/<flow> baseline --exclude <router> --agent <name>`
for the subagent you are folding, and for any subagent that shares a tool with it. Every chain it lists needs a baseline task that runs the
whole chain and grades its end, as step 1 describes. Then read the "Break map" in `PLAN.md`
for the rows this kind of change can cause. If a chain or a break this change touches has
no task, stop and say so. A chain needs its task before the change. A gap in the break map
is the person's call, as "No change without a task on its chains" in `SKILL.md` says. A
change measured on an eval that cannot see its chains has not been measured.

## Sort the subagent's prompt

Go through the prompt line by line. Each line goes to one of five places.

| What the line is | Where it goes |
| --- | --- |
| Procedure and domain knowledge: how to do the job, what order, what to watch for | The skill body |
| A hard limit: "never do X unless Y", policy checks, approval rules | Into the tool, where it is enforced. The skill can still explain the rule so the agent can explain an outcome |
| Facts and reference material: policies, definitions, specs | A reference file inside the skill, or a lookup tool if it is large or changes often |
| Persona, tone, greetings | Deleted. The main system prompt owns the voice |
| Instructions written for an older model: shouting, "think step by step", reminders to use tools | Deleted |

If nothing is left for the skill body, there is no skill. A thin subagent often turns into
tools alone, and that is a good result.

## Write the skill

Start from `templates/skill-template.md`. `/skill-creator` can draft and check it.

The description is the only part the agent sees before it decides to load the skill, so it
carries the most weight:

- Say what the skill covers and when to load it, in the words a user would use.
- Keep it to a sentence or two.
- Make it distinct from every other skill's description. Two skills that sound alike will
  be picked at random.

Write the body the way you would brief a capable colleague: the goal, the steps that are
not obvious, and the reason behind each rule. Leave out what the model would do anyway.

## Build the tools

Start from `templates/tool_spec.md` for each one.

- **Group by what the user wants, not by API.** If the subagent always called three
  endpoints in a row, that is one tool.
- **Put preconditions inside the tool.** If B needs A's result, B checks for it and
  returns a message the agent can act on ("No return was created. The order was delivered
  52 days ago and the window is 30 days.") instead of relying on the agent to remember the
  order of operations.
- **Return raw results.** The main agent should see the data, not another model's summary
  of it.
- **Mark the tools that change something**, so the harness can put an approval step in
  front of them.
- **Reuse.** If another subagent already wraps the same API, the main agent needs it once.
- **Only run what you declared.** The code that executes the main agent's tool calls
  should accept the tools it was given and nothing else. Do not pass an arbitrary tool
  name through to a shared backend.
- **Prove a moved rule with a direct call.** When a rule moves from the prompt into a
  tool, call the tool yourself with a case that breaks the rule and check it refuses. Make
  that a unit test. The eval cannot show this: a task that passes because the model never
  tried the forbidden action says nothing about what the tool would have done.

## Wire it into the main agent

1. Give the main agent the new tools.
2. Put the skill where the main agent loads skills from. If the harness has no way to load
   skills on demand, add one: list each skill's name and description in the system prompt
   and give the agent a `load_skill` tool that returns the body.
   `templates/skill_loader.py` shows this in about forty lines.
3. Remove the subagent's route from the router, and delete the router rules about it. The
   system prompt should get shorter in this step. If you find yourself adding to it, that
   content probably belongs in the skill.
4. If the main agent now carries more than about 30 to 50 tool definitions, defer the less
   common ones behind tool search so they are loaded on demand.
5. Keep the subagent's code and prompt in the repo, unused, until the person says keep.
   Its route is already gone from the router (item 3), so the variant you score is the
   system you would keep.

## Measure

1. Run the eval as the next variant and write `change.md` in the variant directory (first
   line: what changed).
2. Compare with the last variant that was kept:

   ```bash
   python3 <skill folder>/scripts/compare.py .claude/hillclimb/<flow> <last kept variant> <this variant>
   ```

3. **Read the chain tasks.** For every task that runs this subagent's work together with
   another agent's, open the trace even if it passed. Check that what one side found (the
   id, the date, the eligibility result) was actually used by the other. A fold removes one
   handoff and can leave the ones around it worse.
4. **Read the neighbours' tasks, not only this domain's.** A fold gives the main agent
   tools that subagents still in place may also start from. With a lookup in hand, the
   main agent can answer a neighbouring question itself, from less than the subagent would
   have gathered, and stop delegating. Open the traces of tasks in domains that share a
   tool with this one even if they passed, of any task that got worse, and of any task
   listed under "Paths that changed" in the comparison. One rep failing
   out of several is how this showed up in the kit's own example run. The fixes are to say in the tool description what the tool does not
   cover, or to fold or merge the neighbour next. Do it as its own variant.
5. **Check the skill is doing something.** Run the tasks that touch this domain once more
   with the skill removed and the tools left in, as its own variant with the same reps. If
   the score is the same, the model does not need the skill.
   This check is a paid run, so include it when you first say how big the fold is, and use
   a switch that hides the skill (`templates/skill_loader.py` has one) so the check needs
   no code change. If the skill turns out not to be needed, recommend deleting it and
   keeping the tools. Taking a skill out changes the prompt every task sees, so the system
   you would then keep is the one without it, and only its own domain's tasks have been
   run that way. Running the whole eval without the skill is a further paid run that no
   earlier yes covers: put it to the person at the check-in, with its estimate.
6. If the subagent had its own eval, point it at the main agent and keep it next to the
   skill. It is now the skill's eval, and the owning team keeps running it.

## Decide

This section is what you recommend at the check-in. The person makes the call.

- **Holds:** recommend keeping it. Once the person agrees, delete the subagent and its
  prompt. Its route left the router when you wired the fold in, so this removes code no
  model could reach and needs no new run.
- **Unclear:** worse by a single rep on a task the fold should not touch, with no cause in
  the trace. Recommend more reps, as "When a result is unclear" in `SKILL.md` describes.
- **Close, or worse on a few tasks:** read those traces. The usual causes are a skill
  description that does not trigger, a rule that was dropped, a tool that returns too
  little, or the main agent answering a neighbour's question with a tool it just gained.
  `/claude-api hillclimb` can iterate on the skill and tool descriptions against the eval.
  Recommend the fix, and if the person agrees, make it and rerun as the next variant.
- **Still worse:** recommend reverting, keeping the subagent, and changing its verdict to
  `as-tool`. Write
  down which tasks it lost on. That is useful to whoever tries again after a model upgrade.

## Check in

Check in, using the layout in `SKILL.md`. Found: the comparison table and the with and without skill result, every
task that changed with its cause from the trace, and anything you skipped. Recommend: keep,
fix or revert, or more reps when the result is unclear, with the reason, and the next item
on the worklist with its token estimate from the baseline (`estimate.py`, shown next to
what this run used). Also under Found: any task whose route changed, and what you edited
in the main agent's prompt. Need: one question, "Keep it and go on to <next item>? keep
and go on / keep and stop / fix / revert".

The person decides. Then tick the item in `PLAN.md` with the numbers and their decision.
