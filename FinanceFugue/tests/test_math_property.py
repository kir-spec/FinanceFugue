import math
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant
from hypothesis import strategies as st
from src.models import Order

class OrderMathMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        # Инициализируем заказ со случайной валидной ценой
        self.order = Order(id="test_1", service_type="Test")
        self.order.update_price(100.0)  # Стартовая цена
        self.payment_ids = []

    # --- ПРАВИЛА (ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ) ---

    @rule(new_price=st.floats(min_value=0.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False))
    def action_update_price(self, new_price):
        try:
            self.order.update_price(new_price)
        except ValueError:
            # Ожидаемое исключение (например, если цена меньше полученной суммы)
            pass

    @rule(new_advance=st.floats(min_value=0.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False))
    def action_update_advance(self, new_advance):
        try:
            self.order.update_advance(new_advance)
        except ValueError:
            # Ожидаемое исключение (например, если аванс больше цены)
            pass

    @rule(payment_amount=st.floats(min_value=-1_000_000.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False))
    def action_add_payment(self, payment_amount):
        # Отсекаем нулевые платежи до вызова, так как они запрещены
        if abs(payment_amount) < 0.01:
            return

        try:
            payment = self.order.add_payment(payment_amount, "платеж")
            if payment:
                self.payment_ids.append(payment.id)
        except ValueError:
            # Ожидаемое исключение (превышение долга, или возврат больше полученного)
            pass

    @rule(payment_idx=st.integers(min_value=0, max_value=100))
    def action_delete_payment(self, payment_idx):
        if not self.payment_ids:
            return
        
        idx = payment_idx % len(self.payment_ids)
        p_id = self.payment_ids[idx]
        try:
            if self.order.delete_payment(p_id):
                self.payment_ids.pop(idx)
        except ValueError:
            # Невозможно удалить (например, сломает аванс)
            pass

    # --- ИНВАРИАНТЫ (НЕПРЕЛОЖНЫЕ ИСТИНЫ МАТЕМАТИКИ) ---

    @invariant()
    def check_debt_not_negative(self):
        assert self.order.debt >= -1e-9, f"Долг стал отрицательным: {self.order.debt}"

    @invariant()
    def check_advance_valid(self):
        assert self.order.advance >= -1e-9, f"Аванс стал отрицательным: {self.order.advance}"
        assert self.order.advance <= self.order.price + 1e-9, f"Аванс {self.order.advance} превысил цену {self.order.price}"

    @invariant()
    def check_total_received_not_exceeds_price(self):
        assert self.order.total_received <= self.order.price + 1e-9, f"Получено {self.order.total_received} больше цены {self.order.price}"

    @invariant()
    def check_advance_received_not_exceeds_advance(self):
        assert self.order.total_advance_received <= self.order.advance + 1e-9, f"Внесено аванса {self.order.total_advance_received} больше требуемого {self.order.advance}"

    @invariant()
    def check_remaining_debt_not_negative(self):
        assert self.order.remaining_debt >= -1e-9, f"Остаток долга отрицательный: {self.order.remaining_debt}"

    @invariant()
    def check_consistency(self):
        # Ручной пересчет должен совпадать с кэшированными значениями
        calc_total = sum(p.amount for p in self.order.payments)
        assert math.isclose(calc_total, self.order.total_received, abs_tol=1e-5), "Кэш total_received рассинхронизирован"

TestOrderMath = OrderMathMachine.TestCase
