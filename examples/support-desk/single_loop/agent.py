# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""Tamberwick Home support as a single agent loop.

What happened to each of the six subagents in ../app:

  orders + shipping  merged, then folded into one tool, `track_order`. Their prompts held
                     almost no procedure, so there is no skill.
  returns            folded into the `returns` skill plus `start_return`. The 30 day and
                     final sale rules moved out of the prompt and into the tool.
  account            folded into three tools. The "never print the address" rule is now
                     the tool's behaviour: it does not return the address at all.
  diagnostics        kept as a subagent, called as a tool. It reads a device log of tens of
                     thousands of tokens that the main context has no use for afterwards.
  claims             kept, with a full handoff. The insurer owns it and it has to talk to
                     the customer directly.

Two limits the subagents left to the model now sit in the harness. The customer is whoever
is signed in, set when the conversation is built: no tool takes a customer id, and every
order, tracking id and serial number is checked against that customer (customer.py). And
every write, the main agent's and the subagents', goes through one write gate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))   # the kit root, for reference_loop

from reference_loop.loop import Agent, Budget, Tool  # noqa: E402

from app.backend import Backend  # noqa: E402
from app.llm import Meter, get_client, model_name  # noqa: E402
from app.subagents import ClaimsSession, Runtime, allow_all_writes, run_subagent  # noqa: E402

from .customer import CustomerBackend  # noqa: E402

# No real ids as examples: a model can quote an example from a tool description to a customer.
ORDER_ID = {"type": "string", "description": "Four digit order number."}


# The shape in skill/templates/subagent_response.schema.json, checked by hand so the
# example needs no schema library. A test keeps the two in step.
RESPONSE_FIELDS = {"conclusion": str, "evidence": list, "actions_taken": list, "confidence": str, "caveats": list}
CONFIDENCE = ("high", "medium", "low")


def fits_response_shape(result) -> bool:
    return (isinstance(result, dict)
            and set(result) == set(RESPONSE_FIELDS)                      # every field, and no extras
            and all(isinstance(result[k], kind) for k, kind in RESPONSE_FIELDS.items())
            and all(isinstance(item, str) for k in ("evidence", "actions_taken", "caveats") for item in result[k])
            and result["confidence"] in CONFIDENCE
            and bool(result["conclusion"].strip()))


def checked_response(raw: str) -> dict:
    """A subagent's reply as the agreed shape, or a result that says plainly it was not.
    An empty reply is an error, which the loop hands back to the main agent as one."""
    if not raw.strip():
        raise ValueError("The specialist returned nothing.")
    try:
        result = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    except ValueError:
        result = None
    if fits_response_shape(result):
        return result
    return {"conclusion": raw, "evidence": [], "actions_taken": [],
            "confidence": "low", "caveats": ["The specialist did not return the agreed structure. Check before repeating it."]}


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


