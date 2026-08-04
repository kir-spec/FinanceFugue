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
    files: List[ProjectFile] = field(default_factory=list)
    payments: List[Payment] = field(default_factory=list)

    @property
    def total_received(self) -> float:
        """Общая сумма полученных платежей"""
        return sum(p.amount for p in self.payments)

    @property
    def total_advance_received(self) -> float:
        """Сумма полученных авансов"""
        return sum(p.amount for p in self.payments if p.type == "аванс")

    @property
    def total_payments_received(self) -> float:
        """Сумма полученных регулярных платежей"""
        return sum(p.amount for p in self.payments if p.type == "платеж")

    @property
    def total_corrections_received(self) -> float:
        """Сумма корректировок"""
        return sum(p.amount for p in self.payments if p.type == "корректировка")

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

    def add_payment(self, amount: float, payment_type: str = "платеж", note: str = "", date: str = None):
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
        
        # Если это аванс и сумма аванса изменилась, обновляем advance
        if payment_type == "аванс":
            self.advance = max(self.advance, self.total_advance_received)

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
            self.advance = new_advance
            # Если есть разница, добавляем коррекцию аванса
            if diff > 0:
                # Добавляем дополнительный аванс
                self.add_payment(diff, "аванс", "Корректировка аванса")
            else:
                # Уменьшаем аванс (возврат)
                self.add_payment(diff, "аванс", "Уменьшение аванса")

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
                
                self.payments.pop(i)
                return True
        return False

@dataclass
class Client:
    id: str
    name: str
    email: str = ""  # Добавлено поле почты
    social_link: str = ""  # Добавлено поле ссылки
    notes: str = ""
    orders: List[Order] = field(default_factory=list)