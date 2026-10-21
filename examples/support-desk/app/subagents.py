# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""Specialist subagents. Each one runs in its own context window with its own
prompt and tools, and hands back only its final text."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .backend import Backend
from .llm import Meter, create, text_of, tool_uses
from .tools import TOOLS_BY_AGENT, call_tool

PROMPTS = Path(__file__).parent / "prompts"
MAX_TURNS = 8


def load_prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text()


def allow_all_writes(name: str, args: dict) -> bool:
    """A write gate that asks nobody. The eval uses it because there is no customer to ask."""
    return True


@dataclass
class Runtime:
    backend: Backend
    meter: Meter
    client: object
    trace: list = field(default_factory=list)
    # The write gate: called with a tool's name and arguments before any write. With none set, no write runs.
    approve: Callable[[str, dict], bool] | None = None
    # Told the usage of every run_subagent model call. If it returns False, the conversation's token
    # budget is spent and the specialist stops.
    on_usage: Callable[[object], object] | None = None

    def log(self, role: str, content: str, name: str | None = None) -> None:
        entry = {"role": role, "content": content}
        if name:
            entry["name"] = name
        self.trace.append(entry)


def _run_tools(rt: Runtime, agent: str, response) -> list:
    declared = {tool["name"] for tool in TOOLS_BY_AGENT[agent]}
    results = []
    for call in tool_uses(response):
        rt.log("tool_call", str(call.input), name=f"{agent}.{call.name}")
        if call.name in declared:   # an agent may only run the tools it was given
            output = call_tool(rt.backend, call.name, call.input, rt.approve)
        else:
            output = json.dumps({"error": f"Unknown tool {call.name}."})
        rt.log("tool_result", output[:2000])
        results.append({"type": "tool_result", "tool_use_id": call.id, "content": output})
    return results


def run_subagent(rt: Runtime, name: str, brief: str, system: str | None = None) -> str:
    """Run one specialist to completion and return its summary."""
    messages = [{"role": "user", "content": brief}]
    for _ in range(MAX_TURNS):
        response = create(rt.client, rt.meter, name, system=system or load_prompt(name),
                          messages=messages, tools=TOOLS_BY_AGENT[name])
        spent = bool(rt.on_usage) and rt.on_usage(response.usage) is False
        if response.stop_reason != "tool_use":
            return text_of(response)
        if spent:
            return f"The {name} specialist stopped before it finished: the token budget for this request is spent."
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": _run_tools(rt, name, response)})
    return f"The {name} specialist ran out of turns."


class ClaimsSession:
    """The claims specialist takes over the conversation and talks to the customer
    directly until a claim is opened.

    Claims is run by Harbor Mutual, the shipping insurer, not by Tamberwick. The
    insurer owns this prompt, and it requires that the claim record be the
    customer's own conversation with its agent. In production this is a call to
    the insurer's endpoint; here it runs in process so the example is self-contained.
    """

    def __init__(self, rt: Runtime, opening: str) -> None:
        self.rt = rt
        self.messages: list = [{"role": "user", "content": opening}]
        self.done = False

    def reply(self) -> str:
        for _ in range(MAX_TURNS):
            response = create(self.rt.client, self.rt.meter, "claims", system=load_prompt("claims"),
                              messages=self.messages, tools=TOOLS_BY_AGENT["claims"])
            self.messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason != "tool_use":
                return text_of(response)
            before = len(self.rt.backend.actions)
            results = _run_tools(self.rt, "claims", response)
            self.messages.append({"role": "user", "content": results})
            if any(a["name"] == "open_claim" for a in self.rt.backend.actions[before:]):
                self.done = True
            if any(json.loads(r["content"]).get("declined") for r in results):
                self.done = True   # the customer said no to the claim, so the conversation goes back
        return "The claims specialist ran out of turns."

    def send(self, user_text: str) -> str:
        self.messages.append({"role": "user", "content": user_text})
        return self.reply()