class Conversation:
    def __init__(self, backend: Backend | None = None, meter: Meter | None = None, client=None, *,
                 customer_id: str | None, approve: Callable[[str, dict], bool]) -> None:
        """customer_id is the signed-in customer, from the session and never from the chat.
        approve is the write gate: it gets a tool's name and arguments and says whether the write may run."""
        if not callable(approve):
            raise ValueError("Pass approve=, the write gate. There is no conversation without one.")
        self.rt = Runtime(CustomerBackend(backend or Backend(), customer_id), meter or Meter(),
                          client or get_client(), approve=approve)
        self.messages: list = []
        self.claims: ClaimsSession | None = None
        self.handoff_summary: str | None = None
        self.note_for_main: str | None = None
        self.agent = Agent(
            system=(HERE / "system.md").read_text(),
            tools=self._tools(),
            skills_dir=HERE / "skills",
            model=model_name(),
            client=self.rt.client,
            budget=Budget(max_turns=12, max_tokens=300_000),
            approve=self._gate(approve),   # the same gate the subagents' writes go through
            on_usage=lambda usage: self.rt.meter.add("main", usage),
        )
        self.rt.on_usage = self.agent.charge   # a subagent's tokens count against the main loop's budget

    @property
    def trace(self) -> list:
        return self.rt.trace

    # ---- tools, grouped by what the customer wants, not by API ----------
    def _tools(self) -> list[Tool]:
        backend = self.rt.backend

        def track_order(args):
            order = backend.get_order(args["order_id"])
            if "error" in order:
                return order
            if not order["tracking_id"]:
                return {"order": order, "shipment": None,
                        "note": "This order has not shipped yet, so there is no ETA to give."}
            return {"order": order, "shipment": backend.get_tracking(order["tracking_id"])}

        def start_return(args):
            verdict = backend.check_return_eligibility(args["order_id"])
            if "error" in verdict:
                return verdict
            if not verdict["eligible"]:
                return {"created": False, "reason": verdict["reason"],
                        "instruction": "No return was created. Tell the customer which rule applies. "
                                       "There are no exceptions."}
            return {"created": True, **backend.create_return(args["order_id"], args["reason"])}

        def get_account(args):
            account = backend.get_account()
            if "shipping_address" in account:   # addresses stay out of replies, whatever format they are stored in
                account["shipping_address"] = "on file, not shown in chat"
            return account

        def update_shipping_address(args):
            result = backend.update_shipping_address(args["address"])
            return {"ok": True} if result.get("ok") else result

        def diagnose_device(args):
            # Subagent as a tool: fresh context in, one structured conclusion out.
            serial = str(args.get("serial") or "").strip()
            if not serial:   # the one fact the specialist cannot work without
                return {"error": "diagnose_device needs the device's serial number. Ask the customer for it."}
            refused = backend.refuse_device(serial)
            if refused:   # not this customer's device, so no specialist runs and no log is read
                return refused
            raw = run_subagent(self.rt, "diagnostics", f"Diagnose the device with serial {serial}.",
                               system=(HERE / "diagnostics_agent.md").read_text())
            return checked_response(raw)

        def handoff_to_claims(args):
            refused = backend.signed_out()
            if refused:   # the insurer's specialist could do nothing for someone who is not signed in
                return refused
            self.handoff_summary = args["summary"]
            return "The claims specialist will take the conversation from the next message."

        tools = [
            Tool("track_order", "Where an order is: item, status, carrier, ETA and last scan, in one call.",
                 _schema({"order_id": ORDER_ID}, ["order_id"]), track_order),
            Tool("list_orders", "List the customer's orders when they don't give an order number.",
                 _schema({}, []), lambda args: backend.list_orders()),
            Tool("start_return", "Start a return for an order. Checks the return policy and refuses "
                                 "if the order does not qualify.",
                 _schema({"order_id": ORDER_ID,
                          "reason": {"type": "string",
                                     "enum": ["too_small", "too_large", "changed_mind", "defective", "other"]}},
                         ["order_id", "reason"]), start_return, writes=True),
            Tool("get_account", "Read the customer's account settings. The shipping address is not shown.",
                 _schema({}, []), get_account),
            Tool("update_shipping_address", "Replace the customer's default shipping address.",
                 _schema({"address": {"type": "string"}}, ["address"]), update_shipping_address, writes=True),
            Tool("set_marketing_opt_in", "Turn marketing email on or off for the customer.",
                 _schema({"opt_in": {"type": "boolean"}}, ["opt_in"]),
                 lambda args: backend.set_marketing_opt_in(args["opt_in"]), writes=True),
            Tool("diagnose_device", "Find out what is wrong with a device from its serial number, which "
                                    "starts with SN-. Returns the fault, the fix and the evidence.",
                 _schema({"serial": {"type": "string"}}, ["serial"]), diagnose_device),
            Tool("handoff_to_claims", "Hand the conversation to the insurer's claims specialist when an item "
                                      "arrived damaged. The specialist talks to the customer directly.",
                 _schema({"summary": {"type": "string"}}, ["summary"]), handoff_to_claims,
                 writes=True),   # it sends the summary to a third party and leads to a claim
        ]
        return [self._logged(tool) for tool in tools]

    def _gate(self, approve):
        def gate(tool: Tool, args: dict) -> bool:
            allowed = approve(tool.name, args)
            if not allowed:   # the tool never runs, so this is the only place the attempt can reach the trace
                self.rt.log("tool_call", str(args), name=f"main.{tool.name}")
                self.rt.log("tool_result", "Declined at the write gate.")
            return allowed
        return gate

    def _logged(self, tool: Tool) -> Tool:
        inner = tool.run

        def run(args):
            self.rt.log("tool_call", str(args), name=f"main.{tool.name}")
            output = inner(args)
            self.rt.log("tool_result", (output if isinstance(output, str) else json.dumps(output))[:2000])
            return output

        tool.run = run
        return tool

    # ---- conversation ---------------------------------------------------
    def send(self, user_text: str) -> str:
        self.rt.log("user", user_text)
        reply = self._claims_turn(user_text) if self.claims else self._main_turn(user_text)
        self.rt.log("assistant", reply)
        return reply

    def _main_turn(self, user_text: str) -> str:
        if self.note_for_main:
            user_text = f"({self.note_for_main})\n\n{user_text}"
            self.note_for_main = None
        result = self.agent.run(user_text, self.messages)
        if self.handoff_summary is None:
            return result.text or f"Sorry, I could not finish that request ({result.stop})."
        self.claims = ClaimsSession(self.rt, f"{user_text}\n\n(Summary from Tamberwick support: {self.handoff_summary})")
        self.handoff_summary = None
        return self._finish_claims_turn(self.claims.reply())

    def _claims_turn(self, user_text: str) -> str:
        return self._finish_claims_turn(self.claims.send(user_text))

    def _finish_claims_turn(self, reply: str) -> str:
        if self.claims.done:
            self.note_for_main = f"The Harbor Mutual claims specialist finished with the customer and said: {reply}"
            self.claims = None
        return reply


def new_conversation(backend: Backend | None = None, meter: Meter | None = None, client=None,
                     customer_id: str | None = None) -> Conversation:
    """Entry point the eval runner calls. Same signature as app.new_conversation.

    The eval has no customer to ask, so every write is allowed here. In production, build the
    Conversation with a callback that confirms each write with the customer.
    """
    return Conversation(backend, meter, client, customer_id=customer_id, approve=allow_all_writes)
