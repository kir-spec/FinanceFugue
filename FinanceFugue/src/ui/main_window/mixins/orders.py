import uuid
from datetime import datetime

from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QVBoxLayout,
)
from PySide6.QtCore import Qt

from ....models import Order
from ....logger import get_logger
from ....theme import (
    CANCEL_DIALOG_BUTTON_STYLE,
    DATE_EDIT_STYLE,
    NEW_ORDER_DIALOG_STYLESHEET,
    SUCCESS_DIALOG_BUTTON_STYLE,
)

logger = get_logger("MainWindow")


class OrdersMixin:
    def quick_add_order(self, client):
        self.current_client = client
        for i in range(self.cl_list.count()):
            item = self.cl_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == client.id:
                self.cl_list.setCurrentItem(item)
                self.select_client(item)
                break
        self.add_order()

    def add_order(self):
        if not self.current_client:
            QMessageBox.warning(self, "Внимание", "Сначала выберите клиента.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Новый заказ")
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(350)

        dialog.setStyleSheet(NEW_ORDER_DIALOG_STYLESHEET)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        service_label = QLabel("Тип услуги:")
        service_combo = QComboBox()
        service_combo.addItems(
            [
                "Монтаж звука",
                "Монтаж аудио",
                "Оркестровка",
                "Нотный набор",
                "Сведение",
                "Аранжировка",
                "Мастеринг",
                "Консультация",
            ]
        )
        form_layout.addRow(service_label, service_combo)

        price_layout = QHBoxLayout()
        price_edit = QLineEdit("0")

        currency_combo = QComboBox()
        currency_combo.addItems(["RUB", "USD", "EUR", "UAH"])
        currency_combo.setFixedWidth(70)

        price_layout.addWidget(price_edit)
        price_layout.addWidget(currency_combo)

        form_layout.addRow("Стоимость:", price_layout)

        deadline_label = QLabel("Срок выполнения:")
        deadline_edit = QDateEdit()
        deadline_edit.setCalendarPopup(True)
        deadline_edit.setDisplayFormat("dd.MM.yyyy")
        deadline_edit.setDate(datetime.now().date())
        deadline_edit.setStyleSheet(DATE_EDIT_STYLE)
        form_layout.addRow(deadline_label, deadline_edit)

        layout.addLayout(form_layout)

        finance_group = QGroupBox("Финансы")
        finance_layout = QFormLayout(finance_group)
        finance_layout.setSpacing(10)

        advance_label = QLabel("Аванс:")
        advance_edit = QLineEdit("0")
        finance_layout.addRow(advance_label, advance_edit)

        layout.addWidget(finance_group)
        layout.addStretch()

        buttons = QHBoxLayout()
        create_btn = QPushButton("Создать заказ")
        create_btn.setFixedWidth(140)
        create_btn.setStyleSheet(SUCCESS_DIALOG_BUTTON_STYLE)

        cancel_btn = QPushButton("Отмена")
        cancel_btn.setFixedWidth(100)
        cancel_btn.setStyleSheet(CANCEL_DIALOG_BUTTON_STYLE)

        buttons.addWidget(create_btn)
        buttons.addStretch()
        buttons.addWidget(cancel_btn)

        layout.addLayout(buttons)

        def create_order():
            try:
                price_text = price_edit.text().replace(",", ".").replace(" ", "")
                price = float(price_text or 0)
                if price < 0:
                    QMessageBox.warning(dialog, "Ошибка", "Стоимость не может быть отрицательной.")
                    return

                advance_text = advance_edit.text().replace(",", ".").replace(" ", "")
                advance = float(advance_text or 0)
                if advance < 0:
                    QMessageBox.warning(dialog, "Ошибка", "Аванс не может быть отрицательным.")
                    return
                if advance > price:
                    QMessageBox.warning(dialog, "Ошибка", "Аванс не может превышать стоимость.")
                    return

                new_order = Order(
                    id=str(uuid.uuid4()),
                    service_type=service_combo.currentText(),
                    price=price,
                    currency=currency_combo.currentText(),
                    advance=advance,
                    created_at=datetime.now().strftime("%d.%m.%Y %H:%M"),
                    deadline=deadline_edit.date().toString("dd.MM.yyyy"),
                    status="В работе",
                    payments=[],
                )

                if advance > 0:
                    new_order.add_payment(advance, "аванс", "Первоначальный аванс")

                self.current_client.orders.append(new_order)
                logger.info(
                    "Добавлен новый заказ для %s: %s (ID: %s)",
                    self.current_client.name,
                    new_order.service_type,
                    new_order.id,
                )
                self.render_client_profile()
                self.save_db()
                dialog.accept()

            except ValueError as e:
                QMessageBox.warning(dialog, "Ошибка", f"Ошибка ввода данных: {e}")

        def cancel():
            dialog.reject()

        create_btn.clicked.connect(create_order)
        cancel_btn.clicked.connect(cancel)

        service_combo.setFocus()
        dialog.exec()
