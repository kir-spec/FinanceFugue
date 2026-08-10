from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Tuple

from ..models import Client

def calculate_monthly_revenue(clients: List[Client]) -> Tuple[List[str], List[float], List[float]]:
    """Возвращает (Месяцы, Выручка, Долги) с агрегацией по месяцам (YYYY-MM)."""
    monthly_data: Dict[str, Dict[str, float]] = defaultdict(lambda: {"revenue": 0.0, "debt": 0.0})
    
    for client in clients:
        if client.is_deleted:
            continue
        for order in client.orders:
            if order.is_deleted:
                continue
            
            try:
                dt_str = order.created_at.split()[0]
                dt = datetime.strptime(dt_str, "%d.%m.%Y")
                month_key = dt.strftime("%Y-%m")
            except Exception:
                month_key = "Неизвестно"
                
            monthly_data[month_key]["revenue"] += order.total_received
            monthly_data[month_key]["debt"] += order.debt

    sorted_months = sorted(monthly_data.keys())
    if "Неизвестно" in sorted_months:
        sorted_months.remove("Неизвестно")
        
    revenues = [monthly_data[m]["revenue"] for m in sorted_months]
    debts = [monthly_data[m]["debt"] for m in sorted_months]
    
    return sorted_months, revenues, debts


def get_top_clients(clients: List[Client], top_n: int = 5) -> List[Tuple[str, float]]:
    """Возвращает топ N клиентов по общей сумме оплаченных заказов."""
    client_totals = []
    
    for client in clients:
        if client.is_deleted:
            continue
        total_paid = sum(o.total_received for o in client.orders if not o.is_deleted)
        if total_paid > 0:
            client_totals.append((client.name, total_paid))
            
    # Сортируем по убыванию выручки
    client_totals.sort(key=lambda x: x[1], reverse=True)
    return client_totals[:top_n]


def get_funnel_stats(clients: List[Client]) -> Dict[str, int]:
    """Считает заказы по статусам."""
    stats = {
        "В работе": 0,
        "Завершен": 0,
        "Удален": 0
    }
    
    for client in clients:
        if client.is_deleted:
            continue
        for order in client.orders:
            if order.is_deleted:
                stats["Удален"] += 1
            elif order.status == "Завершен":
                stats["Завершен"] += 1
            else:
                stats["В работе"] += 1
                
    return stats
