import math
import uuid
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

# --- МОДЕЛИ ДАННЫХ ---

@dataclass
class ProjectFile:
    path: str
    name: str
    is_finished: bool = False
    is_folder: bool = False  # Флаг для обозначения папки

@dataclass
class Payment:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = ""  # "аванс", "платеж", "корректировка"
    amount: float = 0.0
    date: str = ""
    note: str = ""
    
    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'amount': self.amount,
            'date': self.date,
            'note': self.note
        }

@dataclass
class Order:
    id: str
    service_type: str
    price: float = 0.0
    currency: str = "RUB"  # Добавлено поле валюты
    advance: float = 0.0
    created_at: str = ""
    deadline: str = ""
    status: str = "В работе"
    is_deleted: bool = False  # Флаг корзины заказов
    files: List[ProjectFile] = field(default_factory=list)
    payments: List[Payment] = field(default_factory=list)
    # Кэши для агрегатов. Пересчитываются вручную через
    # ``_recalculate_totals`` при мутации ``payments``.
    # Это устраняет O(N) итерации на каждое обращение к ``debt``,
    # ``advance_debt`` и т.п. (важно для UI с 1000+ платежей).
    _total_received_cache: float = field(default=0.0, init=False, repr=False, compare=False)
    _total_advance_cache: float = field(default=0.0, init=False, repr=False, compare=False)
    _total_payments_cache: float = field(default=0.0, init=False, repr=False, compare=False)
    _total_corrections_cache: float = field(default=0.0, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Если платежи переданы в конструктор (например, из БД),
        # прогреваем кэш сразу, иначе все total_* будут нулями
        # до первого add/delete_payment.
        if self.payments:
            self._recalculate_totals()
            # Совместимость с add_payment: при загрузке из БД
            # платежи типа "аванс" автоматически поднимают advance.
            if self.total_advance_received > 0:
                self.advance = max(self.advance, self.total_advance_received)

    def _recalculate_totals(self) -> None:
        self._total_received_cache = sum(p.amount for p in self.payments)
        self._total_advance_cache = sum(
            p.amount for p in self.payments if p.type == "аванс"
        )
        self._total_payments_cache = sum(
            p.amount for p in self.payments if p.type == "платеж"
        )
        self._total_corrections_cache = sum(
            p.amount for p in self.payments if p.type == "корректировка"
        )

    @property
    def total_received(self) -> float:
        return self._total_received_cache

    @property
    def total_advance_received(self) -> float:
        return self._total_advance_cache

    @property
    def total_payments_received(self) -> float:
        return self._total_payments_cache

    @property
    def total_corrections_received(self) -> float:
        return self._total_corrections_cache

    @property
    def debt(self) -> float:
        """Текущий долг"""
        return max(0.0, self.price - self.total_received)

    @property
    def advance_debt(self) -> float:
        """Долг по авансу (если аванс не внесен полностью)"""
        return max(0.0, self.advance - self.total_advance_received)

    @property
    def remaining_debt(self) -> float:
        """Долг после аванса"""
        return max(0.0, self.price - self.advance - self.total_payments_received - self.total_corrections_received)

    @property
    def days_until_deadline(self) -> Optional[int]:
        """Количество дней до дедлайна"""
        if not self.deadline:
            return None
        try:
            deadline_date = datetime.strptime(self.deadline, "%d.%m.%Y")
            today = datetime.now()
            return (deadline_date - today).days
        except ValueError:
            return None

    def add_payment(
        self, amount: float, payment_type: str = "платеж", note: str = "", date: Optional[str] = None
    ) -> Optional[Payment]:
        """Добавить платеж.

        Валидация:
        * 0 запрещён;
        * значение должно быть конечным (NaN/Inf отклоняются);
        * положительный платёж не должен превышать остаток долга;
        * отрицательный платёж (возврат) не должен превышать полученную сумму.
          Раньше при переплате ``debt == 0`` и любой положительный платёж
          проходил проверку — теперь это тоже блокируется.
        """
        if not math.isfinite(amount):
            raise ValueError("Сумма платежа должна быть конечным числом")
        if amount == 0:
            raise ValueError("Сумма платежа не может быть нулевой")

        if amount > 0:
            if amount > self.debt:
                raise ValueError(
                    f"Сумма платежа ({amount}) превышает остаток долга ({self.debt})"
                )
        else:
            if abs(amount) > self.total_received:
                raise ValueError(
                    f"Сумма возврата ({abs(amount)}) превышает полученную сумму "
                    f"({self.total_received})"
                )
        
        if date is None:
            date = datetime.now().strftime("%d.%m.%Y %H:%M")
        
        payment = Payment(
            type=payment_type,
            amount=amount,
            date=date,
            note=note
        )
        
        self.payments.append(payment)
        self._recalculate_totals()

        # Если это аванс и сумма аванса изменилась, обновляем advance
        if payment_type == "аванс":
            self.advance = max(self.advance, self.total_advance_received)

        return payment

    def update_advance(self, new_advance: float):
        """Обновить сумму аванса"""
        if not math.isfinite(new_advance):
            raise ValueError("Аванс должен быть конечным числом")
        if new_advance < 0:
            raise ValueError("Аванс не может быть отрицательным")
        
        if new_advance > self.price:
            raise ValueError("Аванс не может превышать стоимость заказа")
        
        old_advance = self.advance
        diff = new_advance - old_advance
        
        if diff != 0:
            # Сначала проводим платеж, так как он может выбросить ValueError при валидации
            if diff > 0:
                self.add_payment(diff, "аванс", "Корректировка аванса")
            else:
                self.add_payment(diff, "аванс", "Уменьшение аванса")
            # Только после успешного платежа меняем значение
            self.advance = new_advance

    def update_price(self, new_price: float):
        """Обновить стоимость заказа с проверками.

        При уменьшении цены ниже аванса сначала уменьшаем ``total_received``
        через возврат аванса (negative payment), затем меняем ``advance``
        и ``price``. Раньше порядок был обратный, и ``add_payment`` откатывал
        ``self.advance`` через ``max(self.advance, total_advance_received)``.
        """
        if not math.isfinite(new_price):
            raise ValueError("Стоимость должна быть конечным числом")
        if new_price < 0:
            raise ValueError("Стоимость не может быть отрицательной")

        if new_price < self.advance:
            diff = self.advance - new_price
            self.add_payment(-diff, "аванс", "Возврат аванса из-за уменьшения стоимости")
            self.advance = new_price

        if new_price < self.total_received:
            raise ValueError(
                f"Новая стоимость ({new_price}) не может быть меньше уже "
                f"полученной суммы ({self.total_received})"
            )

        self.price = new_price

    def delete_payment(self, payment_id: str) -> bool:
        """Удалить платеж по ID"""
        for i, payment in enumerate(self.payments):
            if payment.id == payment_id:
                # Проверяем, не нарушит ли удаление логику аванса
                if payment.type == "аванс":
                    remaining_advance = self.total_advance_received - payment.amount
                    if remaining_advance < 0:
                        raise ValueError("Невозможно удалить платеж: аванс станет отрицательным")

                # Нельзя удалять возврат (отрицательный платеж), если после этого
                # полученная сумма превысит общую стоимость заказа.
                if payment.amount < 0:
                    new_total = self.total_received - payment.amount
                    if new_total > self.price:
                        raise ValueError("Невозможно удалить возврат: общая сумма превысит стоимость заказа")

                self.payments.pop(i)
                self._recalculate_totals()
                return True
        return False

@dataclass
class Client:
    id: str
    name: str
    email: str = ""  # Добавлено поле почты
    social_link: str = ""  # Добавлено поле ссылки
    avatar_path: str = ""  # Относительный путь до аватарки
    is_deleted: bool = False  # Флаг корзины
    notes: str = ""
    orders: List[Order] = field(default_factory=list)