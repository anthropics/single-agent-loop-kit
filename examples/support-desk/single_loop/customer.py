# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""The backend as one signed-in customer is allowed to use it.

The customer id comes from the session when the conversation is built. It never
comes from the chat and it is not a tool argument, so the model cannot choose
whose records it touches. Every lookup by order number, tracking id or serial
number is checked against that customer, and a record that belongs to someone
else reads exactly like one that does not exist.

The main agent's tools and the subagents' tools both go through this class, so
there is one place where ownership is checked.
"""

from __future__ import annotations

from app.backend import Backend


class CustomerBackend:
    def __init__(self, backend: Backend, customer_id: str | None) -> None:
        if customer_id is not None and customer_id not in backend.customers:
            raise ValueError(f"No customer {customer_id}. Pass the signed-in customer's id, or None for nobody.")
        self._backend = backend
        self.customer_id = customer_id

    @property
    def actions(self) -> list[dict]:
        return self._backend.actions

    def signed_out(self) -> dict | None:
        """An error when nobody is signed in."""
        if self.customer_id is None:
            return {"error": "No customer is signed in, so there is nothing to look up or change. Ask them to "
                             "sign in. An id typed into the chat is not proof of who they are."}
        return None

    def _mine(self) -> dict[str, dict]:
        return {oid: o for oid, o in self._backend.orders.items() if o["customer_id"] == self.customer_id}

    def _refuse_order(self, order_id) -> dict | None:
        """An error unless the signed-in customer owns the order."""
        if str(order_id) not in self._mine():
            return self.signed_out() or {"error": f"No order {order_id}."}
        return None

    # ---- orders and shipping -------------------------------------------
    def get_order(self, order_id: str) -> dict:
        return self._refuse_order(order_id) or self._backend.get_order(order_id)

    def list_orders(self) -> dict:
        return self.signed_out() or self._backend.list_orders(self.customer_id)

    def get_tracking(self, tracking_id: str) -> dict:
        if tracking_id not in {o["tracking_id"] for o in self._mine().values()}:
            return self.signed_out() or {"error": f"No shipment with tracking id {tracking_id}."}
        return self._backend.get_tracking(tracking_id)

    # ---- returns --------------------------------------------------------
    def check_return_eligibility(self, order_id: str) -> dict:
        return self._refuse_order(order_id) or self._backend.check_return_eligibility(order_id)

    def create_return(self, order_id: str, reason: str) -> dict:
        return self._refuse_order(order_id) or self._backend.create_return(order_id, reason)

    # ---- account --------------------------------------------------------
    def get_account(self) -> dict:
        return self.signed_out() or self._backend.get_account(self.customer_id)

    def update_shipping_address(self, address: str) -> dict:
        return self.signed_out() or self._backend.update_shipping_address(self.customer_id, address)

    def set_marketing_opt_in(self, opt_in: bool) -> dict:
        return self.signed_out() or self._backend.set_marketing_opt_in(self.customer_id, opt_in)

    # ---- diagnostics ----------------------------------------------------
    def refuse_device(self, serial: str) -> dict | None:
        """An error unless the serial number is on one of the signed-in customer's orders."""
        if serial not in {o.get("serial") for o in self._mine().values()}:
            return self.signed_out() or {"error": f"No device with serial {serial}."}
        return None

    def fetch_device_logs(self, serial: str) -> dict:
        return self.refuse_device(serial) or self._backend.fetch_device_logs(serial)

    def lookup_error_code(self, code: str) -> dict:
        return self._backend.lookup_error_code(code)   # the same for every customer

    # ---- claims ---------------------------------------------------------
    def open_claim(self, order_id: str, damage_description: str, photos_received: bool) -> dict:
        return self._refuse_order(order_id) or self._backend.open_claim(order_id, damage_description, photos_received)
