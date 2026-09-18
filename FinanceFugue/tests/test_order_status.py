import unittest

from src.models import Client, Order
from src.services.client_stats import calculate_client_stats
from src.services.order_status import classify_order, reconcile_order_dict


class TestOrderStatusSync(unittest.TestCase):
    def test_archived_paid_counts_completed(self):
        o = Order(
            id="o1",
            service_type="Mix",
            price=10000,
            advance=5000,
            status="В работе",
            is_archived=True,
        )
        o.add_payment(5000, payment_type="аванс")
        o.add_payment(5000, payment_type="платеж")
        self.assertEqual(classify_order(o), "completed")
        stats = calculate_client_stats(Client(id="c1", name="A", orders=[o]))
        self.assertEqual(stats["completed_orders"], 1)
        self.assertEqual(stats["active_orders"], 0)

    def test_reconcile_dict_from_bot(self):
        raw = {
            "id": "o1",
            "price": 10000,
            "status": "В работе",
            "is_archived": True,
            "payments": [{"amount": 10000}],
        }
        fixed = reconcile_order_dict(raw)
        self.assertEqual(fixed["status"], "Завершен")


    def test_status_matrix(self):
        from src.services.order_status import classify_order

        cases = [
            ("В работе", False, 0, "in_work"),
            ("Завершен", False, 0, "completed"),
            ("Отменен", False, 0, "cancelled"),
            ("В работе", True, 0, "completed"),
            ("Выполнен", False, 0, "completed"),
        ]
        for status, archived, price, expected in cases:
            pr = price or 100
            o = Order(
                id="x",
                service_type="s",
                price=pr,
                status=status,
                is_archived=archived,
            )
            if archived and expected == "completed":
                o.add_payment(pr, payment_type="платеж")
            self.assertEqual(classify_order(o), expected, msg=status)


if __name__ == "__main__":
    unittest.main()
