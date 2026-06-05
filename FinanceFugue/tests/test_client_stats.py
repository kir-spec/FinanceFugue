import unittest

from src.models import Client, Order
from src.services.client_stats import calculate_client_stats, calculate_global_dashboard


class TestClientStats(unittest.TestCase):
    def test_client_stats(self):
        client = Client(
            id="c1",
            name="A",
            orders=[
                Order(id="o1", service_type="X", price=1000, advance=200, status="В работе"),
                Order(id="o2", service_type="Y", price=500, advance=0, status="Завершен"),
            ],
        )
        stats = calculate_client_stats(client)
        self.assertEqual(stats["total_orders"], 2)
        self.assertEqual(stats["completed_orders"], 1)

    def test_global_dashboard(self):
        clients = [
            Client(
                id="c1",
                name="A",
                orders=[Order(id="o1", service_type="X", price=1000, advance=100, status="В работе")],
            )
        ]
        dash = calculate_global_dashboard(clients)
        self.assertEqual(len(dash), 5)
        self.assertIn("В РАБОТЕ", dash[0][0])


if __name__ == "__main__":
    unittest.main()
