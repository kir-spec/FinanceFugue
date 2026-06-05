"""Финансы и платежи для карточки заказа."""
from datetime import datetime

from PySide6.QtWidgets import (
    QLabel, QMessageBox, QLineEdit, QDialog, QVBoxLayout, QFormLayout, QComboBox, QDateEdit,
    QDialogButtonBox, QTextEdit,
)
from PySide6.QtGui import QDoubleValidator

from ..dialogs import PaymentsDialog
from ..logger import get_logger
from ..theme import (
    ADD_PAYMENT_DIALOG_STYLESHEET,
    DATE_EDIT_STYLE,
    deadline_date_edit_style,
    payment_status_style,
)

logger = get_logger("Widgets")


class OrderFinancialMixin:
    def format_number(self, num):
        """Форматирует число без точек"""
        if num == int(num):
            return str(int(num))
        return str(num).rstrip('0').rstrip('.') if '.' in str(num) else str(num)

    def sync_price(self):
        try:
            text = self.cost_edit.text()
            # Заменяем запятую на точку и удаляем пробелы
            text = text.replace(',', '.').replace(' ', '')
            if not text:
                new_price = 0.0
            else:
                new_price = float(text)
            
            if new_price < 0:
                QMessageBox.warning(self._bridge.window, "Ошибка", "Стоимость не может быть отрицательной")
                self.cost_edit.setText(self.format_number(self.order.price))
                return
            
            if new_price < self.order.total_received:
                msg_box = QMessageBox(self._bridge.window)
                msg_box.setWindowTitle("Изменение стоимости")
                msg_box.setText(f"Новая стоимость ({new_price:.2f} {self._currency_sym()}) меньше уже полученной суммы ({self.order.total_received:.2f} {self._currency_sym()}).")
                msg_box.setInformativeText(f"Это приведет к необходимости вернуть {self.order.total_received - new_price:.2f} {self._currency_sym()}\nПродолжить?")
                msg_box.setIcon(QMessageBox.Icon.Question)
                
                btn_yes = msg_box.addButton("Да", QMessageBox.ButtonRole.YesRole)
                btn_no = msg_box.addButton("Нет", QMessageBox.ButtonRole.NoRole)
                
                msg_box.exec()
                
                if msg_box.clickedButton() == btn_yes:
                    # Рассчитываем разницу для возврата
                    diff = self.order.total_received - new_price
                    # Создаем возврат
                    self.order.add_payment(-diff, "корректировка", "Возврат из-за уменьшения стоимости заказа")
                    self.order.price = new_price
                    
                    # Обновляем аванс, если он теперь больше цены
                    if self.order.advance > new_price:
                        self.order.advance = new_price
                        self.advance_edit.setText(self.format_number(new_price))
                else:
                    self.cost_edit.setText(self.format_number(self.order.price))
                    return
            
            elif new_price < self.order.advance:
                # Новая стоимость меньше аванса
                diff = self.order.advance - new_price
                msg_box = QMessageBox(self._bridge.window)
                msg_box.setWindowTitle("Изменение стоимости")
                msg_box.setText(f"Новая стоимость ({new_price:.2f} {self._currency_sym()}) меньше аванса ({self.order.advance:.2f} {self._currency_sym()}).")
                msg_box.setInformativeText(f"Это приведет к возврату части аванса в размере {diff:.2f} {self._currency_sym()}\nПродолжить?")
                msg_box.setIcon(QMessageBox.Icon.Question)
                
                btn_yes = msg_box.addButton("Да", QMessageBox.ButtonRole.YesRole)
                btn_no = msg_box.addButton("Нет", QMessageBox.ButtonRole.NoRole)
                
                msg_box.exec()
                
                if msg_box.clickedButton() == btn_yes:
                    # Уменьшаем аванс до новой цены
                    self.order.advance = new_price
                    self.advance_edit.setText(self.format_number(new_price))
                    # Добавляем возврат аванса
                    self.order.add_payment(-diff, "аванс", "Возврат части аванса из-за уменьшения стоимости")
                    self.order.price = new_price
                else:
                    self.cost_edit.setText(self.format_number(self.order.price))
                    return
            else:
                # Обычное изменение цены
                self.order.price = new_price
            
            self.update_financial_display()
            self._bridge.request_save()
        except ValueError:
            # Если введено не число, оставляем старое значение
            self.cost_edit.setText(self.format_number(self.order.price))

    def sync_advance(self):
        try:
            text = self.advance_edit.text()
            # Заменяем запятую на точку и удаляем пробелы
            text = text.replace(',', '.').replace(' ', '')
            if not text:
                new_advance = 0.0
            else:
                new_advance = float(text)
            
            if new_advance < 0:
                QMessageBox.warning(self._bridge.window, "Ошибка", "Аванс не может быть отрицательным")
                self.advance_edit.setText(self.format_number(self.order.advance))
                return
            
            if new_advance > self.order.price:
                QMessageBox.warning(self._bridge.window, "Ошибка", "Аванс не может превышать стоимость заказа")
                self.advance_edit.setText(self.format_number(self.order.advance))
                return
            
            diff = new_advance - self.order.advance
            
            if diff != 0:
                if diff > 0:
                    # Увеличение аванса
                    self.order.add_payment(diff, "аванс", "Дополнительный аванс")
                else:
                    # Уменьшение аванса (возврат)
                    msg_box = QMessageBox(self._bridge.window)
                    msg_box.setWindowTitle("Возврат аванса")
                    msg_box.setText(
                        f"Вы уменьшаете аванс на {abs(diff):.2f} {self._currency_sym()}. "
                        "Это создаст возврат средств."
                    )
                    msg_box.setInformativeText("Продолжить?")
                    msg_box.setIcon(QMessageBox.Icon.Question)
                    
                    btn_yes = msg_box.addButton("Да", QMessageBox.ButtonRole.YesRole)
                    btn_no = msg_box.addButton("Нет", QMessageBox.ButtonRole.NoRole)
                    
                    msg_box.exec()
                    
                    if msg_box.clickedButton() == btn_yes:
                        self.order.add_payment(diff, "аванс", "Возврат части аванса")
                    else:
                        self.advance_edit.setText(self.format_number(self.order.advance))
                        return
            
            self.order.advance = new_advance
            self.update_financial_display()
            self._bridge.request_save()
            
        except ValueError:
            # Если введено не число, оставляем старое значение
            self.advance_edit.setText(self.format_number(self.order.advance))

    def sync_debt(self):
        try:
            text = self.debt_edit.text()
            # Заменяем запятую на точку и удаляем пробелы
            text = text.replace(',', '.').replace(' ', '')
            if not text:
                new_debt = 0.0
            else:
                new_debt = float(text)
            
            if new_debt < 0:
                QMessageBox.warning(self._bridge.window, "Ошибка", "Долг не может быть отрицательным")
                self.debt_edit.setText(self.format_number(self.order.debt))
                return
            
            if new_debt > self.order.price:
                QMessageBox.warning(self._bridge.window, "Ошибка", "Долг не может превышать стоимость")
                self.debt_edit.setText(self.format_number(self.order.debt))
                return
            
            # Рассчитываем новую полученную сумму на основе долга
            new_received = self.order.price - new_debt
            diff = new_received - self.order.total_received
            
            if diff != 0:
                if diff > 0:
                    # Добавляем корректировочный платеж
                    self.order.add_payment(diff, "корректировка", "Корректировка полученной суммы")
                else:
                    # Возврат средств
                    msg_box = QMessageBox(self._bridge.window)
                    msg_box.setWindowTitle("Возврат средств")
                    msg_box.setText(f"Вы создаете возврат средств на сумму {abs(diff):.2f} {self._currency_sym()}")
                    msg_box.setInformativeText("Продолжить?")
                    msg_box.setIcon(QMessageBox.Icon.Question)
                    
                    btn_yes = msg_box.addButton("Да", QMessageBox.ButtonRole.YesRole)
                    btn_no = msg_box.addButton("Нет", QMessageBox.ButtonRole.NoRole)
                    
                    msg_box.exec()
                    
                    if msg_box.clickedButton() == btn_yes:
                        self.order.add_payment(diff, "корректировка", "Корректировка (возврат)")
                    else:
                        self.debt_edit.setText(self.format_number(self.order.debt))
                        return
            
            self.update_financial_display()
            self._bridge.request_save()
            
        except ValueError:
            QMessageBox.warning(self._bridge.window, "Ошибка", "Введите числовое значение")
            self.debt_edit.setText(self.format_number(self.order.debt))

    def sync_deadline(self, qdate):
        self.order.deadline = qdate.toString("dd.MM.yyyy")
        logger.info(f"Изменен срок заказа {self.order.id}: {self.order.deadline}")
        self.update_deadline_color()
        self._bridge.request_save()

    def sync_order_date(self, qdate):
        new_date = qdate.toString("dd.MM.yyyy")
        # Сохраняем время если оно было
        if " " in self.order.created_at:
            time_part = self.order.created_at.split()[1]
            self.order.created_at = f"{new_date} {time_part}"
        else:
            self.order.created_at = f"{new_date} 00:00"
        logger.info(f"Изменена дата заказа {self.order.id}: {self.order.created_at}")
        self._bridge.request_save()

    def update_deadline_color(self):
        """Обновление цвета поля дедлайна в зависимости от оставшегося времени"""
        if not self.order.deadline:
            self.deadline_edit.setStyleSheet(DATE_EDIT_STYLE)
            return

        try:
            deadline_date = datetime.strptime(self.order.deadline, "%d.%m.%Y")
            days_left = (deadline_date - datetime.now()).days

            if days_left <= 3:
                style = deadline_date_edit_style("#FF4B2B", "#FF4B2B", tinted_dropdown=True)
            elif days_left < 5:
                style = deadline_date_edit_style("#FFA500", "#FFA500", text="#000000", tinted_dropdown=True)
            else:
                style = deadline_date_edit_style("#28A745", "#28A745", tinted_dropdown=True)
            self.deadline_edit.setStyleSheet(style)
        except ValueError:
            self.deadline_edit.setStyleSheet(DATE_EDIT_STYLE)

    def update_financial_display(self):
        # Обновляем поля ввода
        self.cost_edit.setText(self.format_number(self.order.price))
        self.advance_edit.setText(self.format_number(self.order.advance))
        self.debt_edit.setText(self.format_number(self.order.debt))
        
        # Обновляем статусы
        self.update_payment_status()

    def update_order_status(self, state):
        self.order.status = "Завершен" if state else "В работе"
        self._bridge.request_save()

    def update_payment_status(self):
        # Если стоимость 0, статус не показываем (или пишем "Бесплатно/Не задано")
        if self.order.price == 0:
             self.payment_status.setText("")
             return

        if self.order.debt <= 0:
            self.payment_status.setText("✅ Оплачено полностью")
            self.payment_status.setStyleSheet(payment_status_style("#28A745"))
        elif self.order.total_received >= self.order.advance:
            self.payment_status.setText("⚠ Аванс погашен, остался долг")
            self.payment_status.setStyleSheet(payment_status_style("#FFA500"))
        elif self.order.total_received > 0:
            self.payment_status.setText("⚠ Частично оплачено")
            self.payment_status.setStyleSheet(payment_status_style("#FFA500"))
        else:
            self.payment_status.setText("❌ Не оплачено")
            self.payment_status.setStyleSheet(payment_status_style("#FF4B2B"))

    def add_payment_dialog(self):
        dialog = QDialog(self._bridge.window)
        dialog.setWindowTitle("Добавить платеж")
        dialog.setFixedWidth(400)
        
        dialog.setStyleSheet(ADD_PAYMENT_DIALOG_STYLESHEET)
        
        layout = QVBoxLayout(dialog)
        
        form_layout = QFormLayout()
        
        # Тип платежа
        type_label = QLabel("Тип платежа:")
        type_combo = QComboBox()
        type_combo.addItems(["платеж", "аванс", "корректировка"])
        form_layout.addRow(type_label, type_combo)
        
        # Сумма
        amount_label = QLabel("Сумма:")
        amount_edit = QLineEdit()
        # Разрешаем отрицательные значения для возвратов
        amount_validator = QDoubleValidator(-9999999, 9999999, 2)
        amount_edit.setValidator(amount_validator)
        form_layout.addRow(amount_label, amount_edit)
        
        # Дата платежа
        date_label = QLabel("Дата:")
        date_edit = QDateEdit()
        date_edit.setDate(datetime.now().date())
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("dd.MM.yyyy")
        form_layout.addRow(date_label, date_edit)
        
        # Примечание
        note_label = QLabel("Примечание:")
        note_edit = QTextEdit()
        note_edit.setMaximumHeight(60)
        form_layout.addRow(note_label, note_edit)
        
        layout.addLayout(form_layout)
        
        # Кнопки
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                amount_text = amount_edit.text().replace(',', '.')
                if not amount_text:
                    QMessageBox.warning(self._bridge.window, "Ошибка", "Введите сумму платежа")
                    return
                    
                amount = float(amount_text)
                note = note_edit.toPlainText()
                date = date_edit.date().toString("dd.MM.yyyy")
                payment_type = type_combo.currentText()
                
                self.order.add_payment(amount, payment_type, note, date + " 00:00")
                logger.info(f"Добавлен платеж: {amount} ({payment_type}) для заказа {self.order.service_type}")
                self.update_financial_display()
                self._bridge.request_save()
                
                if amount > 0:
                    QMessageBox.information(
                        self._bridge.window,
                        "Платеж добавлен",
                        f"Платеж на сумму {amount:.2f} {self._currency_sym()} успешно добавлен.\n"
                        f"Получено: {self.order.total_received:.2f} {self._currency_sym()}\n"
                        f"Остаток долга: {self.order.debt:.2f} {self._currency_sym()}"
                    )
                else:
                    QMessageBox.information(
                        self._bridge.window,
                        "Возврат добавлен",
                        f"Возврат на сумму {abs(amount):.2f} {self._currency_sym()} успешно добавлен.\n"
                        f"Получено: {self.order.total_received:.2f} {self._currency_sym()}\n"
                        f"Остаток долга: {self.order.debt:.2f} {self._currency_sym()}"
                    )
                
            except ValueError as e:
                QMessageBox.warning(self._bridge.window, "Ошибка", str(e))

    def show_payments_history(self):
        dialog = PaymentsDialog(self.order, self._bridge.window)
        dialog.exec()
        self.update_financial_display()

    def delete_order(self):
        if not self.order:
            return
        
        msg_box = QMessageBox(self._bridge.window)
        msg_box.setWindowTitle("Удаление заказа")
        msg_box.setText(f"Вы уверены, что хотите удалить заказ '{self.order.service_type}'?")
        msg_box.setIcon(QMessageBox.Icon.Question)
        
        btn_delete = msg_box.addButton("Удалить", QMessageBox.ButtonRole.YesRole)
        btn_cancel = msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        
        msg_box.exec()
        
        if msg_box.clickedButton() == btn_delete:
            logger.info(f"Удаление заказа: {self.order.service_type} (ID: {self.order.id})")
            # Находим клиента, которому принадлежит заказ
            for client in self._bridge.clients:
                if self.order in client.orders:
                    client.orders.remove(self.order)
                    break
            
            # Перерисовываем профиль
            self._bridge.request_profile_refresh()
            self._bridge.request_save()
