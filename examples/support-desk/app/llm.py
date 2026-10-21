# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""The one place this app talks to the model, plus a meter for calls and tokens."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def model_name() -> str:
    name = os.environ.get("KIT_MODEL")
    if not name:
        raise SystemExit(
            "Set KIT_MODEL to the Claude model id your team uses, "
            "or KIT_MODEL=fake for the offline smoke test."
        )
    return name


@dataclass
class Meter:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    by_agent: dict = field(default_factory=dict)

    def add(self, agent: str, usage) -> None:
        tokens_in = (
            getattr(usage, "input_tokens", 0)
            + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
            + (getattr(usage, "cache_read_input_tokens", 0) or 0)
        )
        tokens_out = getattr(usage, "output_tokens", 0)
        self.calls += 1
        self.input_tokens += tokens_in
        self.output_tokens += tokens_out
        row = self.by_agent.setdefault(agent, {"calls": 0, "input_tokens": 0, "output_tokens": 0})
        row["calls"] += 1
        row["input_tokens"] += tokens_in
        row["output_tokens"] += tokens_out


def get_client():
    if model_name() == "fake":
        from .fake_model import FakeClient
        return FakeClient()
    import anthropic
    return anthropic.Anthropic()


def create(client, meter: Meter, agent: str, *, system: str, messages: list, tools: list):
    response = client.messages.create(
        model=model_name(),
        max_tokens=16000,
        system=system,
        messages=messages,
        tools=tools,
    )
    meter.add(agent, response.usage)
    return response


def text_of(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text").strip()


def tool_uses(response) -> list:
    return [b for b in response.content if b.type == "tool_use"]
