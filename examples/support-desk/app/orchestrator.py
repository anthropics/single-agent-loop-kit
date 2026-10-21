# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""The router. It never answers on its own: it delegates each request to a
specialist subagent, or hands the whole conversation to claims."""

from __future__ import annotations

from .backend import Backend
from .llm import Meter, create, get_client, text_of, tool_uses
from .subagents import MAX_TURNS, ClaimsSession, Runtime, load_prompt, run_subagent

DELEGATES = ["orders", "shipping", "returns", "account", "diagnostics"]

ROUTER_TOOLS = [
    {
        "name": "delegate",
        "description": "Send a brief to one specialist and get back its summary.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent": {"type": "string", "enum": DELEGATES},
                "brief": {"type": "string", "description": "Everything the specialist needs to know."},
            },
            "required": ["agent", "brief"],
        },
    },
    {
        "name": "handoff_to_claims",
        "description": "Hand the conversation to the claims specialist for shipping damage.",
        "input_schema": {
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        },
    },
]


def _refusal(call) -> str | None:
    """Why a router tool call will not run. The schema lists the tools and the specialists,
    but nothing makes the model keep to it, so the call is checked against what was declared."""
    if call.name not in {tool["name"] for tool in ROUTER_TOOLS}:
        return f"There is no tool named {call.name}."
    if call.name == "delegate" and not (call.input.get("agent") in DELEGATES and call.input.get("brief")):
        return f"delegate needs a brief and one of these specialists: {', '.join(DELEGATES)}."
    return None


class Conversation:
    """One customer conversation. Call send() once per customer message."""

    def __init__(self, backend: Backend | None = None, meter: Meter | None = None, client=None) -> None:
        self.rt = Runtime(backend or Backend(), meter or Meter(), client or get_client(),
                          approve=lambda name, args: True)
        self.messages: list = []
        self.claims: ClaimsSession | None = None

    @property
    def trace(self) -> list:
        return self.rt.trace

    def send(self, user_text: str) -> str:
        self.rt.log("user", user_text)
        reply = self._claims_turn(user_text) if self.claims else self._router_turn(user_text)
        self.rt.log("assistant", reply)
        return reply

    def _claims_turn(self, user_text: str) -> str:
        reply = self.claims.send(user_text)
        self._close_claims_if_done(reply)
        return reply

    def _close_claims_if_done(self, reply: str) -> None:
        if self.claims and self.claims.done:
            self.messages.append({"role": "assistant", "content": f"[claims specialist] {reply}"})
            self.claims = None

    def _router_turn(self, user_text: str) -> str:
        self.messages.append({"role": "user", "content": user_text})
        for _ in range(MAX_TURNS):
            response = create(self.rt.client, self.rt.meter, "router", system=load_prompt("router"),
                              messages=self.messages, tools=ROUTER_TOOLS)
            self.messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason != "tool_use":
                return text_of(response)

            results, handoff_summary = [], None
            for call in tool_uses(response):
                refusal = _refusal(call)
                if refusal:
                    self.rt.log("tool_call", str(call.input), name=f"router.{call.name}")
                    self.rt.log("tool_result", refusal)
                    results.append({"type": "tool_result", "tool_use_id": call.id, "content": refusal, "is_error": True})
                    continue
                self.rt.log("tool_call", str(call.input), name=f"router.{call.name}")
                if call.name == "delegate":
                    output = run_subagent(self.rt, call.input["agent"], call.input["brief"])
                else:
                    handoff_summary = call.input.get("summary", "")
                    output = "Conversation handed to the claims specialist."
                self.rt.log("tool_result", output)
                results.append({"type": "tool_result", "tool_use_id": call.id, "content": output})
            self.messages.append({"role": "user", "content": results})

            if handoff_summary is not None:
                opening = f"{user_text}\n\n(Router summary: {handoff_summary})"
                self.claims = ClaimsSession(self.rt, opening)
                reply = self.claims.reply()
                self._close_claims_if_done(reply)
                return reply
        return "Sorry, I could not finish that request."


def new_conversation(backend: Backend | None = None, meter: Meter | None = None, client=None,
                     customer_id: str | None = None) -> Conversation:
    """Entry point the eval runner calls. Keep this signature when you change the app.
    customer_id is the customer the eval task says is signed in."""
    return Conversation(backend, meter, client)
