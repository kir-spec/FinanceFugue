import os
import shutil
import logging
from .logger import get_logger

logger = get_logger("Dialogs")
import glob
import json
import zipfile
import uuid
from pathlib import Path
from dataclasses import asdict
from datetime import datetime
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, 
    QListWidgetItem, QPushButton, QMessageBox, QWidget, 
    QLineEdit, QFileDialog, QCheckBox, QGroupBox, QRadioButton,
    QFormLayout, QTextEdit, QDialogButtonBox, QInputDialog, QDateEdit, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QAction

from .models import Order, ProjectFile, Client

# --- ДИАЛОГ ПЛАТЕЖЕЙ ---
class PaymentsDialog(QDialog):
    def __init__(self, order: Order, parent=None):
        super().__init__(parent)
        self.order = order
        self.setWindowTitle("История платежей")
        self.setFixedSize(600, 400)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
            }
            QLabel {
                color: #FFFFFF;
                font-size: 12px;
            }
            QListWidget {
                background-color: #252525;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #333333;
            }
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #3D3D3D;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #AAAAAA;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # Статистика
        stats_widget = QWidget()
        stats_layout = QHBoxLayout(stats_widget)
        
        curr = getattr(self.order, 'currency', 'RUB')
        stats = [
            ("Общая стоимость:", f"{self.order.price:.2f} {curr}", "#FFFFFF"),
            ("Аванс:", f"{self.order.advance:.2f} {curr}", "#FFD700"),
            ("Получено:", f"{self.order.total_received:.2f} {curr}", "#28A745"),
            ("Долг:", f"{self.order.debt:.2f} {curr}", "#FF4B2B" if self.order.debt > 0 else "#28A745")
        ]
        
        for title, value, color in stats:
            stat = QWidget()
            stat_layout = QVBoxLayout(stat)
            title_label = QLabel(title)
            title_label.setStyleSheet("color: #AAAAAA; font-size: 11px;")
            value_label = QLabel(value)
            value_label.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: bold;")
            stat_layout.addWidget(title_label)
            stat_layout.addWidget(value_label)
            stats_layout.addWidget(stat)
        
        stats_layout.addStretch()
        layout.addWidget(stats_widget)
        
        # Список платежей
        self.payments_list = QListWidget()
        layout.addWidget(self.payments_list)
        
        self.load_payments()
        
        # Кнопки
        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout(buttons_widget)
        
        self.delete_btn = QPushButton("Удалить выбранный платеж")
        self.delete_btn.clicked.connect(self.delete_payment)
        self.delete_btn.setEnabled(False)
        
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        
        buttons_layout.addWidget(self.delete_btn)
        buttons_layout.addStretch()
        buttons_layout.addWidget(close_btn)
        
        layout.addWidget(buttons_widget)
        
        self.payments_list.itemSelectionChanged.connect(self.on_selection_changed)
    
    def load_payments(self):
        self.payments_list.clear()
        
        # Группируем платежи по типам
        advance_payments = [p for p in self.order.payments if p.type == "аванс"]
        regular_payments = [p for p in self.order.payments if p.type == "платеж"]
        correction_payments = [p for p in self.order.payments if p.type == "корректировка"]
        
        if advance_payments:
            item = QListWidgetItem("=== АВАНСЫ ===")
            item.setForeground(QColor("#FFD700"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.payments_list.addItem(item)
            
            for payment in advance_payments:
                text = f"{payment.date} - {payment.amount:+.2f} ₽"
                if payment.note:
                    text += f" ({payment.note})"
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, payment.id)
                self.payments_list.addItem(item)
        
        if regular_payments:
            item = QListWidgetItem("=== ПЛАТЕЖИ ===")
            item.setForeground(QColor("#28A745"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.payments_list.addItem(item)
            
            for payment in regular_payments:
                text = f"{payment.date} - {payment.amount:+.2f} ₽"
                if payment.note:
                    text += f" ({payment.note})"
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, payment.id)
                self.payments_list.addItem(item)
        
        if correction_payments:
            item = QListWidgetItem("=== КОРРЕКТИРОВКИ ===")
            item.setForeground(QColor("#FFA500"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.payments_list.addItem(item)
            
            for payment in correction_payments:
                color = "#28A745" if payment.amount > 0 else "#FF4B2B"
                text = f"{payment.date} - {payment.amount:+.2f} ₽"
                if payment.note:
                    text += f" ({payment.note})"
                item = QListWidgetItem(text)
                item.setForeground(QColor(color))
                item.setData(Qt.ItemDataRole.UserRole, payment.id)
                self.payments_list.addItem(item)
        
        if not self.order.payments:
            item = QListWidgetItem("Платежей нет")
            item.setForeground(QColor("#888888"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.payments_list.addItem(item)
    
    def on_selection_changed(self):
        has_selection = len(self.payments_list.selectedItems()) > 0
        self.delete_btn.setEnabled(has_selection)
    
    def delete_payment(self):
        selected_items = self.payments_list.selectedItems()
        if not selected_items:
            return
        
        item = selected_items[0]
        payment_id = item.data(Qt.ItemDataRole.UserRole)
        
        if not payment_id:  # Это заголовок
            return
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Удаление платежа")
        msg_box.setText("Вы уверены, что хотите удалить этот платеж?")
        msg_box.setIcon(QMessageBox.Icon.Question)
        
        btn_delete = msg_box.addButton("Удалить", QMessageBox.ButtonRole.YesRole)
        btn_cancel = msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        
        msg_box.exec()
        
        if msg_box.clickedButton() == btn_delete:
            try:
                self.order.delete_payment(payment_id)
                self.load_payments()
                self.parent().save_db()
                QMessageBox.information(self, "Успех", "Платеж удален")
            except ValueError as e:
                logger.error(f"Ошибка удаления платежа: {e}")
                QMessageBox.warning(self, "Ошибка", str(e))

# --- ДИАЛОГ ИМПОРТА ИЗ ПАПКИ ---
class FolderImportDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Импорт клиентов из папки")
        self.setFixedSize(500, 400)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
            }
            QLabel {
                color: #FFFFFF;
                font-size: 12px;
            }
            QLineEdit {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #444444;
                padding: 6px;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #3D3D3D;
            }
            QListWidget {
                background-color: #252525;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                font-size: 12px;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # Выбор папки
        folder_layout = QHBoxLayout()
        folder_label = QLabel("Папка для импорта:")
        self.folder_edit = QLineEdit()
        self.folder_edit.setReadOnly(True)
        browse_btn = QPushButton("Обзор...")
        browse_btn.clicked.connect(self.browse_folder)
        
        folder_layout.addWidget(folder_label)
        folder_layout.addWidget(self.folder_edit, 1)
        folder_layout.addWidget(browse_btn)
        layout.addLayout(folder_layout)
        
        # Расширения файлов
        layout.addWidget(QLabel("Расширения файлов для импорта (через запятую):"))
        self.extensions_edit = QLineEdit(".mp3,.wav,.mid,.midi,.pdf,.doc,.docx,.txt")
        layout.addWidget(self.extensions_edit)
        
        # Группировка файлов
        layout.addWidget(QLabel("Группировать файлы по:"))
        group_layout = QHBoxLayout()
        self.group_by_name = QCheckBox("Имени файла (без расширения)")
        self.group_by_name.setChecked(True)
        self.group_by_type = QCheckBox("Типу файла")
        group_layout.addWidget(self.group_by_name)
        group_layout.addWidget(self.group_by_type)
        layout.addLayout(group_layout)
        
        # Предварительный просмотр
        layout.addWidget(QLabel("Будут созданы клиенты и заказы:"))
        self.preview_list = QListWidget()
        layout.addWidget(self.preview_list)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        scan_btn = QPushButton("Сканировать папку")
        scan_btn.clicked.connect(self.scan_folder)
        import_btn = QPushButton("Импортировать")
        import_btn.clicked.connect(self.accept)
        import_btn.setEnabled(False)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        
        buttons_layout.addWidget(scan_btn)
        buttons_layout.addStretch()
        buttons_layout.addWidget(import_btn)
        buttons_layout.addWidget(cancel_btn)
        
        layout.addLayout(buttons_layout)
        
        self.scan_btn = scan_btn
        self.import_btn = import_btn
        self.scan_results = []
    
    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку для импорта")
        if folder:
            self.folder_edit.setText(folder)
    
    def scan_folder(self):
        folder = self.folder_edit.text()
        if not folder or not os.path.exists(folder):
            QMessageBox.warning(self, "Ошибка", "Выберите существующую папку")
            return
        
        extensions = [ext.strip().lower() for ext in self.extensions_edit.text().split(",") if ext.strip()]
        if not extensions:
            QMessageBox.warning(self, "Ошибка", "Укажите расширения файлов")
            return
        
        self.preview_list.clear()
        self.scan_results = []
        
        # Сканируем только первую вложенность папок
        for client_folder in os.listdir(folder):
            client_path = os.path.join(folder, client_folder)
            if os.path.isdir(client_path):
                client_name = client_folder
                client_files = []
                
                # Собираем файлы с нужными расширениями из папки клиента
                for file in os.listdir(client_path):
                    file_path = os.path.join(client_path, file)
                    if os.path.isfile(file_path) and any(file.lower().endswith(ext) for ext in extensions):
                        client_files.append((file, file_path))
                
                if client_files:
                    # Группируем файлы
                    if self.group_by_name.isChecked():
                        grouped_files = {}
                        for file_name, file_path in client_files:
                            name_without_ext = os.path.splitext(file_name)[0]
                            if name_without_ext not in grouped_files:
                                grouped_files[name_without_ext] = []
                            grouped_files[name_without_ext].append((file_name, file_path))
                        
                        for group_name, files_list in grouped_files.items():
                            self.scan_results.append({
                                'client_name': client_name,
                                'order_name': group_name,
                                'files': files_list
                            })
                            self.preview_list.addItem(f"Клиент: {client_name} -> Заказ: {group_name} ({len(files_list)} файлов)")
                    else:
                        # Группируем по расширению
                        grouped_files = {}
                        for file_name, file_path in client_files:
                            ext = os.path.splitext(file_name)[1].lower()
                            if ext not in grouped_files:
                                grouped_files[ext] = []
                            grouped_files[ext].append((file_name, file_path))
                        
                        for ext, files_list in grouped_files.items():
                            self.scan_results.append({
                                'client_name': client_name,
                                'order_name': f"Заказ {ext}",
                                'files': files_list
                            })
                            self.preview_list.addItem(f"Клиент: {client_name} -> Заказ: {ext} ({len(files_list)} файлов)")
        
        if self.scan_results:
            self.import_btn.setEnabled(True)
            self.preview_list.addItem(f"\nВсего будет создано: {len(self.scan_results)} заказов")
        else:
            self.preview_list.addItem("Файлы для импорта не найдены")

# --- ДИАЛОГ ПЕРВОГО ЗАПУСКА ---
class FirstRunDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добро пожаловать в Pro Music CRM!")
        self.resize(800, 600)
        self.setMinimumSize(600, 500)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
            }
            QLabel {
                color: #FFFFFF;
                font-size: 12px;
            }
            QGroupBox {
                color: #FFFFFF;
                border: 2px solid #444444;
                border-radius: 5px;
                margin-top: 10px;
                font-size: 14px;
                font-weight: bold;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px 0 10px;
                color: #00D1FF;
            }
            QRadioButton {
                color: #DDDDDD;
                font-size: 12px;
                padding: 5px;
            }
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                padding: 10px 20px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #3D3D3D;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # Приветствие
        welcome_label = QLabel(
            "Добро пожаловать в Pro Music CRM!\n\n"
            "Для начала работы настройте параметры хранения данных."
        )
        welcome_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #00D1FF; padding: 20px;")
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(welcome_label)
        
        # Выбор места хранения базы данных
        db_group = QGroupBox("Хранение базы данных")
        db_layout = QVBoxLayout(db_group)
        
        db_layout.addWidget(QLabel("Выберите место для хранения базы данных:"))
        
        self.db_path_edit = QLineEdit(os.path.join(os.path.expanduser("~"), "ProMusicCRM"))
        self.db_path_edit.setReadOnly(True)
        
        browse_btn = QPushButton("Выбрать папку...")
        browse_btn.clicked.connect(self.browse_db_folder)
        
        db_path_layout = QHBoxLayout()
        db_path_layout.addWidget(self.db_path_edit, 1)
        db_path_layout.addWidget(browse_btn)
        db_layout.addLayout(db_path_layout)
        
        layout.addWidget(db_group)
        
        # Выбор способа хранения файлов
        files_group = QGroupBox("Хранение файлов клиентов")
        files_layout = QVBoxLayout(files_group)
        
        files_layout.addWidget(QLabel("Как вы хотите хранить файлы клиентов?"))
        
        self.file_storage_original = QRadioButton("Оставлять файлы на своих местах")
        self.file_storage_original.setChecked(True)
        self.file_storage_original.toggled.connect(self.on_storage_changed)
        
        files_layout.addWidget(self.file_storage_original)
        
        original_desc = QLabel(
            "• Файлы остаются там, где они есть\n"
            "• Программа будет ссылаться на оригинальные файлы\n"
            "• Экономит место на диске\n"
            "• При перемещении файлов ссылки могут сломаться"
        )
        original_desc.setStyleSheet("color: #AAAAAA; font-size: 11px; padding-left: 25px;")
        files_layout.addWidget(original_desc)
        
        self.file_storage_copy = QRadioButton("Копировать файлы в базу данных")
        self.file_storage_copy.toggled.connect(self.on_storage_changed)
        
        files_layout.addWidget(self.file_storage_copy)
        
        copy_desc = QLabel(
            "• Файлы копируются в папку базы данных\n"
            "• Все данные хранятся в одном месте\n"
            "• Занимает больше места на диске\n"
            "• Более надежно, файлы всегда доступны"
        )
        copy_desc.setStyleSheet("color: #AAAAAA; font-size: 11px; padding-left: 25px;")
        files_layout.addWidget(copy_desc)
        
        layout.addWidget(files_group)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        
        start_btn = QPushButton("Начать работу")
        start_btn.setStyleSheet("""
            QPushButton {
                background-color: #28A745;
                color: white;
                font-weight: bold;
            }
        """)
        start_btn.clicked.connect(self.accept)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(start_btn)
        
        layout.addLayout(buttons_layout)
    
    def browse_db_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку для базы данных")
        if folder:
            self.db_path_edit.setText(folder)
    
    def on_storage_changed(self):
        pass
    
    def get_settings(self):
        storage_mode = 'link' if self.file_storage_original.isChecked() else 'copy'
        
        return {
            'database_path': self.db_path_edit.text(),
            'file_storage_mode': storage_mode
        }

# --- ДИАЛОГ ЭКСПОРТА ЗАКАЗОВ КЛИЕНТА ---
class ClientOrdersExportDialog(QDialog):
    def __init__(self, client, parent=None):
        super().__init__(parent)
        self.client = client
        self.setWindowTitle("Экспорт заказов клиента")
        self.setFixedSize(500, 400)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
            }
            QLabel {
                color: #FFFFFF;
                font-size: 12px;
            }
            QCheckBox {
                color: #DDDDDD;
                font-size: 12px;
            }
            QListWidget {
                background-color: #252525;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                font-size: 12px;
            }
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #3D3D3D;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # Описание
        layout.addWidget(QLabel("Выберите заказы для экспорта:"))
        
        # Список заказов с чекбоксами
        self.orders_list = QListWidget()
        for order in self.client.orders:
            item = QListWidgetItem(f"{order.service_type} (ID: {order.id[:8]}, создан: {order.created_at})")
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, order)
            self.orders_list.addItem(item)
        
        layout.addWidget(self.orders_list)
        
        # Опции экспорта
        options_widget = QWidget()
        options_layout = QVBoxLayout(options_widget)
        
        self.include_files_cb = QCheckBox("Включить файлы заказов в экспорт")
        self.include_files_cb.setChecked(True)
        options_layout.addWidget(self.include_files_cb)
        
        layout.addWidget(options_widget)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        
        select_all_btn = QPushButton("Выбрать все")
        select_all_btn.clicked.connect(self.select_all)
        
        deselect_all_btn = QPushButton("Снять выделение")
        deselect_all_btn.clicked.connect(self.deselect_all)
        
        export_btn = QPushButton("Экспорт")
        export_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        
        buttons_layout.addWidget(select_all_btn)
        buttons_layout.addWidget(deselect_all_btn)
        buttons_layout.addStretch()
        buttons_layout.addWidget(export_btn)
        buttons_layout.addWidget(cancel_btn)
        
        layout.addLayout(buttons_layout)
    
    def select_all(self):
        for i in range(self.orders_list.count()):
            item = self.orders_list.item(i)
            item.setCheckState(Qt.CheckState.Checked)
    
    def deselect_all(self):
        for i in range(self.orders_list.count()):
            item = self.orders_list.item(i)
            item.setCheckState(Qt.CheckState.Unchecked)
    
    def get_export_data(self):
        selected_orders = []
        for i in range(self.orders_list.count()):
            item = self.orders_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected_orders.append(item.data(Qt.ItemDataRole.UserRole))
        
        return {
            'selected_orders': selected_orders,
            'include_files': self.include_files_cb.isChecked()
        }

# --- ДИАЛОГ НАСТРОЕК КЛИЕНТА ---
class ClientSettingsDialog(QDialog):
    def __init__(self, client, parent=None):
        super().__init__(parent)
        self.client = client
        self.parent_app = parent
        self.setWindowTitle("Настройки клиента")
        self.setFixedWidth(400)
        
        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; }
            QLabel { color: #FFFFFF; font-size: 12px; }
            QLineEdit, QTextEdit {
                background-color: #333333; color: #FFFFFF;
                border: 1px solid #444444; padding: 6px; border-radius: 3px;
            }
            QPushButton {
                background-color: #2D2D2D; color: #FFFFFF;
                border: 1px solid #3D3D3D; padding: 8px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #3D3D3D; }
        """)
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.name_edit = QLineEdit(client.name)
        form.addRow("Имя:", self.name_edit)
        
        self.email_edit = QLineEdit(client.email)
        form.addRow("Email:", self.email_edit)
        
        self.link_edit = QLineEdit(client.social_link)
        form.addRow("Соц. сеть:", self.link_edit)
        
        self.notes_edit = QTextEdit(client.notes)
        self.notes_edit.setMaximumHeight(80)
        form.addRow("Заметка:", self.notes_edit)
        
        layout.addLayout(form)
        
        # Группа инструментов экспорта
        export_group = QGroupBox("Инструменты экспорта")
        export_group.setStyleSheet("""
            QGroupBox {
                color: #00D1FF;
                border: 1px solid #444444;
                border-radius: 5px;
                margin-top: 15px;
                padding-top: 15px;
                font-weight: bold;
            }
        """)
        export_layout = QVBoxLayout(export_group)
        
        # Кнопка "Экспорт файлов" клиента
        export_files_btn = QPushButton("📁 Экспорт файлов")
        export_files_btn.clicked.connect(self.parent_app.export_client_files)
        
        # Кнопка "Экспорт заказов" клиента
        export_orders_btn = QPushButton("📊 Экспорт заказов")
        export_orders_btn.clicked.connect(self.parent_app.export_client_orders)
        
        export_layout.addWidget(export_files_btn)
        export_layout.addWidget(export_orders_btn)
        layout.addWidget(export_group)
        
        # Удаление клиента
        del_btn = QPushButton("🗑️ Удалить клиента")
        del_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #DC3545;
                border: 1px solid #DC3545;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
                margin-top: 15px;
            }
            QPushButton:hover {
                background-color: #DC3545;
                color: white;
            }
        """)
        del_btn.clicked.connect(self.delete_client)
        layout.addWidget(del_btn)
        
        # Кнопки ОК/Отмена
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        
    def delete_client(self):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Подтверждение удаления")
        msg_box.setText(f"Вы уверены, что хотите удалить клиента '{self.client.name}'?")
        msg_box.setInformativeText("Все заказы и файлы клиента будут также удалены.")
        msg_box.setIcon(QMessageBox.Icon.Warning)
        
        btn_delete = msg_box.addButton("Удалить клиента", QMessageBox.ButtonRole.YesRole)
        btn_cancel = msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        
        msg_box.exec()
        
        if msg_box.clickedButton() == btn_delete:
            logger.info(f"Удаление клиента: {self.client.name} (ID: {self.client.id})")
            self.parent_app.clients.remove(self.client)
            self.parent_app.current_client = None
            self.parent_app.clear_profile_layout()
            self.parent_app.refresh_list()
            self.parent_app.save_db()
            self.reject() # Close settings dialog

# --- ДИАЛОГ НАСТРОЕК ---
class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Настройки системы")
        self.setFixedWidth(280)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
            }
            QLabel {
                color: #FFFFFF;
                font-size: 12px;
                padding: 5px;
            }
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                padding: 8px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #3D3D3D;
            }
            QPushButton:pressed {
                background-color: #4D4D4D;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        db_label = QLabel("Управление базой данных:")
        db_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        db_label.setStyleSheet("color: #00D1FF; font-weight: bold; font-size: 13px;")
        layout.addWidget(db_label)
        
        btn_db_location = QPushButton("Выбрать место хранения базы данных")
        btn_db_location.clicked.connect(self.change_database_location)
        
        btn_imp_folder = QPushButton("Импорт клиентов из папки")
        btn_imp_folder.clicked.connect(self.parent.import_from_folder)
        
        btn_exp = QPushButton("Экспорт базы данных (JSON)")
        btn_exp.clicked.connect(self.parent.export_json)
        
        btn_imp = QPushButton("Импорт базы данных (JSON)")
        btn_imp.clicked.connect(self.parent.import_json_file)
        
        btn_full = QPushButton("Экспорт базы данных + Файлы (ZIP)")
        btn_full.clicked.connect(self.parent.export_full_backup)

        # Управление настройками
        settings_group = QGroupBox("Настройки")
        settings_group.setAlignment(Qt.AlignmentFlag.AlignCenter)
        settings_layout = QVBoxLayout(settings_group)
        
        btn_backup_settings = QPushButton("Создать копию настроек сейчас")
        btn_backup_settings.clicked.connect(self.manual_backup_settings)
        
        btn_restore_settings = QPushButton("Восстановить настройки")
        btn_restore_settings.clicked.connect(self.restore_settings_dialog)
        
        settings_layout.addWidget(btn_backup_settings)
        settings_layout.addWidget(btn_restore_settings)
        
        layout.addWidget(btn_db_location)
        layout.addSpacing(10)
        layout.addWidget(btn_imp_folder)
        layout.addSpacing(10)
        layout.addWidget(btn_exp)
        layout.addWidget(btn_imp)
        layout.addWidget(btn_full)
        layout.addSpacing(10)
        layout.addWidget(settings_group)
        layout.addSpacing(20)
        
        size_lbl = QLabel(f"Размер базы: {self.parent.get_database_size()}")
        size_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        size_lbl.setStyleSheet("color: #888888; font-size: 11px;")
        
        count_lbl = QLabel(f"Клиентов: {len(self.parent.clients)}")
        count_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        count_lbl.setStyleSheet("color: #888888; font-size: 11px;")
        
        layout.addWidget(size_lbl)
        layout.addWidget(count_lbl)
        
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
    
    def manual_backup_settings(self):
        """Ручное создание бэкапа с подтверждением"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Резервное копирование")
        msg_box.setText("Вы собираетесь создать резервную копию настроек приложения.")
        msg_box.setInformativeText(
            "Будет создан JSON файл с текущими путями к базе данных и режимом хранения файлов.\n"
            "Это позволит восстановить конфигурацию в случае сбоя или переноса.\n\n"
            "Продолжить?"
        )
        msg_box.setIcon(QMessageBox.Icon.Question)
        
        btn_yes = msg_box.addButton("Создать копию", QMessageBox.ButtonRole.YesRole)
        btn_no = msg_box.addButton("Отмена", QMessageBox.ButtonRole.NoRole)
        
        msg_box.exec()
        
        if msg_box.clickedButton() == btn_yes:
            self.parent.backup_settings()
            logger.info("Пользователь вручную создал резервную копию настроек")
            QMessageBox.information(self, "Успех", "Резервная копия настроек успешно создана в папке 'settings_backups'.")

    def change_database_location(self):
        """Изменяет место хранения базы данных"""
        folder = QFileDialog.getExistingDirectory(self, "Выберите новое место для базы данных")
        if not folder:
            return
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Перенос базы данных")
        msg_box.setText("Как вы хотите хранить файлы при переносе базы?")
        msg_box.setInformativeText(
            "Вы можете оставить файлы там, где они сейчас, "
            "или скопировать их в новую папку вместе с базой данных."
        )
        msg_box.setIcon(QMessageBox.Icon.Question)
        
        # Добавляем кнопки с понятным текстом на русском
        btn_leave = msg_box.addButton("Оставить как есть", QMessageBox.ButtonRole.NoRole)
        btn_move = msg_box.addButton("Скопировать в новую базу", QMessageBox.ButtonRole.YesRole)
        btn_cancel = msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        
        msg_box.exec()
        
        clicked_button = msg_box.clickedButton()
        
        if clicked_button == btn_cancel:
            return
            
        move_files = (clicked_button == btn_move)
        
        try:
            # Сохраняем текущую базу
            self.parent.save_db()
            
            # Создаем новую папку для базы
            new_db_path = Path(folder) / "pro_database.json"
            
            if move_files:
                # Создаем структуру папок для файлов
                files_folder = Path(folder) / "attached_files"
                files_folder.mkdir(exist_ok=True)
                
                # Копируем файлы
                for client in self.parent.clients:
                    for order in client.orders:
                        for file in order.files:
                            if os.path.exists(file.path):
                                # Создаем новую структуру
                                order_folder = files_folder / order.id
                                order_folder.mkdir(exist_ok=True)
                                
                                new_file_path = order_folder / file.name
                                shutil.copy2(file.path, new_file_path)
                                file.path = str(new_file_path)
            
            # Копируем базу данных
            shutil.copy2(self.parent.storage.path, new_db_path)
            
            # Обновляем путь к базе данных
            self.parent.storage.path = new_db_path
            self.parent.app_settings['database_path'] = folder
            self.parent.save_settings()
            
            QMessageBox.information(
                self,
                "Успех",
                f"База данных успешно перенесена в:\n{folder}\n\n"
                f"{'Файлы были скопированы в новую базу данных' if move_files else 'Файлы остались на своих местах'}"
            )
            
        except Exception as e:
            logger.error(f"Ошибка переноса базы данных: {e}", exc_info=True)
            QMessageBox.critical(self, "Ошибка", f"Не удалось перенести базу данных: {e}")

    def restore_settings_dialog(self):
        """Диалог восстановления настроек из бэкапа"""
        backup_dir = "settings_backups"
        if not os.path.exists(backup_dir):
            QMessageBox.information(self, "Инфо", "Папка с резервными копиями пуста.")
            return

        backups = sorted(glob.glob(os.path.join(backup_dir, "crm_settings_*.json")), reverse=True)
        if not backups:
            QMessageBox.information(self, "Инфо", "Нет доступных резервных копий.")
            return

        items = [os.path.basename(b) for b in backups]
        item, ok = QInputDialog.getItem(self, "Восстановление настроек",
                                      "Выберите файл резервной копии:", items, 0, False)
        
        if ok and item:
            selected_backup = os.path.join(backup_dir, item)
            try:
                with open(selected_backup, "r", encoding="utf-8") as f:
                    new_settings = json.load(f)
                
                self.parent.app_settings = new_settings
                self.parent.save_settings()
                
                QMessageBox.information(self, "Успех",
                                      "Настройки восстановлены. Перезапустите приложение для применения изменений.")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось восстановить настройки: {e}")
