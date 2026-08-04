"""Расчёт статистики по клиентам и заказам."""
from typing import List

from ..models import Client
from .currency import format_multi_currency, has_outstanding_debt, sum_by_currency


def calculate_client_stats(client: Client) -> dict:
    total_orders = len(client.orders)
    completed_orders = sum(1 for o in client.orders if o.status == "Завершен")
    advance_by = sum_by_currency(client.orders, field="advance")
    received_by = sum_by_currency(client.orders, field="total_received")
    debt_by = sum_by_currency(
        client.orders,
        field="debt",
        active_only=True,
    )
    return {
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "total_received": sum(received_by.values()),
        "total_advance": sum(advance_by.values()),
        "total_debt": sum(debt_by.values()),
        "advance_by_currency": advance_by,
        "received_by_currency": received_by,
        "debt_by_currency": debt_by,
        "advance_display": format_multi_currency(advance_by),
        "received_display": format_multi_currency(received_by),
        "debt_display": format_multi_currency(debt_by),
    }


def calculate_global_dashboard(clients: List[Client]) -> list[tuple[str, str, str]]:
    in_work, done = 0, 0
    all_orders = [o for c in clients for o in c.orders]
    advance_by = sum_by_currency(all_orders, field="advance")
    debt_by = sum_by_currency(all_orders, field="debt", active_only=True)
    cash_by = sum_by_currency(all_orders, field="total_received")

    for client in clients:
        for order in client.orders:
            if order.status == "Завершен":
                done += 1
            else:
                in_work += 1

    return [
        ("📋 В РАБОТЕ", str(in_work), "#00D1FF"),
        ("✅ ВЫПОЛНЕНО", str(done), "#28A745"),
        ("💰 АВАНСЫ", format_multi_currency(advance_by), "#FFD700"),
        ("💳 ДОЛГИ", format_multi_currency(debt_by), "#FF4B2B" if has_outstanding_debt(debt_by) else "#28A745"),
        ("💵 КАССА", format_multi_currency(cash_by), "#28A745"),
    ]
