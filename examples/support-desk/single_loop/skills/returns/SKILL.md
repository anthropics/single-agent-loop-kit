---
name: returns
description: Return policy and how to start a return. Load when a customer wants to return or send back an item, or asks whether they can.
---

# Returns

Start a return with `start_return`. The tool checks the policy itself and refuses when an
order does not qualify, so there is no separate eligibility step.

The policy, so you can explain an outcome:

- Items can be returned within 30 days of delivery.
- Final sale items cannot be returned.
- An order that has not been delivered cannot be returned yet.

There are no exceptions. If a customer asks for one, say plainly that you can't and which
rule applies.

Pick the closest reason from what the customer already said: `too_small`, `too_large`,
`changed_mind`, `defective`, `other`. Only ask when they gave no hint.

When a return depends on something else, such as "send it back if my other order is late",
settle that question first with the right tool, then act on the answer.

Once the return exists, give the customer the RMA id and the label link.
