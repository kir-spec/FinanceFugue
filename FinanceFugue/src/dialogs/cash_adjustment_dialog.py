import uuid
from datetime import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QMessageBox, QRadioButton, QButtonGroup, QGroupBox
)
from PySide6.QtCore import Qt

from ..models import Client, Order, Payment
from ..theme import DIALOG_STYLESHEET, COLOR_ACCENT, COLOR_PRIMARY, COLOR_SUCCESS


class CashAdjustmentDialog(QDialog):
    """Диалог для ручной корректировки кассы / баланса."""
    def __init__(self, main_window, parent=None):
        super().__init__(parent or main_window)
        self.window = main_window
        self.setWindowTitle("💵 Корректировка кассы / баланса")
        self.setFixedSize(480, 460)
        self.setStyleSheet(DIALOG_STYLESHEET + f"""
            QLabel {{ color: #FFFFFF; font-size: 11pt; }}
            QLineEdit, QComboBox, QTextEdit {{
                background-color: #2D2D2D; color: #FFFFFF;
                border: 1px solid #4D4D4D; border-radius: 4px; padding: 6px;
                font-size: 11pt;
            }}
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{
                border: 1px solid {COLOR_ACCENT};
            }}
            QRadioButton {{
                color: #FFFFFF; font-size: 11pt; spacing: 6px;
            }}
            QPushButton#applyBtn {{
                background-color: {COLOR_PRIMARY}; color: #FFFFFF;
                font-weight: bold; padding: 10px; border-radius: 4px; font-size: 11pt;
            }}
            QPushButton#applyBtn:hover {{
                background-color: #1084E3;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # 1. Выбор валюты
        cur_layout = QHBoxLayout()
        cur_layout.addWidget(QLabel("Валюта кассы:"))
        self.currency_combo = QComboBox()
        
        # Собираем все используемые валюты в базе
        used_currencies = set()
        for c in getattr(self.window, "clients", []):
            if getattr(c, "is_deleted", False):
                continue
            for o in c.orders:
                if not getattr(o, "is_deleted", False) and o.currency:
                    used_currencies.add(o.currency.upper())
        
        if not used_currencies:
            used_currencies = {"RUB", "USD", "EUR"}
        else:
            used_currencies.update(["RUB", "USD", "EUR"])

        for curr in sorted(used_currencies):
            self.currency_combo.addItem(curr, curr)
        
        # По умолчанию RUB
        rub_idx = self.currency_combo.findData("RUB")
        if rub_idx >= 0:
            self.currency_combo.setCurrentIndex(rub_idx)

        self.currency_combo.currentIndexChanged.connect(self._update_current_cash_display)
        cur_layout.addWidget(self.currency_combo)
        layout.addLayout(cur_layout)

        # Текущий остаток
        self.cash_lbl = QLabel()
        self.cash_lbl.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {COLOR_ACCENT}; padding: 4px 0;")
        layout.addWidget(self.cash_lbl)

        # 2. Режим корректировки
        mode_box = QGroupBox("Способ изменения")
        mode_layout = QVBoxLayout(mode_box)
        
        self.rb_set_total = QRadioButton("Установить новый точный остаток кассы")
        self.rb_delta = QRadioButton("Внести (+) или Списать (-) определенную сумму")
        self.rb_set_total.setChecked(True)

        self.btn_group = QButtonGroup(self)
        self.btn_group.addButton(self.rb_set_total, 1)
        self.btn_group.addButton(self.rb_delta, 2)
        self.btn_group.buttonClicked.connect(self._on_mode_changed)

        mode_layout.addWidget(self.rb_set_total)
        mode_layout.addWidget(self.rb_delta)
        layout.addWidget(mode_box)

        # Поле ввода суммы
        self.val_label = QLabel("Новый остаток кассы:")
        self.val_edit = QLineEdit()
        self.val_edit.setPlaceholderText("Например: 15000.00")
        layout.addWidget(self.val_label)
        layout.addWidget(self.val_edit)

        # Причина / Комментарий
        layout.addWidget(QLabel("Причина / Назначение корректировки:"))
        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("Например: Снятие наличных, инвентаризация, стартовый остаток...")
        self.note_edit.setText("Ручная корректировка остатка кассы")
        layout.addWidget(self.note_edit)

        # Пояснение
        hint_lbl = QLabel("ℹ️ Корректировка будет зафиксирована как финансовая операция с типом «корректировка» и отобразится в отчетах.")
        hint_lbl.setStyleSheet("color: #AAAAAA; font-size: 9pt;")
        hint_lbl.setWordWrap(True)
        layout.addWidget(hint_lbl)

        layout.addStretch()

        # Кнопки управления
        btn_box = QHBoxLayout()
        self.btn_apply = QPushButton("Применить корректировку")
        self.btn_apply.setObjectName("applyBtn")
        self.btn_apply.clicked.connect(self._apply_adjustment)
        
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(self.btn_apply)
        layout.addLayout(btn_box)

        self._update_current_cash_display()

    def _get_current_cash_for_currency(self, currency: str) -> float:
        total = 0.0
        for c in getattr(self.window, "clients", []):
            if getattr(c, "is_deleted", False):
                continue
            for o in c.orders:
                if getattr(o, "is_deleted", False):
                    continue
                if (o.currency or "RUB").upper() == currency.upper():
                    total += o.total_received
        return total

    def _update_current_cash_display(self):
        curr = self.currency_combo.currentData() or "RUB"
        cash = self._get_current_cash_for_currency(curr)
        self.cash_lbl.setText(f"Текущая касса: {cash:,.2f} {curr}")

    def _on_mode_changed(self):
        if self.rb_set_total.isChecked():
            self.val_label.setText("Новый остаток кассы:")
            self.val_edit.setPlaceholderText("Например: 15000.00")
        else:
            self.val_label.setText("Сумма изменения (+ пополнение, - списание):")
            self.val_edit.setPlaceholderText("Например: -500 или +2000")

    def _apply_adjustment(self):
        curr = self.currency_combo.currentData() or "RUB"
        curr_cash = self._get_current_cash_for_currency(curr)
        
        raw_val = self.val_edit.text().strip().replace(" ", "").replace(",", ".")
        try:
            val = float(raw_val)
        except ValueError:
            QMessageBox.warning(self, "Ошибка", "Введите корректное числовое значение суммы.")
            return

        if self.rb_set_total.isChecked():
            delta = val - curr_cash
        else:
            delta = val

        if abs(delta) < 0.001:
            QMessageBox.information(self, "Корректировка", "Сумма кассы не изменилась.")
            self.accept()
            return

        note = self.note_edit.text().strip() or "Корректировка кассы"
        
        # Находим или создаем клиента и заказ для учета системных корректировок
        clients = getattr(self.window, "clients", [])
        
        # Ищем специального клиента "🏛 Корректировки кассы" или создаем его
        adj_client = next((c for c in clients if c.name == "🏛 Корректировки кассы" and not c.is_deleted), None)
        if not adj_client:
            adj_client = Client(
                id=str(uuid.uuid4()),
                name="🏛 Корректировки кассы",
                notes="Служебные корректировки баланса и снятия наличных",
                orders=[]
            )
            clients.append(adj_client)

        # Ищем заказ в нужной валюте
        adj_order = next((o for o in adj_client.orders if o.currency.upper() == curr.upper() and not o.is_deleted), None)
        if not adj_order:
            adj_order = Order(
                id=str(uuid.uuid4()),
                service_type=f"Корректировка ({curr})",
                price=0.0,
                currency=curr,
                created_at=datetime.now().strftime("%d.%m.%Y %H:%M"),
                status="Завершен",
                payments=[]
            )
            adj_client.orders.append(adj_order)

        # Создаем запись корректировки
        payment = Payment(
            id=str(uuid.uuid4()),
            type="корректировка",
            amount=delta,
            date=datetime.now().strftime("%d.%m.%Y %H:%M"),
            note=note
        )
        adj_order.add_payment(payment)

        # Сохраняем БД и обновляем UI
        try:
            self.window.save_db()
            if hasattr(self.window, "update_dash"):
                self.window.update_dash()
            if hasattr(self.window, "refresh_list"):
                self.window.refresh_list()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить корректировку:\n{e}")
            return

        new_cash = self._get_current_cash_for_currency(curr)
        action_desc = "пополнена на" if delta > 0 else "уменьшена на"
        QMessageBox.information(
            self,
            "Касса скорректирована",
            f"Касса ({curr}) успешно {action_desc} {abs(delta):,.2f} {curr}.\n\n"
            f"Новый остаток: {new_cash:,.2f} {curr}\n"
            f"Операция сохранена с типом «корректировка»."
        )
        self.accept()
