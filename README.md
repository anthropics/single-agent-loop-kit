<!-- Copyright 2026 Anthropic PBC -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Single agent loop kit

A starter kit for moving a multi-agent system (a router or orchestrator in front of
specialist subagents) toward one agent loop that loads skills and tools on demand. It is
the companion to the article
[Building agents: When to fold subagents into your main agent loop](https://claude.com/resources/articles/building-agents-when-to-fold-subagents-into-your-main-agent-loop).

> **Reference implementation. Not maintained and not accepting contributions.**

The kit does not assume a single loop always wins. It measures. Every change is scored on
the same eval before and after, and a subagent only goes away when the numbers say its
replacement holds.

## The idea

1. **Measure.** Find the evals you already have, fill the gaps, and score the system as it
   is today. If you have none, the kit builds one with you.
2. **Combine.** Merge the subagents that always run together.
3. **Fold.** Turn each remaining subagent into a skill and tools in the main agent, one at
   a time, and compare. Keep the ones that earn their own context, and call them as tools.

Then keep it healthy: one small team owns the system prompt and the shared eval, and each
domain team owns its skills.

## Try it in ten minutes

`examples/support-desk` is a small, runnable support agent with a router and six subagents,
built so that each subagent has a known right answer. Follow
[`examples/support-desk/RUNBOOK.md`](examples/support-desk/RUNBOOK.md) to watch Claude Code
audit it, fold one subagent and print the before and after numbers.

Start with the free check. It needs no API key and spends nothing. From wherever you put
the kit (downloaded as a zip, unzip it first):

```bash
cd single-agent-loop-kit/examples/support-desk
KIT_MODEL=fake python3 evals/run_eval.py --variant smoke
```

You should see nineteen lines ending in `19 tasks ran on the offline stand-in model, 0 harness
errors. The plumbing works.` The stand-in follows keyword rules, so that run is not scored.
Scores come from the real run in the runbook.

## Use it on your own system

1. Copy the skill into your agent repo:

   ```bash
   git clone https://github.com/anthropics/single-agent-loop-kit
   cp -r single-agent-loop-kit/skill <your repo>/.claude/skills/single-agent-loop
   ```

2. Open Claude Code in your agent repo and say: `Run the single-agent-loop skill.`
3. It audits first and stops to show you a verdict for each subagent: fold, merge, call as
   a tool, or keep. Correct anything it got wrong.
4. It then works the plan one change at a time. Each change gets its own eval run and a
   comparison, and you decide whether it stays.

It stops at the same points every time: after the audit, before any paid run, after the
baseline, and after each change. Each stop is a short check-in with what it found, what it
recommends and one question for you. Before a paid run, that includes a token estimate.

You do not need an eval to start. If you have none, or none that tests the whole system,
it asks for a safe way to run your system on a test request and for some real requests,
drafts about ten tasks, and has you correct what done means for each before it runs them.

The skill reads whatever orchestration code is in the repo, so it is not tied to a
framework. It keeps its notes in `single-loop/` in your repo.

## What's in the box

| Path | What it is |
| --- | --- |
| [`skill/SKILL.md`](skill/SKILL.md) | The front door. Short, and points at one step file at a time |
| [`skill/steps/00-audit.md`](skill/steps/00-audit.md) | Inventory every subagent and give each a verdict |
| [`skill/steps/01-baseline.md`](skill/steps/01-baseline.md) | Reuse your evals, fill gaps or build one if you have none, score today's system |
| [`skill/steps/02-merge.md`](skill/steps/02-merge.md) | Merge two subagents that always run together |
| [`skill/steps/03-fold.md`](skill/steps/03-fold.md) | Fold a subagent into a skill and tools |
| [`skill/steps/04-as-tool.md`](skill/steps/04-as-tool.md) | Keep a subagent, but call it as a tool with a structured result |
| [`skill/steps/05-upkeep.md`](skill/steps/05-upkeep.md) | Shrink the prompt, prune skills, settle ownership |
| [`skill/scripts/coupling_map.py`](skill/scripts/coupling_map.py) | From a trace export: which subagents carry the traffic and which run together |
| [`skill/scripts/compare.py`](skill/scripts/compare.py) | Two eval runs side by side: task completion, latency, model calls, tokens, cost |
| [`skill/scripts/chain_coverage.py`](skill/scripts/chain_coverage.py) | Checks the eval has a task for every chain of subagents production uses, so a dropped handoff cannot go unseen |
| [`skill/scripts/estimate.py`](skill/scripts/estimate.py) | A token estimate for the next eval run, from one already measured, and the estimate next to the actual afterwards |
| [`skill/templates/`](skill/templates) | Inventory, plan, skill, tool spec, subagent response schema, contribution rules, skill loader |
| [`reference_loop/loop.py`](reference_loop/loop.py) | A small single agent loop to read and copy from: parallel tool batches, skills on demand, tool search, budgets, a write gate, an optional verifier |
| [`examples/support-desk/`](examples/support-desk) | The runnable example, before (`app/`) and after (`single_loop/`) |
| [`examples/support-desk/example-run/`](examples/support-desk/example-run) | What two real runs look like: the plan, a baseline, one fold, one subagent called as a tool, and the comparisons |

## It leans on tools you already have

The steps hand off to these Claude Code commands instead of rebuilding them:

| Command | Used for |
| --- | --- |
| `/claude-api build-eval` | Building or extending the eval in step 1 |
| `/claude-api hillclimb` | Tuning a skill or tool description when a fold comes up short |
| `/claude-api prompt-audit` | Finding instructions written for older models, in step 5 |
| `/claude-api cost-optimize` | Trimming spend once the design has settled |
| `/skill-creator` | Drafting and auditing skills (`/plugin install skill-creator@claude-plugins-official`) |
| `/skill-doctor` | Seeing what each skill costs and how often it is used |

The eval runner in the example writes the same results layout `/claude-api build-eval`
uses, so `/claude-api hillclimb` and its report work on it directly.

## When you don't need this kit

- **You have no subagents yet.** Start with one loop. Read `reference_loop/loop.py` and
  add tools and skills as testing shows you need them.
- **Your subagents earn their context.** Parallel research across fresh contexts,
  independent verification, or work that reads far more than the main agent needs
  afterwards are good reasons to keep a subagent. The audit will tell you so.
- **Your system cannot be scored yet.** Having no eval is fine: the baseline step builds
  one with you. But it needs two things only you can give. A way to run the system on a
  test request outside production, and someone who can say what a correct outcome is for
  the common requests. If either is missing, sort that out first. Without a score, a
  migration is a matter of opinion.

## Cost

The audit reads code and costs what a Claude Code session costs. Eval runs call your model
for every task, rep and version, so the skill asks before every paid run and gives a token
estimate based on runs it has already measured. Start with ten tasks and two or three reps.

## Tests

```bash
python3 -m unittest discover tests
```

They need no API key. They cover the scripts, the reference loop, and an offline run of
both versions of the example.

## What has run on a real model

Two runs of the example, by one person on one model, both recorded as they came out in
[`examples/support-desk/example-run/`](examples/support-desk/example-run): the audit, a
twelve-task baseline and the returns fold, then a seventeen-task baseline and `diagnostics`
called as a tool. Each write-up says what was removed from it after the run and what its
run did not show.

Not run on a real model: the merge and upkeep steps, the finished `single_loop/` version of
the example, tasks t18 and t19, starting from a repo with no eval, and the kit on any
system other than the example. The skill's wording also changed after the second run, and
no session has followed the reworded steps yet.

Changed after both runs and checked offline only:

- The reference loop: a write gate is required when a tool writes, subagent tokens count
  against the budget, a batch of tool calls is capped, and an answer the verifier rejects
  twice is withheld.
- The skill loaders refuse two skills with one name and a skill that links out of the folder.
- The scripts escape names from their input before printing them, and `compare.py` stops on
  a grade that is not a number.
- The example: each task names the customer who is signed in, the runner checks task ids,
  a subagent's write needs a write gate, the router refuses a call it did not declare, and
  `single_loop/` checks who owns a record.

## Support

This project is provided AS IS. Issues and pull requests are not monitored, so we cannot
guarantee fixes for bugs or implementation of feature requests. Fork it and adapt it to
your own system.

## License

Apache-2.0. See [LICENSE](LICENSE).
