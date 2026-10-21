# Step 0: Audit

Find every agent, write down what it is, and give each one a verdict. Nothing changes in
the code during this step.

## Find the agents

A subagent, for this purpose, is anything with its own system prompt and its own model
loop or context that another agent or a router calls. Look for:

- prompt files and prompt strings, and the code that sends them
- agent classes, graph nodes, handoff or delegate tools, "agents as tools"
- agents exposed to the main agent through MCP

Also find what sits in front of them: the router, orchestrator, intent classifier or
planner. It gets a row too, with the verdict `main`, because it is what becomes the single
loop. Its prompt is usually the longest in the system and holds the rules every team added.

Last, note the glue: the code that decides which agent runs, passes context between
agents, and stitches their answers together. Most of it goes away as subagents fold.

## Fill in the inventory

Copy `templates/inventory.tsv` (in this skill's folder) to `single-loop/inventory.tsv` in
the repo and add one row per agent. Keep each cell on one line and separate items with
semicolons. The inventory is the backing record. The person reads the plan, not this file.

| Column | What to write |
| --- | --- |
| `agent` | Its name in the code |
| `owner` | Team or person, from CODEOWNERS, comments, tags in prompts or git history. Add "(inferred)" when it is a guess. `unknown` is allowed |
| `prompt` | Path, and rough size in tokens (characters divided by four is close enough) |
| `tools` | How many, and their names |
| `invoked_by` | `handoff` (it takes over the conversation), `tool_call` (it returns to the caller), `pipeline` (fixed position in a sequence) or `entry` (the router or main agent) |
| `returns` | `free_text` or `structured` |
| `talks_to_user` | `yes` only if its words reach the user without another agent rewriting them |
| `context_read` | Rough input tokens per call. Use the traces if they record tokens. Otherwise estimate from the size of what its tools return |
| `traffic` | Share of traces it appears in. Write "inferred" if there are no traces |
| `chains_with` | Agents it runs right before or after |
| `evals` | Path of any eval that covers it, with task ids or tags if one file covers several agents |
| `verdict` | One of the verdicts below |
| `evidence` | File and line, or trace numbers, behind the verdict |
| `confidence` | `high`: the code and the traces both show it. `medium`: only one of them does, or traffic is inferred. `low`: a guess the owner has to confirm |

## Use traces if there are any

Look in the repo for an export of production traces or logs first, then ask the person
whether one can be pulled. It needs one line per subagent call with a trace id, a
timestamp and the agent name. With one in hand, run the script that sits next to this
skill's `SKILL.md`:

```bash
python3 <skill folder>/scripts/coupling_map.py traces.jsonl
```

It reports volume, time share, the most common sequences and which pairs run back to
back. Add `--exclude <name>` only if the router itself appears as an agent in the file.

If there are no traces, work out the chains from the code (one agent's output is another's
required input) and mark the traffic columns as inferred.

## Give each agent a verdict

| Verdict | Use it when |
| --- | --- |
| `main` | The router or orchestrator. It becomes the single loop. |
| `fold` | The default. The subagent is a prompt (procedure, domain knowledge) plus some API calls, and nothing about its work needs a separate context. It becomes a skill, tools, or both, in the main agent. |
| `merge:<other>` | Two subagents chain on each other's output, read the same data, or run together in most traces. Both rows get this verdict, each naming the other. |
| `as-tool` | It should keep its own context, and its job fits one bounded call. The main agent calls it like any other tool, gets a structured result, and keeps the conversation. |
| `keep` | It has to hold the conversation with the user itself, or it belongs to another company and cannot be changed. The full handoff stays. This is rare. |

**When a subagent has earned its own context.** One of these has to be true. Check each
one and write the number or the line that shows it.

1. **Context.** It reads far more than the main agent needs afterwards: logs, long
   documents, big search results. As a rough guide, tens of thousands of tokens per call
   qualifies, and a few thousand does not. Before you settle on this, ask whether the tool
   could simply return less (filter, search, paginate). If it could, the better plan is
   often `fold` with a better tool. Put that to the owner as an open question.
2. **Parallel or independent work.** Several fresh contexts explore separately for
   thoroughness, or one checks another's work without seeing how it was produced.
3. **Tool overload or conflict that skills cannot fix.** The main agent measurably picks
   the wrong tools with everything loaded, or the instructions truly contradict each other.

**What does not earn a separate context:**

- A different team inside the company owns it. Ownership moves to the skill and its eval.
- It has its own persona or voice. One agent should have one voice.
- Its prompt is long. A skill's body is only loaded when it is needed.
- It has many tools. Tool search loads tool definitions on demand.
- Its steps are fixed. Fixed steps are a workflow, which is plain code. Give it `fold`: the
  fixed part goes inside a tool, and whatever still needs judgment (choosing, explaining)
  goes in a skill.

**`as-tool` or `keep`.** If the subagent can do its job from one brief and hand back a
result, it is `as-tool`. That holds even if it is already reached through a tool call
today: the verdict means it stays, with a structured result and no voice of its own. Only
a subagent that must exchange several messages with the user itself, or that an outside
party controls (another company, a contract, a regulator), is `keep`.

**Merges.** A merge is cheap and fairly safe because the main agent changes least: one entry in its list instead of two. It removes
a handoff and the summary lost in it. Rank a merge pair by the busier of the two. Write
the verdict you expect for the merged agent, usually `fold`, in the worklist. If both
subagents are thin, the plan can fold the pair in one change instead of merging first.
Say which you propose and why.

## Read the prompts while you are there

For each prompt, the router's included, note what the fold step will need. These go in the
"Prompt notes" section of the plan.

- rules that are really hard limits (they belong in a tool, where they can be enforced)
- persona and tone instructions (the main prompt owns voice)
- instructions about other agents ("ask the router to call X first")
- rules different teams added to the router prompt, and any that contradict each other

## Write the plan

Copy `templates/PLAN.md` to `single-loop/PLAN.md` and fill in every section except
"Evals", which step 1 fills in, and "Changes", which fills in as each change is made:

- **Verdicts**: one line per agent with the reason and the evidence.
- **Glue**: the code that goes away as subagents fold.
- **Prompt notes**: from the section above.
- **Worklist**: checkboxes, in this order: merges, then folds, then as-tool changes.
  Inside each group, highest traffic first. With no traffic data, lowest risk first:
  fewest tools that change something, best eval coverage. The first fold also turns the
  router into the main agent (it may now answer and call tools itself). That is part of
  the same change.
- **Open questions for owners**: conflicting rules, unclear ownership, tools that could
  return less.
- **Left as it is, and why**: the `keep` rows.

## Check in

Check in, using the layout in `SKILL.md`. Found: the verdict table, one line per subagent
with the single strongest piece of evidence, and the verdicts you are least sure of.
Recommend: the order you would work the plan in, and why. Also under Found: how many
questions only an owner can answer are open, and that they are in `PLAN.md`. Need: "Are
these verdicts right?"

Do not build on a verdict the person has not seen. When they agree, tick "Verdicts agreed"
in the plan's status list.
