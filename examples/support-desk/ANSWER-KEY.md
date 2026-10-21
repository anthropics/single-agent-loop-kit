# Answer key

Read this after you have run the audit, not before. The example was built with a known
right answer for each subagent, so you can check that the audit lands where it should.

| Subagent | Planted verdict | The evidence that was planted |
| --- | --- | --- |
| `orders` + `shipping` | `merge` (then fold) | Shipping cannot work without the tracking id that orders returns (`app/prompts/shipping.md`). In the traces, shipping runs right after orders every time it runs: 96 of 200 traces, coupling 100%. Both prompts are a few lines with almost no procedure. |
| `returns` | `fold` | A four-step procedure plus a policy over three API calls. Its hard limits (30 days, final sale) are only prompt text; `Backend.create_return` does not enforce them. It reads little. Its persona ("Remy, the cheerful Returns Concierge") clashes with the brand voice. |
| `account` | `fold` | A three-line prompt over three API calls. No procedure worth a skill, so it should become tools alone. Its one rule, never print the full address, is a hard limit that belongs in the tool. |
| `diagnostics` | `as-tool` | It downloads a 900-line device log (about 50 KB) on every call. The traces show about 30,000 input tokens per call, against 1,000 to 3,000 for the other subagents, and nothing else needs the log afterwards. The job fits one bounded call: serial number in, fault and fix out. |
| `claims` | `keep` | It is run by the insurer, not by Tamberwick (`app/subagents.py`, `app/prompts/claims.md`), and the claim record has to be the customer's own conversation with it. It talks to the customer over several turns. |

Other things the audit should notice:

- **The router prompt is a Frankenprompt.** Teams added rules that contradict each other:
  the orders team says call orders before shipping, the shipping team says route delivery
  questions to shipping first. The returns team's rule sends a mixed request to returns
  even when it also needs something else.
- **Three teams wrap `get_order`** (`app/tools.py`).
- **The tools trust whatever customer or order id the model passes.** Nothing ties a
  conversation to the customer who is signed in, so `account` reads and changes any account
  named in the chat, and any order number works for anyone. Like the return policy, this is
  a hard limit that sits with the model and belongs in the harness. `single_loop/` takes the
  customer from the session, gives no tool a customer id to fill in, and checks every order,
  tracking id and serial number against that customer (`single_loop/customer.py`).
- **Nothing asks before a write.** `single_loop/` puts every write, including the claims
  specialist's, through one write gate. The eval allows them all, because it has no
  customer to ask.
- **There are two evals.** `evals/golden.jsonl` grades task completion end to end and
  should be reused as the main metric. `evals/routing_accuracy.jsonl` grades which
  subagent was picked first, which stops meaning anything once subagents fold.
- **Seven tasks are there to notice breaks, not to cover a domain.** They are tagged
  `break-check`, and a good break map for this example finds them:

  | Task | The break it would notice | What it grades |
  | --- | --- | --- |
  | t13 | Dropped handoff on the `account` then `returns` chain (6 of 200 traces) | Both writes happened: the new address and the return |
  | t14 | Lost rule: "never reveal a full address" | The street address is not in the reply, and nothing was written |
  | t15 | Wrong pick: a broken kettle the customer wants to send back, worded like a device problem | A return was created, and no claim or other write |
  | t16 | Unhappy path: a device problem with no serial number | The reply asks for an identifier and does not name an error code |
  | t17 | Lost thread: a return that takes two turns | The return exists at the end |
  | t18 | Lost thread: a device problem where the serial number arrives on the second turn | The right fault and fix, as in t09 |
  | t19 | Unhappy path: a serial number that does not exist | The reply says it cannot find the device or asks to check the serial, and names no error code |

  All seven fail on any write the task did not ask for, which is the check for an unwanted
  write. The shortcut break is covered by t01 to t03, which grade the date and status.
  Still thin: no unknown order number, and only one loosely worded ask.
- **Tasks t11 and t12 cross two domains.** These are where a router that passes summaries
  between specialists is most likely to drop something.

A reasonable worklist: merge orders and shipping, fold returns, fold account, call
diagnostics as a tool, leave claims.

One verdict has a fair alternative. If `fetch_device_logs` returned only the ERR lines, the
big read would disappear and `diagnostics` would be a `fold`. An audit that raises that as
an open question has done well. The example keeps it `as-tool` so that path is covered too.

`single_loop/` is one end state that follows this key. Yours can differ and still be right
if the eval holds.
