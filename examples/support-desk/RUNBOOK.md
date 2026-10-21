# Runbook: try the kit on Tamberwick Home

Tamberwick Home is a made-up appliance retailer. Its support agent is a router in front of
six specialist subagents, in `app/`. This runbook has Claude Code audit it, fold one
subagent, and show the before and after numbers.

## Before you start

1. Open a terminal in this folder. From wherever you put the kit:

   ```bash
   cd single-agent-loop-kit/examples/support-desk
   ```

2. Check the plumbing with the offline stand-in model. It needs Python 3.10 or newer and
   nothing else: no key, no install, no spend.

   ```bash
   KIT_MODEL=fake python3 evals/run_eval.py --variant smoke
   ```

   It should end with `19 tasks ran on the offline stand-in model, 0 harness errors. The
   plumbing works.` The stand-in follows keyword rules, so that run is not scored.

3. Install the Anthropic SDK in a virtual environment. A bare `pip install` is refused by
   Homebrew's Python and by most recent Linux system Pythons.

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install anthropic
   ```

4. Give the SDK a credential and pick the model:

   ```bash
   export ANTHROPIC_API_KEY=<your key>
   export KIT_MODEL=<the Claude model id you use>
   ```

   Any credential the Anthropic SDK can find works in place of the key.

5. Make this folder a git repository, so the fold can happen on a branch you can throw
   away. Skip this if the kit is already a git checkout.

   ```bash
   git init && git add -A && git commit -m "Starting point"
   ```

6. Make two paid calls before the full run, a light task and a heavy one. They prove the
   credential and the model work, and they give the first real token counts:

   ```bash
   python3 evals/run_eval.py --variant probe --only t08
   python3 evals/run_eval.py --variant probe --only t09
   python3 ../../skill/scripts/estimate.py .claude/hillclimb/support-desk probe --tasks 19 --reps 2 --heavy 3
   ```

   The last line prints a token range for the full baseline, and a likely figure that
   assumes three of the nineteen tasks are as heavy as `t09` (the three that read a device log are).
   It is rough on purpose. After the baseline, estimates come from the baseline itself and
   are much closer.

   One line ending in `pass` or `FAIL` means the model answered. A line with `ERROR` means
   the call did not go through, and the message says why. Sort that out before going on.
   `APIConnectionError` means the request never left your machine: a firewall, a proxy, or
   Claude Code's sandbox is blocking `api.anthropic.com`. If you run Claude Code with
   sandboxing on, allow that host, or the eval runs it launches will fail the same way.

7. Start Claude Code from this same terminal (`claude`), so the eval runs it launches see
   the virtual environment and both variables.

The offline stand-in follows keyword rules written for the app as it ships. It cannot
choose a tool or a route that a change adds, so after a change an offline run only shows
the old paths still work. Unit tests with a scripted model are how to exercise a new path
before paying for a run.

Live runs spend real tokens. One pass over the nineteen tasks is around a hundred model calls.
The three diagnostics tasks that reach the device log are the expensive ones, since the log is 900 lines.

## The run

In Claude Code, paste this:

```text
Use the single-agent-loop skill in ../../skill on this repo.

The system to migrate is in app/. Traces are in traces/traces.jsonl. Do not open
ANSWER-KEY.md, single_loop/ or example-run/ until I tell you to.

Stop at every check-in the skill describes and wait for my answer each time. I will
answer them one at a time.

1. Run step 0, the audit. Check in with the verdicts.
2. Run step 1. Reuse the eval that is already here. I have already run the probe as
   variant `probe` (t08 and t09). Check in with the size of the run and a token estimate
   from it, and once I say yes, run the baseline with
   `python3 evals/run_eval.py --variant baseline --reps 2`. Check in with the result and
   the tokens it used.
3. For the first change, fold the `returns` subagent with step 3, on a new git branch. Run
   it as variant v1 with the same reps, then compare baseline and v1.
4. Check in with the comparison and whether you would keep the fold.
```

### What to expect

Claude Code stops four times and waits for you. Each stop is a short check-in with the same
three parts: what it found, what it recommends and why, and one question for you.

| Stop | What you get | What it asks |
| --- | --- | --- |
| After the audit | A verdict for each subagent with its evidence | Are the verdicts right? |
| Before the paid run | The eval it will use, the number of conversations, and a token estimate with what it is based on | Okay to spend that? |
| After the baseline | The score, the tokens used against the estimate, why each failing task failed, and any chain of subagents the eval has no task for | Does the eval measure what matters, and go ahead with the fold (or add the missing tasks first)? |
| After the fold | Before and after numbers, and every task that changed | Keep it? |

If you carry on past the fold, expect one check-in per change, so four in all for this
example's worklist. Answer each one on its own. Approving two stops in one message means you never read the
first. The estimates count tokens for the eval runs only. They leave out Claude Code's own usage
while it reads and edits, and they are not turned into money, since prices differ by model.

If it runs past a stop, say "stop and give me the check-in for the last step".

When it has finished, open `ANSWER-KEY.md` and check the audit's verdicts against it.
[`example-run/`](example-run/README.md) has the plan, results and traces from one real run
of this prompt, to compare with yours. [`example-run/as-tool/`](example-run/as-tool/README.md)
has a second run, where the one change was `diagnostics` called as a tool.

## See the end state

`single_loop/` is the same support agent after the whole plan: one loop, one skill, eight
tools, one subagent called as a tool, one handoff. Run it against the same eval and compare:

```bash
python3 evals/run_eval.py --variant baseline --reps 2            # skip if you ran it above
python3 evals/run_eval.py --variant single --app single_loop --reps 2
python3 ../../skill/scripts/compare.py .claude/hillclimb/support-desk baseline single
```

Add `--price-in` and `--price-out` (dollars per million tokens for your model) to see cost
per task.

Whatever the comparison prints is the result. If the single loop loses a task, read that
task's trace in `.claude/hillclimb/support-desk/single/traces/` before you draw a conclusion.
