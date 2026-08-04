import unittest

from src.models import Order


class TestOrderUpdatePriceFix(unittest.TestCase):
    """Проверки исправления рассинхрона ``advance`` при ``update_price``."""

    def _filled_order(self, price=1000.0, advance=500.0) -> Order:
        order = Order(id="o1", service_type="Test", price=price, advance=advance)
        order.add_payment(advance, "аванс", date="01.01.2026")
        return order

    def test_update_price_below_advance_keeps_advance_in_sync(self):
        order = self._filled_order(price=1000.0, advance=500.0)
        order.update_price(300.0)

        self.assertEqual(order.price, 300.0)
        self.assertEqual(order.advance, 300.0)
        self.assertEqual(order.total_received, 300.0)
        self.assertEqual(order.debt, 0.0)

    def test_update_price_above_advance_no_return_payment(self):
        order = self._filled_order(price=1000.0, advance=500.0)
        before = len(order.payments)
        order.update_price(1500.0)

        self.assertEqual(order.price, 1500.0)
        self.assertEqual(order.advance, 500.0)
        self.assertEqual(len(order.payments), before)

    def test_update_price_rejects_below_received(self):
        order = self._filled_order(price=1000.0, advance=500.0)
        order.add_payment(300.0, "платеж", date="02.01.2026")
        with self.assertRaises(ValueError):
            order.update_price(100.0)

    def test_overpayment_rejected_when_debt_zero(self):
        order = self._filled_order(price=1000.0, advance=500.0)
        order.add_payment(500.0, "платеж", date="02.01.2026")
        # debt == 0 теперь блокирует любой положительный платёж
        with self.assertRaises(ValueError):
            order.add_payment(10.0, "платеж", date="03.01.2026")


class TestFormatAmountDecimal(unittest.TestCase):
    def test_half_up_rounding(self):
        from src.services.currency import format_amount

        # Банкирское HALF_EVEN дало бы "0", финансовое HALF_UP → "1"
        self.assertEqual(format_amount(0.5, "RUB"), "1 ₽")
        self.assertEqual(format_amount(2.5, "RUB"), "3 ₽")
        # Точные суммы не теряют копейки
        self.assertEqual(format_amount(1000.5, "RUB"), "1 001 ₽")


class TestClientStatsHasOutstandingDebt(unittest.TestCase):
    def test_has_outstanding_debt_per_currency(self):
        from src.services.currency import has_outstanding_debt

        self.assertFalse(has_outstanding_debt({}))
        self.assertFalse(has_outstanding_debt({"RUB": 0}))
        self.assertTrue(has_outstanding_debt({"RUB": 100}))
        self.assertTrue(has_outstanding_debt({"RUB": 0, "USD": 50}))


if __name__ == "__main__":
    unittest.main()
