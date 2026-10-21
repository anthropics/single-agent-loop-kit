# Working in this repo

This is the single agent loop kit: a Claude Code skill (`skill/`), four scripts, a reference
loop, and a runnable example. `README.md` has the map.

## If the person wants to try the kit

Follow `examples/support-desk/RUNBOOK.md`. During the audit, do not open
`examples/support-desk/ANSWER-KEY.md`, `examples/support-desk/single_loop/` or
`examples/support-desk/example-run/`. They give
away the verdicts the audit is supposed to reach from the code and traces.

## If the person wants to use it on their own system

The skill belongs in their agent repo, not here. Point them at "Use it on your own system"
in `README.md`.

## Rules for changes to the kit

- Run `python3 -m unittest discover tests` before saying a change works.
- No model ids and no prices in code or docs. The model comes from `KIT_MODEL`, and prices
  are arguments to `compare.py`. The one exception is a record of a run (an example's
  results and its write-up), which names the public model id the numbers came from.
- Anything that calls a real model spends money. Say how big the run is and get a yes first.
  `KIT_MODEL=fake` runs the example offline for plumbing checks. Its scores mean nothing.
- Say what was actually run. A new live run goes in `examples/support-desk/example-run/`
  with its results as they came out, including the bad ones. Keep "What has run on a real
  model" in `README.md` true, and say in the pull request when a change was only checked
  offline.
- The scripts in `skill/scripts/` stay dependency-free, since the skill gets copied into
  other repos on its own.
