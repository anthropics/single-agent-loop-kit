# Example run: a fresh baseline and `diagnostics` called as a tool

A second real run of this example, kept beside the first one. Read it after your own audit,
not before. The plan in here gives away the verdicts.

Run on 2026-10-09 with `KIT_MODEL=claude-opus-5`, no harness errors. The baseline and v1 are
two reps of every task. The two rerun variants are four reps of two tasks.
The eval had seventeen tasks then, t01 to t17, and the run is scored on those
seventeen. It has nineteen now. t18 and t19 came out of this run's own check-in and have
not been run on a real model. Claude Code did the work from the runbook prompt with one
difference: the person asked for a single change, `diagnostics` called as a tool (step 4),
instead of the returns fold. It did not see `ANSWER-KEY.md`, `single_loop/` or the first
example run.

One edit was made after the run: the measured results and the findings drawn from them
were removed from this write-up and from `plan/PLAN.md`. The results, traces, `run.json`
files and diff are as the run left them, and the commands under "The comparison" print the
results from them. On 2026-10-09 all 84 scored rows were
regraded from their traces with the grader as it stood that day, which is stricter about
extra writes than the one the run used, and every grade came out the same.

| Path | What it is |
| --- | --- |
| `plan/PLAN.md` | The plan the session wrote: verdicts, the eval and its gaps, the break map, the baseline run, and the one change under "Item 4" |
| `plan/inventory.tsv` | One row per subagent with the evidence behind its verdict |
| `results/probe/` | The two conversations run before the baseline, which its first token estimate rests on |
| `results/baseline/` | 34 graded rows and 34 traces for the system as it started, and `run.json`, the record of how the run was made |
| `results/v1/` | The same for `diagnostics` as a tool, plus `change.md` |
| `results/baseline-t01-t10/`, `results/v1-t01-t10/` | Four more reps of two tasks on each side, run before the decision |
| `as-tool-diagnostics.diff` | The code change behind v1. It applies to the example as it is now |

## The comparison

From `examples/support-desk`:

```bash
python3 ../../skill/scripts/compare.py example-run/as-tool/results baseline v1
python3 ../../skill/scripts/compare.py example-run/as-tool/results baseline-t01-t10 v1-t01-t10
```

The first compares the two full runs. The second compares the four extra reps of t01 and
t10 described below.

## What happened next

The check-in after the change did not settle on keep, fix or revert. It put forward four
more reps of t01 and t10 on both variants, 16 conversations, as the way to settle it, and
the person chose that. (`plan/PLAN.md` records it as asked for by the person.)

The person kept the change. It stays on its branch, and the worklist's other three items
were not started.

## What this run does not show

- **Two reps was too thin to decide on.** The decision took 16 more conversations, and six
  reps is still a small number.
- **Only one change was made, out of worklist order.** As-tool came before any fold, so the
  router was still a router. Its prompt forbids answering the customer, and the session
  added one sentence so it could ask for a serial number.
- **The old route was already out of the router's sight when v1 was scored.** `diagnostics`
  left the `delegate` list and the router's prompt in the same change. The dispatch code is
  still on the branch and would still run `diagnostics` if asked, so the only thing keeping
  the old route closed is the list the router is shown. The person chose to leave the
  branch exactly as it was scored.
- **Two gaps were known and left open.** At the check-in after the baseline, the session
  found no task where the serial number arrives on a second turn and none for a serial
  number that does not exist. The person went ahead without them. They are t18 and t19 now.
- **The main agent could not check the conclusion against data.** Step 4 asks for that. The
  router has no data tools, so it had only the evidence list inside the result.
- **The offline stand-in could not reach the new tool.** Its router rules only know
  `delegate`, so with the diff applied an offline run still sends the device tasks down
  the old route. The new path was covered offline by the five unit tests in the diff and
  first met a model in the paid run.
