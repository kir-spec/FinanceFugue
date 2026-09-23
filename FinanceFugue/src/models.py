import math
from decimal import Decimal
import uuid
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

# Хелперы конвертации
def to_cents(amount_float: float) -> int:
    if not math.isfinite(amount_float):
        return 0
    return int(Decimal(str(amount_float)).quantize(Decimal("0.01"), rounding="ROUND_HALF_UP") * 100)

def from_cents(cents: int) -> float:
    return float(Decimal(str(cents)) / Decimal("100"))

# --- МОДЕЛИ ДАННЫХ ---

@dataclass
class ProjectFile:
    path: str
    name: str
    is_finished: bool = False
    is_folder: bool = False

@dataclass
class Payment:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = ""  # "аванс", "платеж", "корректировка"
    amount_cents: int = 0
    date: str = ""
    note: str = ""
    idempotency_key: Optional[str] = None
    is_reversal: bool = False
    reversal_of_id: Optional[str] = None
    
    # Legacy support
    amount: float = field(default=0.0, repr=False, compare=False)
    
    def __post_init__(self):
        if self.amount != 0.0 and self.amount_cents == 0:
            self.amount_cents = to_cents(self.amount)
            self.amount = 0.0

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'amount_cents': self.amount_cents,
            'date': self.date,
            'note': self.note,
            'idempotency_key': self.idempotency_key,
            'is_reversal': self.is_reversal,
            'reversal_of_id': self.reversal_of_id
        }

@dataclass
class Order:
    id: str
    service_type: str
    price_cents: int = 0
    currency: str = "RUB"
    advance_cents: int = 0
    created_at: str = ""
    deadline: str = ""
    status: str = "В работе"
    is_deleted: bool = False
    is_archived: bool = False
    version: int = 1
    files: List[ProjectFile] = field(default_factory=list)
    payments: List[Payment] = field(default_factory=list)

    # Legacy support
    price: float = field(default=0.0, repr=False, compare=False)
    advance: float = field(default=0.0, repr=False, compare=False)

    _total_received_cache: int = field(default=0, init=False, repr=False, compare=False)
    _total_advance_cache: int = field(default=0, init=False, repr=False, compare=False)
    _total_payments_cache: int = field(default=0, init=False, repr=False, compare=False)
    _total_corrections_cache: int = field(default=0, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.price != 0.0 and self.price_cents == 0:
            self.price_cents = to_cents(self.price)
            self.price = 0.0
        if self.advance != 0.0 and self.advance_cents == 0:
            self.advance_cents = to_cents(self.advance)
            self.advance = 0.0

        if self.payments:
            self._recalculate_totals()
            if self.total_advance_received_cents > 0:
                self.advance_cents = max(self.advance_cents, self.total_advance_received_cents)

    def _recalculate_totals(self) -> None:
        self._total_received_cache = sum(p.amount_cents for p in self.payments)
        self._total_advance_cache = sum(p.amount_cents for p in self.payments if p.type == "аванс")
        self._total_payments_cache = sum(p.amount_cents for p in self.payments if p.type == "платеж")
        self._total_corrections_cache = sum(p.amount_cents for p in self.payments if p.type == "корректировка")

    @property
    def total_received_cents(self) -> int:
        return self._total_received_cache

    @property
    def total_advance_received_cents(self) -> int:
        return self._total_advance_cache

    @property
    def total_payments_received_cents(self) -> int:
        return self._total_payments_cache

    @property
    def total_corrections_received_cents(self) -> int:
        return self._total_corrections_cache

    @property
    def debt_cents(self) -> int:
        return max(0, self.price_cents - self.total_received_cents)

    @property
    def advance_debt_cents(self) -> int:
        return max(0, self.advance_cents - self.total_advance_received_cents)

    @property
    def remaining_debt_cents(self) -> int:
        return max(0, self.price_cents - self.advance_cents - self.total_payments_received_cents - self.total_corrections_received_cents)

    @property
    def days_until_deadline(self) -> Optional[int]:
        if not self.deadline:
            return None
        try:
            deadline_date = datetime.strptime(self.deadline, "%d.%m.%Y")
            today = datetime.now()
            return (deadline_date - today).days
        except ValueError:
            return None

    def add_payment(
        self, amount_cents: int, payment_type: str = "платеж", note: str = "", date: Optional[str] = None, idempotency_key: Optional[str] = None
    ) -> Payment:
        if amount_cents == 0:
            raise ValueError("Сумма платежа не может быть нулевой")

        if amount_cents > 0:
            if amount_cents > self.debt_cents:
                raise ValueError(f"Сумма платежа превышает остаток долга")
        else:
            if abs(amount_cents) > self.total_received_cents:
                raise ValueError(f"Сумма возврата превышает полученную сумму")
        
        if date is None:
            date = datetime.now().strftime("%d.%m.%Y %H:%M")
        
        payment = Payment(
            type=payment_type,
            amount_cents=amount_cents,
            date=date,
            note=note,
            idempotency_key=idempotency_key
        )
        
        self.payments.append(payment)
        self._recalculate_totals()
        self.version += 1

        if payment_type == "аванс":
            self.advance_cents = max(self.advance_cents, self.total_advance_received_cents)

        return payment

    def update_advance(self, new_advance_cents: int):
        if new_advance_cents < 0:
            raise ValueError("Аванс не может быть отрицательным")
        
        if new_advance_cents > self.price_cents:
            raise ValueError("Аванс не может превышать стоимость заказа")
        
        diff = new_advance_cents - self.advance_cents
        if diff != 0:
            if diff > 0:
                self.add_payment(diff, "аванс", "Корректировка аванса")
            else:
                self.add_payment(diff, "аванс", "Уменьшение аванса")
            self.advance_cents = new_advance_cents
            self.version += 1

    def update_price(self, new_price_cents: int):
        if new_price_cents < 0:
            raise ValueError("Стоимость не может быть отрицательной")

        if new_price_cents < self.advance_cents:
            diff = self.advance_cents - new_price_cents
            self.add_payment(-diff, "аванс", "Возврат аванса из-за уменьшения стоимости")
            self.advance_cents = new_price_cents

        if new_price_cents < self.total_received_cents:
            raise ValueError("Новая стоимость не может быть меньше уже полученной суммы")

        self.price_cents = new_price_cents
        self.version += 1

    def reverse_payment(self, payment_id: str, idempotency_key: Optional[str] = None) -> bool:
        original = next((p for p in self.payments if p.id == payment_id and not p.is_reversal), None)
        if not original:
            return False

        if any(p.reversal_of_id == payment_id for p in self.payments):
            raise ValueError("Платеж уже сторнирован")

        reversal_amount = -original.amount_cents
        
        if original.type == "аванс" and reversal_amount < 0:
            if self.total_advance_received_cents + reversal_amount < 0:
                raise ValueError("Невозможно сторнировать: аванс станет отрицательным")

        reversal = Payment(
            type=original.type,
            amount_cents=reversal_amount,
            date=datetime.now().strftime("%d.%m.%Y %H:%M"),
            note=f"СТОРНО: {original.note}",
            is_reversal=True,
            reversal_of_id=payment_id,
            idempotency_key=idempotency_key
        )
        self.payments.append(reversal)
        self._recalculate_totals()
        self.version += 1
        return True

@dataclass
class Client:
    id: str
    name: str
    email: str = ""
    social_link: str = ""
    avatar_path: str = ""
    is_deleted: bool = False
    is_archived: bool = False
    notes: str = ""
    requisites: str = ""
    version: int = 1
    orders: List[Order] = field(default_factory=list)