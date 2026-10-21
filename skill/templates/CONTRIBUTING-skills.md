# Contributing skills and tools to the agent

One agent, many teams. This file says who owns what and what has to be true before
something new ships. Adapt the names and paths to your repo.

## Who owns what

| Thing | Owner |
| --- | --- |
| The system prompt | The central agent team. Nobody else edits it |
| The shared end-to-end eval | The central agent team |
| Review of new skills, tools and evals | The central agent team |
| Each skill and its eval | The domain team, with one named person responsible |
| Each tool | The team that owns the API behind it |

Keep the central team small. Its job is end-to-end quality, not writing every skill.

## Shipping a skill

A skill is ready for review when all of these are true:

- [ ] It has a named owner.
- [ ] Its name is not taken. Two skills with one name must fail to load, not replace each other.
- [ ] The description says what it covers and when to load it, in one or two sentences.
- [ ] The description does not overlap with any existing skill. Read the others first.
- [ ] Hard limits are enforced in tools, not only written in the skill.
- [ ] It ships with its own eval, in the same folder or linked from it.
- [ ] It was tested with and without the skill, and the score is better with it.
- [ ] The shared end-to-end eval was run and did not get worse.
- [ ] It adds nothing to the system prompt.

## Shipping a tool

- [ ] It does one thing a user wants, not one thing an API offers.
- [ ] Preconditions are checked inside the tool, and the failure message tells the agent
      what to do next.
- [ ] It returns raw data.
- [ ] Tools that change something are marked, so they go through approval.
- [ ] Its description says when to use it, and does not overlap with another tool's.

## Asking for a system prompt change

Open a request with the failing eval task that motivates it. The central team will first
try to fix it with a skill, a tool result or a deletion. New sentences in the system prompt
are the last resort.

## Retiring things

- At every model upgrade, each owner reruns the with and without test for their skills and
  deletes the ones that no longer help.
- Skills nobody has loaded in a quarter get deleted. `/skill-doctor` shows usage.
