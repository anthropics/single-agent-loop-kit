# Tool: `verb_noun`

Fill this in before writing the code. One tool per thing the user wants done, not one per API.

**What the user wants when this gets called:**

**Description the agent sees** (what it does and when to use it, one or two sentences).
Do not use a real id as an example here or in the inputs. The agent can quote it to a
user. Describe the format instead:

**Inputs:**

| Name | Type | Notes |
| --- | --- | --- |
|  |  |  |

**APIs it wraps** (in call order):

**Preconditions checked inside the tool**, and the message returned when one fails. Write
the message so the agent can act on it or explain it to the user:

| Check | Message returned |
| --- | --- |
|  |  |

**Returns:** the raw data the agent needs, not a summary.

**Changes something?** yes / no. If yes, it goes behind the harness's approval step.

**Replaces:** which subagent tools or prompt rules this makes unnecessary.
