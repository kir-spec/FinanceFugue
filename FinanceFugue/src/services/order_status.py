"""Канонические статусы заказов — зеркало kosha_finance_bot/crm_order_status.py."""
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from ..models import Order

OrderBucket = Literal["in_work", "completed", "cancelled", "other"]

_CANONICAL = frozenset({"В работе", "Завершен", "Отменен"})

_ALIASES = {
    "завершен": "Завершен",
    "завершён": "Завершен",
    "завершено": "Завершен",
    "выполнен": "Завершен",
    "выполнено": "Завершен",
    "done": "Завершен",
    "completed": "Завершен",
    "complete": "Завершен",
    "в работе": "В работе",
    "in progress": "В работе",
    "in_work": "В работе",
    "active": "В работе",
    "в": "В работе",
    "отменен": "Отменен",
    "отменён": "Отменен",
    "cancelled": "Отменен",
    "canceled": "Отменен",
}


def normalize_order_status(status: str) -> str:
    if not status or not str(status).strip():
        return "В работе"
    s = str(status).strip()
    if s in _CANONICAL:
        return s
    key = s.lower().replace("ё", "е")
    return _ALIASES.get(key, s)


def classify_order(order: "Order") -> OrderBucket:
    status = normalize_order_status(order.status)

    if status == "Отменен":
        return "cancelled"
    if status == "Завершен":
        return "completed"
    if getattr(order, "is_archived", False) and order.debt <= 0.001 and order.price > 0:
        return "completed"
    if not getattr(order, "is_archived", False) and status == "В работе":
        return "in_work"
    if not getattr(order, "is_archived", False):
        return "in_work"
    return "other"


def is_order_in_work(order: "Order") -> bool:
    return classify_order(order) == "in_work"


def is_order_completed(order: "Order") -> bool:
    return classify_order(order) == "completed"


def order_debt_from_payments(price: float, payments: list) -> float:
    received = 0.0
    for p in payments or []:
        if not isinstance(p, dict):
            continue
        try:
            received += float(p.get("amount", 0) or 0)
        except (TypeError, ValueError):
            continue
    return max(0.0, float(price or 0) - received)


def reconcile_order_dict(o_dict: dict) -> dict:
    out = dict(o_dict)
    out["status"] = normalize_order_status(out.get("status") or "В работе")
    price = float(out.get("price", 0) or 0)
    debt = order_debt_from_payments(price, out.get("payments") or [])
    if out.get("is_archived") and debt <= 0.001 and price > 0 and out["status"] == "В работе":
        out["status"] = "Завершен"
    return out


def reconcile_client_dict(c_dict: dict) -> dict:
    out = dict(c_dict)
    orders = []
    for o in out.get("orders") or []:
        if isinstance(o, dict):
            orders.append(reconcile_order_dict(o))
    out["orders"] = orders
    return out


def reconcile_crm_envelope(data: dict) -> dict:
    """После merge/pull: единая семантика статусов по всей базе."""
    if not isinstance(data, dict) or "clients" not in data:
        return data
    out = dict(data)
    out["clients"] = [reconcile_client_dict(c) for c in out["clients"] if isinstance(c, dict)]
    return out
