import unittest
from datetime import datetime, timedelta

from src.models import Client, Order
from src.services.deadline_notifier import collect_deadline_alerts, format_alerts_message


class TestDeadlineNotifier(unittest.TestCase):
    def _order(self, name: str, deadline: str, status: str = "В работе") -> Order:
        return Order(
            id="1",
            service_type=name,
            deadline=deadline,
            status=status,
        )

    def test_collects_urgent_and_overdue(self):
        today = datetime.now().date()
        soon = (today + timedelta(days=2)).strftime("%d.%m.%Y")
        overdue = (today - timedelta(days=1)).strftime("%d.%m.%Y")
        far = (today + timedelta(days=30)).strftime("%d.%m.%Y")

        client = Client(
            id="c1",
            name="Клиент",
            orders=[
                self._order("Срочный", soon),
                self._order("Просрочен", overdue),
                self._order("Далёкий", far),
                self._order("Готов", soon, status="Завершен"),
            ],
        )

        alerts = collect_deadline_alerts([client], warn_days=5)
        names = {a.order_name for a in alerts}
        self.assertEqual(names, {"Срочный", "Просрочен"})

    def test_format_message(self):
        msg = format_alerts_message([])
        self.assertEqual(msg, "")
        alerts = collect_deadline_alerts(
            [Client(id="c", name="A", orders=[self._order("X", datetime.now().strftime("%d.%m.%Y"))])],
            warn_days=5,
        )
        self.assertIn("A", format_alerts_message(alerts))


if __name__ == "__main__":
    unittest.main()
