# Example run: baseline and the first fold

This is a real run of the runbook on this example, kept so you can see what the kit's output
looks like before you spend anything. Read it after your own audit, not before. The plan in
here gives away the verdicts.

Run on 2026-10-08 with `KIT_MODEL=claude-opus-5`, two reps per variant, no harness errors.
The eval had twelve tasks then, t01 to t12, and the run is scored on those
twelve. It has nineteen now. t13 to t19 were added afterwards and were not part of this
run. Claude Code did the work from the runbook prompt without seeing
`ANSWER-KEY.md` or `single_loop/`.

Two edits were made after the run. The made-up retailer had a different name at the time,
and it was swapped for Tamberwick Home throughout, including inside the results, traces and
diff. And the measured results and the findings drawn from them were removed from this
write-up and from `plan/PLAN.md`. Nothing else in the records was changed, and nothing was
rerun. The command under "The comparison" prints the results from the recorded logs.

| Path | What it is |
| --- | --- |
| `plan/PLAN.md` | The plan the audit wrote: a verdict per subagent, the eval and the worklist |
| `plan/inventory.tsv` | One row per subagent with the evidence behind its verdict |
| `results/baseline/` | 24 graded rows and 24 traces for the system as it started |
| `results/v1/` | The same for the returns fold, plus `change.md`, the one-line note of what changed |
| `fold-returns.diff` | The code change behind v1 |
| `as-tool/` | A second run, a day later on seventeen tasks: a fresh baseline and `diagnostics` called as a tool. It has its own `README.md` |

## The comparison

From `examples/support-desk`:

```bash
python3 ../../skill/scripts/compare.py example-run/results baseline v1
```

## What this run does not show

- **Two reps is thin.** One flip moves a task by half. Use three or more when a decision
  rests on a single task.
- **Only one change was made.** The other items on the worklist and `single_loop/` were not
  run. The as-tool change was run later, on its own, and is in `as-tool/`. The audit's verdict for `orders` and `shipping` is a merge, and the plan's worklist
  does it as one fold of the pair straight into the main agent. The plan's default order
  puts that ahead of the returns fold. The runbook
  asks for returns first because it is the smallest change to watch.
- **The eval never tried a return the policy forbids.** The refusal now built into
  `create_return` is proven by the unit test in the diff, not by this run.
- **One chain was not covered.** Production traces include `account` then `returns`, and the
  eval had no task for it. The kit did not check for that when this run was made. It does
  now (`chain_coverage.py`), and t13 was added for it afterwards, along with six more tasks
  that watch for other breaks. To compare a newer run with this one on the same twelve
  tasks, add `--skip-tag break-check` to `compare.py`.
- **The with and without skill check was not finished**, so there is no evidence here on
  whether the returns skill earns its place.
- **The kit has changed since.** The run used the kit as it was on 2026-10-08. The runner now
  also writes a `run.json` beside the results, and `compare.py` prints more. The app part
  of `fold-returns.diff` still applies to the current example. Its test hunk does not,
  because `tests/test_kit.py` has moved on.
