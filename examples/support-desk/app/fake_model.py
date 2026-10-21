# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""A scripted stand-in for the model, for offline smoke tests only.

Set KIT_MODEL=fake to use it. It follows a handful of keyword rules written for
this example's unmodified tools, so it can exercise the plumbing (delegation,
tool calls, handoff, graders, result files) with no API key and no spend.

Its scores mean nothing. Never read a pass rate from a fake run as evidence
about an architecture.
"""

from __future__ import annotations

import itertools
import json
import re
from types import SimpleNamespace

_ids = itertools.count(1)


def _text(text: str):
    return SimpleNamespace(type="text", text=text)


def _use(name: str, args: dict):
    return SimpleNamespace(type="tool_use", id=f"toolu_fake_{next(_ids)}", name=name, input=args)


def _blocks(content):
    return content if isinstance(content, list) else []


def _field(block, key):
    return block.get(key) if isinstance(block, dict) else getattr(block, key, None)


def _first(pattern: str, text: str, flags=0):
    match = re.search(pattern, text, flags)
    return match.group(match.lastindex or 0) if match else None


def _return_order(ask: str):
    return _first(r"(?:return|send back).*?\b(5\d{3})\b", ask, re.S | re.I) or _first(r"\b5\d{3}\b", ask)


class FakeClient:
    def __init__(self) -> None:
        self.messages = self

    def create(self, *, model, max_tokens, system, messages, tools=(), **_):
        names = [t["name"] for t in tools]
        takes = {t["name"]: set(t.get("input_schema", {}).get("properties", {})) for t in tools}
        user_texts = [m["content"] for m in messages if m["role"] == "user" and isinstance(m["content"], str)]
        last_ask = max(i for i, m in enumerate(messages)
                       if m["role"] == "user" and isinstance(m["content"], str))
        ask = messages[last_ask]["content"]

        called, results = [], []
        for message in messages[last_ask + 1:]:
            for block in _blocks(message["content"]):
                if _field(block, "type") == "tool_use":
                    called.append(block)
                elif _field(block, "type") == "tool_result":
                    results.append(str(_field(block, "content")))
        seen = "\n".join(results)
        everything = "\n".join(user_texts) + "\n" + seen

        if "delegate" in names:
            calls, final = self._route(ask, called, results)
        else:
            calls, final = self._specialist(names, ask, {_field(c, "name") for c in called}, seen, everything)
            for call in calls:   # the two versions of a tool can take different arguments
                call.input = {key: value for key, value in call.input.items() if key in takes[call.name]}
            if not calls and '"conclusion"' in system:   # a subagent asked to answer in the agreed shape
                final = json.dumps({"conclusion": (results[-1] if results else final)[:600],
                                    "evidence": [r[:120] for r in results[:-1]], "actions_taken": [],
                                    "confidence": "medium", "caveats": ["Offline stand-in, not a model."]})

        content = calls if calls else [_text(final)]
        usage = SimpleNamespace(
            input_tokens=len(system) // 4 + sum(len(str(m["content"])) for m in messages) // 4,
            output_tokens=sum(len(json.dumps(c.input)) for c in calls) // 4 if calls else len(final) // 4,
        )
        return SimpleNamespace(content=content, usage=usage, model="fake",
                               stop_reason="tool_use" if calls else "end_turn")

    @staticmethod
    def _route(ask: str, called: list, results: list):
        if re.search(r"crack|damag|claim", ask, re.I):
            if not called:
                return [_use("handoff_to_claims", {"summary": ask})], ""
            return [], "Our claims specialist will take it from here."
        plan = []
        if re.search(r"error|blink|stopping", ask, re.I):
            plan.append("diagnostics")
        if re.search(r"where is|arrive|shipped|status|taking too long|get here", ask, re.I):
            plan += ["orders", "shipping"]
        if re.search(r"return|send back", ask, re.I):
            plan.append("returns")
        if re.search(r"address|marketing", ask, re.I):
            plan.append("account")
        done = [_field(c, "input")["agent"] for c in called if _field(c, "name") == "delegate"]
        for agent in plan:
            if agent not in done:
                notes = "\n".join(results)
                return [_use("delegate", {"agent": agent, "brief": f"{ask}\n\nSpecialist notes so far:\n{notes}"})], ""
        return [], "\n".join(results) or "I can help with orders, returns, accounts and devices."

    @staticmethod
    def _specialist(names: list, ask: str, called: set, seen: str, everything: str):
        wants_return = bool(re.search(r"return|send back", ask, re.I))
        order = _return_order(ask) if wants_return else _first(r"\b5\d{3}\b", everything)
        first_order = _first(r"\b5\d{3}\b", ask)
        asks_where = bool(re.search(r"where is|arrive|shipped|status|taking too long|get here", ask, re.I))
        damaged = bool(re.search(r"crack|damag", ask, re.I))
        tracking = _first(r"TRK-\d+", everything)
        customer = _first(r"C-\d{4}", everything)
        serial = _first(r"SN-[A-Z]+-\d+", everything)

        candidates = {
            # tools of the single loop version
            "load_skill": {"name": "returns"} if wants_return else None,
            "track_order": {"order_id": first_order} if first_order and asks_where else None,
            "start_return": {"order_id": order, "reason": "other"} if order and wants_return else None,
            "diagnose_device": {"serial": serial} if serial and "fetch_device_logs" not in names else None,
            "handoff_to_claims": {"summary": ask} if damaged else None,
            # tools of the original subagents
            "get_order": {"order_id": order} if order else None,
            "get_tracking": {"tracking_id": tracking} if tracking else None,
            "check_return_eligibility": {"order_id": order} if order and wants_return else None,
            "create_return": ({"order_id": order, "reason": "other"}
                              if order and '"eligible": true' in seen else None),
            "update_shipping_address": (
                {"customer_id": customer,
                 "address": _first(r"address to (.+?\d{5})", ask, re.I) or "unknown"}
                if customer and re.search(r"address", ask, re.I) else None),
            "set_marketing_opt_in": (
                {"customer_id": customer, "opt_in": not re.search(r"stop|unsubscribe|no more", ask, re.I)}
                if customer and re.search(r"marketing", ask, re.I) else None),
            "fetch_device_logs": {"serial": serial} if serial else None,
            "lookup_error_code": ({"code": _first(r"ERR\s+(E\d+)", seen)}
                                  if _first(r"ERR\s+(E\d+)", seen) else None),
            "open_claim": (
                {"order_id": order,
                 "damage_description": max(re.findall(r"[^\n]*(?:crack|damag|crush)[^\n]*", everything, re.I),
                                           key=len, default="damaged in shipping"),
                 "photos_received": True}
                if order and re.search(r"photo", everything, re.I)
                and re.search(r"crack|damag", everything, re.I) and "get_order" in called else None),
        }
        calls = [_use(name, candidates[name]) for name in names
                 if candidates.get(name) and name not in called]
        if calls:
            return calls, ""
        if "open_claim" in names and "open_claim" not in called:
            return [], ("I'm sorry about the damage. Could you describe what is damaged and where, "
                        "and confirm you've emailed photos to claims@tamberwick.example?")
        clipped = [r if len(r) <= 3000 else f"{r[:200]} ... {r[-1500:]}" for r in seen.splitlines()]
        return [], "\n".join(clipped) or "Nothing to do."
