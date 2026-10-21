# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""Tool definitions, grouped by the subagent that owns them.

Each team wrote its own tools, so there is overlap: three teams wrap `get_order`.
"""

from __future__ import annotations

import json

from .backend import Backend


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "name": name,
        "description": description,
        "input_schema": {"type": "object", "properties": properties, "required": required},
    }


ORDER_ID = {"type": "string", "description": "Four digit order number, for example 5001."}
CUSTOMER_ID = {"type": "string", "description": "Customer id, for example C-1001."}

GET_ORDER = _tool("get_order", "Look up one order: item, status, delivery date, tracking id.",
                  {"order_id": ORDER_ID}, ["order_id"])

TOOLS_BY_AGENT: dict[str, list[dict]] = {
    "orders": [
        GET_ORDER,
        _tool("list_orders", "List a customer's orders.", {"customer_id": CUSTOMER_ID}, ["customer_id"]),
    ],
    "shipping": [
        _tool("get_tracking", "Carrier status and ETA for a tracking id such as TRK-77002.",
              {"tracking_id": {"type": "string"}}, ["tracking_id"]),
    ],
    "returns": [
        GET_ORDER,
        _tool("check_return_eligibility", "Check whether an order can be returned.",
              {"order_id": ORDER_ID}, ["order_id"]),
        _tool("create_return", "Create a return and a prepaid label.",
              {"order_id": ORDER_ID, "reason": {"type": "string"}}, ["order_id", "reason"]),
    ],
    "account": [
        _tool("get_account", "Read a customer's account.", {"customer_id": CUSTOMER_ID}, ["customer_id"]),
        _tool("update_shipping_address", "Replace the customer's default shipping address.",
              {"customer_id": CUSTOMER_ID, "address": {"type": "string"}}, ["customer_id", "address"]),
        _tool("set_marketing_opt_in", "Turn marketing email on or off.",
              {"customer_id": CUSTOMER_ID, "opt_in": {"type": "boolean"}}, ["customer_id", "opt_in"]),
    ],
    "diagnostics": [
        _tool("fetch_device_logs", "Download the full device log for a serial number such as SN-VAC-3391.",
              {"serial": {"type": "string"}}, ["serial"]),
        _tool("lookup_error_code", "Explain a device error code such as E42.",
              {"code": {"type": "string"}}, ["code"]),
    ],
    "claims": [
        GET_ORDER,
        _tool("open_claim", "Open a shipping damage claim.",
              {"order_id": ORDER_ID,
               "damage_description": {"type": "string"},
               "photos_received": {"type": "boolean"}},
              ["order_id", "damage_description", "photos_received"]),
    ],
}

# Tools that change something. A test keeps this in step with the backend.
WRITES = {"create_return", "update_shipping_address", "set_marketing_opt_in", "open_claim"}


def call_tool(backend: Backend, name: str, args: dict, approve=None) -> str:
    """Run one tool against the backend and return its result as a JSON string.

    approve is the conversation's write gate, called with the tool's name and arguments.
    A tool in WRITES runs only when it says yes. With no gate, no write runs.
    """
    fn = getattr(backend, name, None)
    if fn is None or name.startswith("_"):
        return json.dumps({"error": f"Unknown tool {name}."})
    if name in WRITES and approve is None:
        return json.dumps({"error": f"{name} changes something and this conversation has no write gate, so it did not run."})
    if name in WRITES and not approve(name, args):
        return json.dumps({"error": "The customer declined this action. Do not retry it; ask what they want instead.",
                           "declined": True})
    try:
        return json.dumps(fn(**args))
    except TypeError as exc:
        return json.dumps({"error": f"Bad arguments for {name}: {exc}"})
