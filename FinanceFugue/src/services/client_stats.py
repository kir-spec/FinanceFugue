"""Расчёт статистики по клиентам и заказам."""
from typing import List, Optional
from datetime import datetime

from ..models import Client
from .currency import format_multi_currency, has_outstanding_debt, sum_by_currency
from .order_status import classify_order, is_order_in_work, normalize_order_status


def calculate_client_stats(client: Client) -> dict:
    orders = [o for o in client.orders if not getattr(o, "is_deleted", False)]
    total_orders = len(orders)
    active_orders = sum(1 for o in orders if classify_order(o) == "in_work")
    completed_orders = sum(1 for o in orders if classify_order(o) == "completed")
    cancelled_orders = sum(1 for o in orders if classify_order(o) == "cancelled")
    advance_by = sum_by_currency(orders, field="advance")
    received_by = sum_by_currency(orders, field="total_received")
    debt_by = sum_by_currency(
        orders,
        field="debt",
        active_only=True,
    )
    return {
        "total_orders": total_orders,
        "active_orders": active_orders,
        "completed_orders": completed_orders,
        "cancelled_orders": cancelled_orders,
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


def calculate_global_dashboard(
    clients: List[Client], 
    archive_clients: Optional[List[Client]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> list[tuple[str, str, str]]:
    
    in_work, done, cancelled = 0, 0, 0
    active_clients = [c for c in clients if not getattr(c, "is_deleted", False)]
    all_clients = active_clients + (archive_clients or [])
    all_orders = []
    
    for client in all_clients:
        for order in client.orders:
            if getattr(order, "is_deleted", False):
                continue
            order_date = None
            if order.created_at:
                try:
                    order_date = datetime.strptime(order.created_at.split()[0], "%d.%m.%Y")
                except ValueError:
                    pass
            
            if start_date and order_date:
                if order_date.date() < start_date.date():
                    continue
            if end_date and order_date:
                if order_date.date() > end_date.date():
                    continue
                    
            all_orders.append(order)
            bucket = classify_order(order)
            if bucket == "completed":
                done += 1
            elif bucket == "cancelled":
                cancelled += 1
            elif bucket == "in_work":
                in_work += 1

    advance_by = sum_by_currency(all_orders, field="advance")
    debt_by = sum_by_currency(all_orders, field="debt", active_only=True)
    cash_by = sum_by_currency(all_orders, field="total_received")

    return [
        ("📋 В РАБОТЕ", str(in_work), "#00D1FF"),
        ("✅ ВЫПОЛНЕНО", str(done), "#28A745"),
        ("💰 АВАНСЫ", format_multi_currency(advance_by), "#FFD700"),
        ("💳 ДОЛГИ", format_multi_currency(debt_by), "#FF4B2B" if has_outstanding_debt(debt_by) else "#28A745"),
        ("💵 КАССА", format_multi_currency(cash_by), "#28A745"),
    ]
