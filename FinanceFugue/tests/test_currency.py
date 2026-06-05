import unittest

from src.models import Client, Order
from src.services.currency import format_multi_currency, sum_by_currency
from src.services.client_stats import calculate_client_stats, calculate_global_dashboard


class TestCurrency(unittest.TestCase):
    def test_sum_by_currency_does_not_mix(self):
        orders = [
            Order(id="o1", service_type="A", price=100, currency="RUB"),
            Order(id="o2", service_type="B", price=50, currency="USD"),
        ]
        advance = sum_by_currency(orders, field="advance")
        self.assertEqual(advance["RUB"], 0.0)
        self.assertEqual(advance["USD"], 0.0)

    def test_format_multi_currency(self):
        text = format_multi_currency({"RUB": 1000, "USD": 50})
        self.assertIn("₽", text)
        self.assertIn("$", text)
        self.assertIn("+", text)

    def test_client_stats_mixed_currency_display(self):
        client = Client(
            id="c1",
            name="A",
            orders=[
                Order(id="o1", service_type="X", price=1000, advance=100, currency="RUB"),
                Order(id="o2", service_type="Y", price=200, advance=50, currency="USD"),
            ],
        )
        stats = calculate_client_stats(client)
        self.assertIn("₽", stats["advance_display"])
        self.assertIn("$", stats["advance_display"])

    def test_global_dashboard_mixed(self):
        clients = [
            Client(
                id="c1",
                name="A",
                orders=[Order(id="o1", service_type="X", price=100, currency="USD")],
            )
        ]
        dash = calculate_global_dashboard(clients)
        self.assertIn("$", dash[2][1])


if __name__ == "__main__":
    unittest.main()
