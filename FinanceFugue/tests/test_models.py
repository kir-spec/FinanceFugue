import unittest

from src.models import Order


class TestOrder(unittest.TestCase):
    def _order(self, price=1000.0, advance=500.0):
        order = Order(id="o1", service_type="Test", price=price, advance=advance)
        order.add_payment(500.0, "аванс", date="01.01.2026")
        return order

    def test_debt_after_advance(self):
        order = self._order()
        self.assertEqual(order.debt, 500.0)

    def test_payment_reduces_debt(self):
        order = self._order()
        order.add_payment(200.0, "платеж", date="02.01.2026")
        self.assertEqual(order.debt, 300.0)

    def test_zero_payment_rejected(self):
        order = Order(id="o1", service_type="Test", price=100.0)
        with self.assertRaises(ValueError):
            order.add_payment(0, "платеж")

    def test_overpayment_rejected(self):
        order = self._order()
        with self.assertRaises(ValueError):
            order.add_payment(600.0, "платеж", date="02.01.2026")


if __name__ == "__main__":
    unittest.main()
