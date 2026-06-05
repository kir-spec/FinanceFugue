"""Проверка приближающихся дедлайнов заказов."""
from dataclasses import dataclass
from datetime import datetime
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import Client


@dataclass(frozen=True)
class DeadlineAlert:
    client_name: str
    order_name: str
    deadline: str
    days_left: int


def collect_deadline_alerts(
    clients: List["Client"],
    *,
    warn_days: int = 5,
) -> List[DeadlineAlert]:
    """Возвращает незавершённые заказы с дедлайном в пределах warn_days дней (включая просроченные)."""
    alerts: List[DeadlineAlert] = []
    today = datetime.now().date()

    for client in clients:
        for order in client.orders:
            if order.status == "Завершен" or not order.deadline:
                continue
            try:
                deadline_date = datetime.strptime(order.deadline, "%d.%m.%Y").date()
            except ValueError:
                continue
            days_left = (deadline_date - today).days
            if days_left <= warn_days:
                alerts.append(
                    DeadlineAlert(
                        client_name=client.name,
                        order_name=order.service_type,
                        deadline=order.deadline,
                        days_left=days_left,
                    )
                )

    alerts.sort(key=lambda a: a.days_left)
    return alerts


def format_alerts_message(alerts: List[DeadlineAlert]) -> str:
    if not alerts:
        return ""
    lines = []
    for alert in alerts[:15]:
        if alert.days_left < 0:
            status = f"просрочен на {abs(alert.days_left)} дн."
        elif alert.days_left == 0:
            status = "сегодня"
        else:
            status = f"через {alert.days_left} дн."
        lines.append(f"• {alert.client_name} — «{alert.order_name}» ({alert.deadline}, {status})")
    if len(alerts) > 15:
        lines.append(f"... и ещё {len(alerts) - 15}")
    return "\n".join(lines)
