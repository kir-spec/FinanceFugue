import sys
import json
import uuid
import os
import zipfile
import shutil
import platform
import subprocess
from dataclasses import dataclass, asdict, field
from pathlib import Path
from datetime import datetime, timedelta
from typing import List

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox,
    QListWidget, QListWidgetItem, QMessageBox, QScrollArea,
    QFrame, QFileDialog, QCheckBox, QDialog, QFormLayout, QTextEdit,
    QInputDialog, QGroupBox, QGridLayout, QDialogButtonBox,
    QSizePolicy, QMenu, QDateEdit
)
from PyQt6.QtGui import QFont, QIcon, QDoubleValidator, QPalette, QColor, QAction
from PyQt6.QtCore import Qt, pyqtSignal

# --- МОДЕЛИ ДАННЫХ ---
@dataclass
class ProjectFile:
    path: str
    name: str
    is_finished: bool = False

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
    advance: float = 0.0
    created_at: str = ""
    deadline: str = ""
    status: str = "В работе"
    files: List[ProjectFile] = field(default_factory=list)
    payments: List[Payment] = field(default_factory=list)

    @property
    def total_received(self) -> float:
        """Общая сумма полученных платежей"""
        return sum(p.amount for p in self.payments if p.amount > 0)

    @property
    def total_advance_received(self) -> float:
        """Сумма полученных авансов"""
        return sum(p.amount for p in self.payments if p.type == "аванс")

    @property
    def total_payments_received(self) -> float:
        """Сумма полученных регулярных платежей"""
        return sum(p.amount for p in self.payments if p.type == "платеж")

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
        return max(0.0, self.price - self.advance - self.total_payments_received)

    @property
    def days_until_deadline(self) -> int:
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
        """Добавить платеж"""
        if amount == 0:
            raise ValueError("Сумма платежа не может быть нулевой")
        
        # Проверяем, что платеж не превышает задолженность
        if amount > 0:
            if amount > self.debt:
                raise ValueError(f"Сумма платежа ({amount}) превышает остаток долга ({self.debt})")
        else:
            if abs(amount) > self.total_received:
                raise ValueError(f"Сумма возврата ({abs(amount)}) превышает полученную сумму ({self.total_received})")
        
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

    def update_total_received(self, new_total: float):
        """Обновить общую полученную сумму с созданием корректировочного платежа"""
        if new_total < 0:
            raise ValueError("Полученная сумма не может быть отрицательной")
        
        if new_total > self.price:
            raise ValueError("Полученная сумма не может превышать стоимость")
        
        current_total = self.total_received
        diff = new_total - current_total
        
        if diff != 0:
            if diff > 0:
                # Добавляем корректировочный платеж
                self.add_payment(diff, "корректировка", "Корректировка полученной суммы")
            else:
                # Добавляем корректировочный возврат
                self.add_payment(diff, "корректировка", "Корректировка (возврат)")

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
    notes: str = ""
    orders: List[Order] = field(default_factory=list)

# --- ХРАНИЛИЩЕ ---
class CRMStorage:
    def __init__(self, filename="pro_database.json"):
        self.path = Path(filename)

    def load(self) -> List[Client]:
        if not self.path.exists(): 
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
                clients = []
                for c_dict in data:
                    orders = []
                    for o in c_dict.get('orders', []):
                        files = [ProjectFile(**fi) for fi in o.get('files', [])]
                        
                        payments = []
                        for p in o.get('payments', []):
                            payment = Payment(
                                id=p.get('id', str(uuid.uuid4())),
                                type=p.get('type', 'платеж'),
                                amount=p.get('amount', 0.0),
                                date=p.get('date', ''),
                                note=p.get('note', '')
                            )
                            payments.append(payment)
                        
                        order = Order(
                            id=o.get('id', str(uuid.uuid4())),
                            service_type=o.get('service_type', ''),
                            price=o.get('price', 0.0),
                            advance=o.get('advance', 0.0),
                            created_at=o.get('created_at', ''),
                            deadline=o.get('deadline', ''),
                            status=o.get('status', 'В работе'),
                            files=files,
                            payments=payments
                        )
                        orders.append(order)
                    
                    client = Client(
                        id=c_dict.get('id', str(uuid.uuid4())),
                        name=c_dict.get('name', ''),
                        notes=c_dict.get('notes', ''),
                        orders=orders
                    )
                    clients.append(client)
                return clients
        except Exception as e:
            print(f"Ошибка загрузки базы данных: {e}")
            return []

    def save(self, clients: List[Client]):
        try:
            temp_path = self.path.with_suffix('.tmp')
            data = []
            for c in clients:
                c_dict = asdict(c)
                orders_data = []
                for order in c.orders:
                    order_dict = {
                        'id': order.id,
                        'service_type': order.service_type,
                        'price': order.price,
                        'advance': order.advance,
                        'created_at': order.created_at,
                        'deadline': order.deadline,
                        'status': order.status,
                        'files': [asdict(f) for f in order.files],
                        'payments': [p.to_dict() for p in order.payments]
                    }
                    orders_data.append(order_dict)
                c_dict['orders'] = orders_data
                data.append(c_dict)
            
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            if self.path.exists():
                os.remove(self.path)
            os.rename(temp_path, self.path)
        except Exception as e:
            print(f"Ошибка сохранения базы данных: {e}")
            QMessageBox.critical(None, "Ошибка", f"Не удалось сохранить базу данных: {e}")

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
        
        stats = [
            ("Общая стоимость:", f"{self.order.price:.2f} ₽", "#FFFFFF"),
            ("Аванс:", f"{self.order.advance:.2f} ₽", "#FFD700"),
            ("Получено:", f"{self.order.total_received:.2f} ₽", "#28A745"),
            ("Долг:", f"{self.order.debt:.2f} ₽", "#FF4B2B" if self.order.debt > 0 else "#28A745")
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
        
        reply = QMessageBox.question(
            self,
            "Удаление платежа",
            "Вы уверены, что хотите удалить этот платеж?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.order.delete_payment(payment_id)
                self.load_payments()
                self.parent().save_db()
                QMessageBox.information(self, "Успех", "Платеж удален")
            except ValueError as e:
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
        
        # Сканируем папки
        for root, dirs, files in os.walk(folder):
            # Клиент - это название папки (не корневой)
            if root == folder:
                continue
                
            client_name = os.path.basename(root)
            client_files = []
            
            # Собираем файлы с нужными расширениями
            for file in files:
                if any(file.lower().endswith(ext) for ext in extensions):
                    file_path = os.path.join(root, file)
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

# --- ДИАЛОГ НАСТРОЕК ---
class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Настройки системы")
        self.setFixedWidth(400)
        
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
        
        layout.addWidget(QLabel("Управление базой данных:"))
        
        btn_imp_folder = QPushButton("Импорт клиентов из папки")
        btn_imp_folder.clicked.connect(self.parent.import_from_folder)
        
        btn_exp = QPushButton("Экспорт базы данных (JSON)")
        btn_exp.clicked.connect(self.parent.export_json)
        
        btn_imp = QPushButton("Импорт базы данных (JSON)")
        btn_imp.clicked.connect(self.parent.import_json_file)
        
        btn_full = QPushButton("Экспорт базы данных + Файлы (ZIP)")
        btn_full.clicked.connect(self.parent.export_full_backup)
        
        layout.addWidget(btn_imp_folder)
        layout.addSpacing(10)
        layout.addWidget(btn_exp)
        layout.addWidget(btn_imp)
        layout.addWidget(btn_full)
        layout.addSpacing(20)
        
        layout.addWidget(QLabel(f"Размер базы данных: {self.parent.get_database_size()}"))
        layout.addWidget(QLabel(f"Количество клиентов: {len(self.parent.clients)}"))
        
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

# --- ВИДЖЕТЫ ---
class FileItemWidget(QWidget):
    statusChanged = pyqtSignal()
    renameRequested = pyqtSignal(str, str)  # old_path, new_name
    
    def __init__(self, file_obj: ProjectFile, parent_app):
        super().__init__()
        self.file_obj = file_obj
        self.parent_app = parent_app
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        
        # Убрал чекбокс слева - оставил только название файла
        self.name_label = QLabel(file_obj.name)
        self.name_label.setStyleSheet("color: #DDDDDD; font-size: 12px;")
        self.name_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.name_label.customContextMenuRequested.connect(self.show_context_menu)
        
        # Кнопка открытия файла
        btn_open = QPushButton("Открыть")
        btn_open.setFixedWidth(70)
        btn_open.clicked.connect(self.open_file)
        btn_open.setStyleSheet("""
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                padding: 4px;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #3D3D3D;
            }
        """)
        
        layout.addWidget(self.name_label, 1)
        layout.addWidget(btn_open)
    
    def show_context_menu(self, pos):
        menu = QMenu(self)
        rename_action = QAction("Переименовать", self)
        rename_action.triggered.connect(self.rename_file)
        menu.addAction(rename_action)
        menu.exec(self.name_label.mapToGlobal(pos))
    
    def rename_file(self):
        new_name, ok = QInputDialog.getText(
            self,
            "Переименование файла",
            "Введите новое имя файла:",
            QLineEdit.EchoMode.Normal,
            self.file_obj.name
        )
        
        if ok and new_name.strip() and new_name != self.file_obj.name:
            old_path = self.file_obj.path
            old_dir = os.path.dirname(old_path)
            new_path = os.path.join(old_dir, new_name.strip())
            
            try:
                # Переименовываем файл в файловой системе
                os.rename(old_path, new_path)
                
                # Обновляем объект файла
                self.file_obj.path = new_path
                self.file_obj.name = new_name.strip()
                self.name_label.setText(new_name.strip())
                
                # Сохраняем изменения
                self.parent_app.save_db()
                QMessageBox.information(self, "Успех", "Файл переименован")
                
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось переименовать файл: {e}")
    
    def open_file(self):
        try:
            if os.path.exists(self.file_obj.path):
                if platform.system() == "Windows":
                    os.startfile(self.file_obj.path)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", self.file_obj.path])
                else:
                    subprocess.Popen(["xdg-open", self.file_obj.path])
            else:
                QMessageBox.warning(self, "Файл не найден", f"Файл {self.file_obj.name} не существует.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть файл: {e}")

class OrderWidget(QFrame):
    def __init__(self, order: Order, parent_app):
        super().__init__()
        self.order = order
        self.parent_app = parent_app
        self.init_ui()
        self.update_deadline_color()

    def init_ui(self):
        self.setStyleSheet("""
            QFrame#OrderCard { 
                background-color: #2A2A2A; 
                border-radius: 8px; 
                border: 1px solid #3D3D3D; 
                margin-bottom: 10px; 
            }
        """)
        self.setObjectName("OrderCard")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(8)

        # Заголовок
        header = QHBoxLayout()
        
        # Простая стрелка для сворачивания (убрал фон)
        self.toggle_btn = QPushButton("▼")
        self.toggle_btn.setFixedSize(20, 20)
        self.toggle_btn.clicked.connect(self.toggle_contents)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #FFFFFF;
                border: none;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                color: #00D1FF;
            }
        """)

        title = QLabel(f"Заказ: {self.order.service_type}")
        title.setStyleSheet("font-weight: bold; color: #00D1FF; font-size: 14px;")
        
        # Чекбокс "Выполнен"
        self.status_cb = QCheckBox("Выполнен")
        self.status_cb.setChecked(self.order.status == "Завершен")
        self.status_cb.stateChanged.connect(self.update_order_status)
        self.status_cb.setStyleSheet("""
            QCheckBox {
                color: #DDDDDD;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #555555;
                background: #222222;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #28A745;
                background: #28A745;
            }
        """)

        # Кнопка "История платежей"
        self.payments_history_btn = QPushButton("История платежей")
        self.payments_history_btn.setFixedWidth(120)
        self.payments_history_btn.clicked.connect(self.show_payments_history)
        self.payments_history_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078D7;
                color: white;
                padding: 6px 8px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056A3;
            }
        """)

        # Простой красный крестик для удаления
        delete_btn = QPushButton("✕")
        delete_btn.setFixedSize(20, 20)
        delete_btn.clicked.connect(self.delete_order)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #FF4444;
                border: none;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                color: #FF0000;
            }
        """)

        header.addWidget(self.toggle_btn)
        header.addWidget(title)
        header.addWidget(self.status_cb)
        header.addWidget(self.payments_history_btn)
        header.addStretch()
        header.addWidget(delete_btn)
        self.main_layout.addLayout(header)

        # Содержимое
        self.content = QWidget()
        self.c_layout = QVBoxLayout(self.content)
        self.c_layout.setSpacing(8)
        
        # Информация (ID и дата создания)
        info_widget = QWidget()
        info_layout = QHBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        
        id_label = QLabel(f"ID: {self.order.id[:8]}...")
        id_label.setStyleSheet("color: #888888; font-size: 10px;")
        info_layout.addWidget(id_label)
        
        if self.order.created_at:
            date_label = QLabel(f"Создан: {self.order.created_at}")
            date_label.setStyleSheet("color: #888888; font-size: 10px;")
            info_layout.addWidget(date_label)
        
        info_layout.addStretch()
        self.c_layout.addWidget(info_widget)
        
        # Финансовый блок
        financial_widget = QWidget()
        financial_layout = QGridLayout(financial_widget)
        financial_layout.setContentsMargins(0, 5, 0, 5)
        financial_layout.setSpacing(8)
        financial_layout.setVerticalSpacing(10)
        
        # Первая строка
        cost_label = QLabel("Стоимость:")
        cost_label.setStyleSheet("color: #CCCCCC; font-size: 12px; padding-right: 5px;")
        cost_label.setFixedWidth(70)
        
        self.cost_edit = QLineEdit(self.format_number(self.order.price))
        self.cost_edit.setFixedWidth(120)
        self.cost_edit.textChanged.connect(self.sync_price)
        self.cost_edit.setStyleSheet("""
            QLineEdit {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #444444;
                padding: 5px 8px;
                border-radius: 3px;
                font-size: 12px;
            }
        """)
        
        advance_label = QLabel("Аванс:")
        advance_label.setStyleSheet("color: #CCCCCC; font-size: 12px; padding-right: 5px;")
        advance_label.setFixedWidth(50)
        
        self.advance_edit = QLineEdit(self.format_number(self.order.advance))
        self.advance_edit.setFixedWidth(120)
        self.advance_edit.editingFinished.connect(self.sync_advance)
        self.advance_edit.setStyleSheet("""
            QLineEdit {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #444444;
                padding: 5px 8px;
                border-radius: 3px;
                font-size: 12px;
            }
        """)
        
        # Вторая строка - кнопка "Добавить платеж" и поле "Долг"
        add_payment_btn = QPushButton("Добавить платеж")
        add_payment_btn.setFixedWidth(120)
        add_payment_btn.clicked.connect(self.add_payment_dialog)
        add_payment_btn.setStyleSheet("""
            QPushButton {
                background-color: #28A745;
                color: white;
                font-weight: bold;
                padding: 6px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        
        debt_label = QLabel("Долг:")
        debt_label.setStyleSheet("color: #CCCCCC; font-size: 12px; padding-right: 5px;")
        debt_label.setFixedWidth(50)
        
        self.debt_edit = QLineEdit(self.format_number(self.order.debt))
        self.debt_edit.setFixedWidth(120)
        self.debt_edit.editingFinished.connect(self.sync_debt)
        self.debt_edit.setStyleSheet("""
            QLineEdit {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #444444;
                padding: 5px 8px;
                border-radius: 3px;
                font-size: 12px;
            }
        """)
        
        # Расположение элементов в сетке
        financial_layout.addWidget(cost_label, 0, 0, Qt.AlignmentFlag.AlignRight)
        financial_layout.addWidget(self.cost_edit, 0, 1)
        financial_layout.addWidget(advance_label, 0, 2, Qt.AlignmentFlag.AlignRight)
        financial_layout.addWidget(self.advance_edit, 0, 3)
        
        financial_layout.addWidget(add_payment_btn, 1, 0, 1, 2, Qt.AlignmentFlag.AlignLeft)
        financial_layout.addWidget(debt_label, 1, 2, Qt.AlignmentFlag.AlignRight)
        financial_layout.addWidget(self.debt_edit, 1, 3)
        
        self.c_layout.addWidget(financial_widget)

        # Прогресс оплаты
        self.payment_progress = QLabel()
        self.update_payment_progress()
        self.c_layout.addWidget(self.payment_progress)

        # Статус оплаты
        self.payment_status = QLabel()
        self.update_payment_status()
        self.c_layout.addWidget(self.payment_status)

        # Дедлайн с цветовой индикацией
        deadline_widget = QWidget()
        deadline_layout = QHBoxLayout(deadline_widget)
        deadline_layout.setContentsMargins(0, 0, 0, 0)
        
        deadline_label = QLabel("Срок:")
        deadline_label.setStyleSheet("color: #CCCCCC; font-size: 12px; padding-right: 10px;")
        self.deadline_edit = QLineEdit(self.order.deadline)
        self.deadline_edit.textChanged.connect(self.sync_deadline)
        self.deadline_edit.setStyleSheet("""
            QLineEdit {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #444444;
                padding: 5px 8px;
                border-radius: 3px;
                font-size: 12px;
            }
        """)
        self.deadline_edit.setFixedWidth(150)
        
        deadline_layout.addWidget(deadline_label)
        deadline_layout.addWidget(self.deadline_edit)
        deadline_layout.addStretch()
        
        self.c_layout.addWidget(deadline_widget)
        
        # Файлы
        files_label = QLabel("Файлы:")
        files_label.setStyleSheet("font-weight: bold; margin-top: 10px; color: #CCCCCC; font-size: 13px;")
        self.c_layout.addWidget(files_label)
        
        if self.order.files:
            for f in self.order.files:
                fw = FileItemWidget(f, self.parent_app)
                fw.statusChanged.connect(self.parent_app.save_db)
                self.c_layout.addWidget(fw)
        else:
            no_files = QLabel("Файлы не добавлены")
            no_files.setStyleSheet("color: #888888; font-style: italic; font-size: 11px; padding: 5px;")
            self.c_layout.addWidget(no_files)

        # Кнопки управления файлами
        btns = QHBoxLayout()
        b_f = QPushButton("+ Добавить файл")
        b_f.clicked.connect(self.add_file)
        b_f.setStyleSheet("""
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                padding: 6px 10px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #3D3D3D;
            }
        """)
        
        b_z = QPushButton("📦 Создать ZIP")
        b_z.clicked.connect(self.pack_zip)
        b_z.setStyleSheet("""
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                padding: 6px 10px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #3D3D3D;
            }
        """)
        
        btns.addWidget(b_f)
        btns.addWidget(b_z)
        btns.addStretch()
        
        self.c_layout.addLayout(btns)

        self.main_layout.addWidget(self.content)

    def format_number(self, num):
        """Форматирует число без точек"""
        if num == int(num):
            return str(int(num))
        return str(num).rstrip('0').rstrip('.') if '.' in str(num) else str(num)

    def toggle_contents(self):
        visible = self.content.isVisible()
        self.content.setVisible(not visible)
        self.toggle_btn.setText("▶" if visible else "▼")

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
                QMessageBox.warning(self, "Ошибка", "Стоимость не может быть отрицательной")
                self.cost_edit.setText(self.format_number(self.order.price))
                return
            
            if new_price < self.order.total_received:
                QMessageBox.warning(self, "Ошибка", "Стоимость не может быть меньше уже полученной суммы")
                self.cost_edit.setText(self.format_number(self.order.price))
                return
            
            self.order.price = new_price
            
            # Проверяем аванс
            if self.order.advance > new_price:
                self.order.advance = new_price
                self.advance_edit.setText(self.format_number(new_price))
            
            self.update_financial_display()
            self.parent_app.save_db()
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
                QMessageBox.warning(self, "Ошибка", "Аванс не может быть отрицательным")
                self.advance_edit.setText(self.format_number(self.order.advance))
                return
            
            if new_advance > self.order.price:
                QMessageBox.warning(self, "Ошибка", "Аванс не может превышать стоимость заказа")
                self.advance_edit.setText(self.format_number(self.order.advance))
                return
            
            self.order.update_advance(new_advance)
            self.update_financial_display()
            self.parent_app.save_db()
            
        except ValueError as e:
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
                QMessageBox.warning(self, "Ошибка", "Долг не может быть отрицательным")
                self.debt_edit.setText(self.format_number(self.order.debt))
                return
            
            if new_debt > self.order.price:
                QMessageBox.warning(self, "Ошибка", "Долг не может превышать стоимость")
                self.debt_edit.setText(self.format_number(self.order.debt))
                return
            
            # Рассчитываем новую полученную сумму на основе долга
            new_received = self.order.price - new_debt
            if new_received < 0:
                QMessageBox.warning(self, "Ошибка", "Некорректное значение долга")
                self.debt_edit.setText(self.format_number(self.order.debt))
                return
            
            self.order.update_total_received(new_received)
            self.update_financial_display()
            self.parent_app.save_db()
            
        except ValueError as e:
            QMessageBox.warning(self, "Ошибка", "Введите числовое значение")
            self.debt_edit.setText(self.format_number(self.order.debt))

    def sync_deadline(self):
        self.order.deadline = self.deadline_edit.text()
        self.update_deadline_color()
        self.parent_app.save_db()
    
    def update_deadline_color(self):
        """Обновление цвета поля дедлайна в зависимости от оставшегося времени"""
        if not self.order.deadline:
            self.deadline_edit.setStyleSheet("""
                QLineEdit {
                    background-color: #333333;
                    color: #FFFFFF;
                    border: 1px solid #444444;
                    padding: 5px 8px;
                    border-radius: 3px;
                    font-size: 12px;
                }
            """)
            return
            
        try:
            deadline_date = datetime.strptime(self.order.deadline, "%d.%m.%Y")
            today = datetime.now()
            days_left = (deadline_date - today).days
            
            if days_left < 0:
                # Просрочено - красный
                self.deadline_edit.setStyleSheet("""
                    QLineEdit {
                        background-color: #FF4B2B;
                        color: white;
                        border: 1px solid #FF4B2B;
                        padding: 5px 8px;
                        border-radius: 3px;
                        font-size: 12px;
                        font-weight: bold;
                    }
                """)
            elif days_left == 0:
                # Остался 1 день - красный
                self.deadline_edit.setStyleSheet("""
                    QLineEdit {
                        background-color: #FF4B2B;
                        color: white;
                        border: 1px solid #FF4B2B;
                        padding: 5px 8px;
                        border-radius: 3px;
                        font-size: 12px;
                        font-weight: bold;
                    }
                """)
            elif days_left <= 2:
                # Осталось 2 дня - желтый
                self.deadline_edit.setStyleSheet("""
                    QLineEdit {
                        background-color: #FFA500;
                        color: white;
                        border: 1px solid #FFA500;
                        padding: 5px 8px;
                        border-radius: 3px;
                        font-size: 12px;
                        font-weight: bold;
                    }
                """)
            else:
                # Все в порядке - стандартный
                self.deadline_edit.setStyleSheet("""
                    QLineEdit {
                        background-color: #333333;
                        color: #FFFFFF;
                        border: 1px solid #444444;
                        padding: 5px 8px;
                        border-radius: 3px;
                        font-size: 12px;
                    }
                """)
        except ValueError:
            # Неверный формат даты
            self.deadline_edit.setStyleSheet("""
                QLineEdit {
                    background-color: #333333;
                    color: #FFFFFF;
                    border: 1px solid #444444;
                    padding: 5px 8px;
                    border-radius: 3px;
                    font-size: 12px;
                }
            """)

    def update_financial_display(self):
        # Обновляем поля ввода
        self.cost_edit.setText(self.format_number(self.order.price))
        self.advance_edit.setText(self.format_number(self.order.advance))
        self.debt_edit.setText(self.format_number(self.order.debt))
        
        # Обновляем статусы
        self.update_payment_status()
        self.update_payment_progress()

    def update_order_status(self, state):
        self.order.status = "Завершен" if state else "В работе"
        self.parent_app.save_db()

    def update_payment_status(self):
        if self.order.debt <= 0:
            self.payment_status.setText("✅ Оплачено полностью")
            self.payment_status.setStyleSheet("color: #28A745; font-size: 12px; font-weight: bold;")
        elif self.order.total_received >= self.order.advance:
            self.payment_status.setText("⚠ Аванс погашен, остался долг")
            self.payment_status.setStyleSheet("color: #FFA500; font-size: 12px; font-weight: bold;")
        elif self.order.total_received > 0:
            self.payment_status.setText("⚠ Частично оплачено")
            self.payment_status.setStyleSheet("color: #FFA500; font-size: 12px; font-weight: bold;")
        else:
            self.payment_status.setText("❌ Не оплачено")
            self.payment_status.setStyleSheet("color: #FF4B2B; font-size: 12px; font-weight: bold;")

    def update_payment_progress(self):
        if self.order.price > 0:
            percentage = (self.order.total_received / self.order.price * 100)
            
            # Разбиваем на аванс и остальные платежи
            advance_percentage = (self.order.total_advance_received / self.order.price * 100) if self.order.price > 0 else 0
            payments_percentage = (self.order.total_payments_received / self.order.price * 100) if self.order.price > 0 else 0
            
            text = f"Прогресс оплаты: {percentage:.1f}%"
            if advance_percentage > 0:
                text += f" (Аванс: {advance_percentage:.1f}%)"
            if payments_percentage > 0:
                text += f" (Платежи: {payments_percentage:.1f}%)"
            
            self.payment_progress.setText(text)
            self.payment_progress.setStyleSheet("color: #AAAAAA; font-size: 11px;")
        else:
            self.payment_progress.setText("")
            self.payment_progress.setStyleSheet("color: #AAAAAA; font-size: 11px;")

    def add_payment_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Добавить платеж")
        dialog.setFixedWidth(400)
        
        dialog.setStyleSheet("""
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
            QComboBox {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #444444;
                padding: 6px;
                border-radius: 3px;
                font-size: 12px;
            }
            QDateEdit {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #444444;
                padding: 6px;
                border-radius: 3px;
                font-size: 12px;
            }
            QTextEdit {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #444444;
                padding: 6px;
                border-radius: 3px;
                font-size: 12px;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        
        form_layout = QFormLayout()
        
        # Дата платежа
        date_label = QLabel("Дата:")
        date_edit = QDateEdit()
        date_edit.setDate(datetime.now().date())
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("dd.MM.yyyy")
        form_layout.addRow(date_label, date_edit)
        
        # Сумма
        amount_label = QLabel("Сумма:")
        amount_edit = QLineEdit()
        # Для корректировки позволяем вводить отрицательные значения
        if self.order.debt <= 0:
            amount_validator = QDoubleValidator(-self.order.total_received, 9999999, 2)
        else:
            amount_validator = QDoubleValidator(0.01, self.order.debt, 2)
        amount_edit.setValidator(amount_validator)
        form_layout.addRow(amount_label, amount_edit)
        
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
                    QMessageBox.warning(self, "Ошибка", "Введите сумму платежа")
                    return
                    
                amount = float(amount_text)
                note = note_edit.toPlainText()
                date = date_edit.date().toString("dd.MM.yyyy")
                
                # Определяем тип платежа автоматически
                if amount > 0:
                    payment_type = "платеж"
                else:
                    payment_type = "корректировка"
                
                self.order.add_payment(amount, payment_type, note, date + " 00:00")
                self.update_financial_display()
                self.parent_app.save_db()
                
                if amount > 0:
                    QMessageBox.information(
                        self,
                        "Платеж добавлен",
                        f"Платеж на сумму {amount:.2f} руб. успешно добавлен.\n"
                        f"Получено: {self.order.total_received:.2f} руб.\n"
                        f"Остаток долга: {self.order.debt:.2f} руб."
                    )
                else:
                    QMessageBox.information(
                        self,
                        "Корректировка добавлена",
                        f"Корректировка на сумму {amount:.2f} руб. успешно добавлена.\n"
                        f"Получено: {self.order.total_received:.2f} руб.\n"
                        f"Остаток долга: {self.order.debt:.2f} руб."
                    )
                
            except ValueError as e:
                QMessageBox.warning(self, "Ошибка", str(e))

    def show_payments_history(self):
        dialog = PaymentsDialog(self.order, self.parent_app)
        dialog.exec()
        self.update_financial_display()

    def add_file(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, 
            "Выберите файлы для заказа", 
            "", 
            "Все файлы (*.*)"
        )
        if paths:
            for p in paths:
                if os.path.exists(p):
                    self.order.files.append(ProjectFile(
                        path=p, 
                        name=os.path.basename(p)
                    ))
            self.parent_app.render_client_profile()
            self.parent_app.save_db()

    def pack_zip(self):
        ready_files = [f for f in self.order.files if os.path.exists(f.path)]
        if not ready_files:
            QMessageBox.information(
                self, 
                "Нет файлов", 
                "Нет файлов для архивации."
            )
            return
        
        default_name = f"{self.order.service_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        path, _ = QFileDialog.getSaveFileName(
            self, 
            "Сохранить архив", 
            default_name,
            "ZIP архивы (*.zip)"
        )
        
        if path:
            try:
                with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
                    for f in ready_files:
                        z.write(f.path, f.name)
                
                QMessageBox.information(
                    self, 
                    "Архив создан", 
                    f"Архив успешно создан: {path}\n"
                    f"Добавлено файлов: {len(ready_files)}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось создать архив: {e}")

    def delete_order(self):
        if not self.order:
            return
        
        reply = QMessageBox.question(
            self,
            "Удаление заказа",
            f"Вы уверены, что хотите удалить заказ '{self.order.service_type}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Находим клиента, которому принадлежит заказ
            for client in self.parent_app.clients:
                if self.order in client.orders:
                    client.orders.remove(self.order)
                    break
            
            # Перерисовываем профиль
            self.parent_app.render_client_profile()
            self.parent_app.save_db()
            
            QMessageBox.information(self, "Успех", "Заказ удален")

# --- ГЛАВНОЕ ОКНО ---
class ProMusicCRM(QMainWindow):
    def __init__(self):
        super().__init__()
        self.storage = CRMStorage()
        self.clients = self.storage.load()
        self.current_client = None
        self.init_ui()
        self.setup_shortcuts()

    def init_ui(self):
        self.setWindowTitle("Symphony Pro CRM")
        self.resize(900, 800)
        
        self.set_dark_palette()
        
        self.setStyleSheet("""
            QMainWindow { 
                background-color: #1E1E1E; 
            }
            QLabel { 
                color: #FFFFFF; 
                border: none; 
            }
            QPushButton { 
                background-color: #2D2D2D; 
                color: #FFFFFF; 
                padding: 8px 12px; 
                border-radius: 4px; 
                border: 1px solid #3D3D3D;
                font-size: 12px;
            }
            QPushButton:hover { 
                background-color: #3D3D3D; 
            }
            QPushButton:pressed { 
                background-color: #4D4D4D; 
            }
            QListWidget { 
                background-color: #252525; 
                color: #FFFFFF; 
                border: 1px solid #3D3D3D; 
                outline: none; 
                font-size: 12px;
            }
            QListWidget::item { 
                padding: 8px; 
                border-bottom: 1px solid #333333; 
            }
            QListWidget::item:hover { 
                background-color: #333333; 
            }
            QListWidget::item:selected { 
                background-color: #0078D7; 
                color: white; 
            }
            QLineEdit, QTextEdit, QComboBox { 
                background-color: #333333; 
                color: #FFFFFF; 
                border: 1px solid #444444; 
                padding: 6px; 
                border-radius: 3px; 
                font-size: 12px;
            }
            QComboBox::drop-down {
                border: none;
                background: #444444;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #FFFFFF;
            }
            QScrollArea { 
                border: none; 
                background: transparent; 
            }
            QScrollBar:vertical { 
                background-color: #252525; 
                width: 12px; 
            }
            QScrollBar::handle:vertical { 
                background-color: #444444; 
                border-radius: 6px; 
            }
            QScrollBar::handle:vertical:hover { 
                background-color: #555555; 
            }
            QScrollBar::add-line, QScrollBar::sub-line {
                background: none;
            }
            QCheckBox { 
                color: #DDDDDD; 
                font-size: 12px;
            }
            QCheckBox::indicator { 
                width: 16px; 
                height: 16px; 
            }
            QTextEdit {
                background-color: #252525;
                color: #FFFFFF;
                border: 1px solid #444444;
                padding: 6px;
                border-radius: 3px;
                font-size: 12px;
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Панель статистики
        self.dash = QFrame()
        self.dash.setStyleSheet("""
            QFrame { 
                background-color: #252525; 
                border-radius: 8px; 
                border: 1px solid #3D3D3D; 
            }
        """)
        self.dash.setFixedHeight(90)
        self.dash_layout = QHBoxLayout(self.dash)
        self.dash_layout.setContentsMargins(20, 10, 20, 10)
        self.dash_layout.setSpacing(30)
        main_layout.addWidget(self.dash)

        # Основная рабочая область
        work_area = QHBoxLayout()
        work_area.setSpacing(15)

        # Левая панель с клиентами
        left_panel = QWidget()
        left_panel.setFixedWidth(250)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        clients_label = QLabel("👤 КЛИЕНТЫ")
        clients_label.setStyleSheet("""
            font-size: 14px; 
            font-weight: bold; 
            color: #00D1FF; 
            padding: 10px 5px;
            background-color: #252525;
            border-radius: 4px;
        """)
        left_layout.addWidget(clients_label)
        
        self.cl_list = QListWidget()
        self.cl_list.itemClicked.connect(self.select_client)
        left_layout.addWidget(self.cl_list)
        
        btn_add = QPushButton("➕ Новый клиент")
        btn_add.clicked.connect(self.add_client)
        btn_add.setStyleSheet("""
            background-color: #0078D7; 
            color: white; 
            font-weight: bold; 
            font-size: 13px;
            padding: 10px;
        """)
        left_layout.addWidget(btn_add)
        
        btn_set = QPushButton("⚙ Настройки системы")
        btn_set.clicked.connect(self.open_settings)
        btn_set.setStyleSheet("""
            background-color: #2D2D2D; 
            color: white; 
            font-size: 13px;
            padding: 10px;
        """)
        left_layout.addWidget(btn_set)
        
        db_info = QLabel(f"Клиентов: {len(self.clients)}")
        db_info.setStyleSheet("color: #888888; font-size: 11px; padding: 10px 5px; background-color: #252525; border-radius: 4px;")
        left_layout.addWidget(db_info)
        
        work_area.addWidget(left_panel)

        # Правая панель с профилем клиента
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("border: none; background-color: transparent;")
        
        self.profile_container = QWidget()
        self.profile_layout = QVBoxLayout(self.profile_container)
        self.profile_layout.setContentsMargins(20, 20, 20, 20)
        self.profile_layout.setSpacing(15)
        
        self.placeholder = QLabel("👈 Выберите клиента из списка или создайте нового")
        self.placeholder.setStyleSheet("""
            font-size: 16px; 
            color: #666666; 
            padding: 40px; 
            text-align: center;
            background-color: #252525;
            border-radius: 8px;
        """)
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.profile_layout.addWidget(self.placeholder)
        
        self.scroll.setWidget(self.profile_container)
        work_area.addWidget(self.scroll, 1)

        main_layout.addLayout(work_area)
        
        self.refresh_list()
        self.update_dash()

    def set_dark_palette(self):
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
        dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(40, 40, 40))
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(50, 50, 50))
        dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 45))
        dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
        dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        self.setPalette(dark_palette)

    def setup_shortcuts(self):
        from PyQt6.QtGui import QKeySequence, QShortcut
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self.add_client)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_db)
        QShortcut(QKeySequence("Ctrl+Q"), self).activated.connect(self.close)
        QShortcut(QKeySequence("Delete"), self).activated.connect(self.delete_client)

    def update_dash(self):
        while self.dash_layout.count():
            item = self.dash_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        in_work, done = 0, 0
        total_advance, total_debt, total_cash = 0.0, 0.0, 0.0
        
        for client in self.clients:
            for order in client.orders:
                total_advance += order.advance
                total_cash += order.total_received
                if order.status == "Завершен":
                    done += 1
                else:
                    in_work += 1
                    total_debt += order.debt
        
        stats = [
            ("📋 В РАБОТЕ", str(in_work), "#00D1FF"),
            ("✅ ВЫПОЛНЕНО", str(done), "#28A745"),
            ("💰 АВАНСЫ", f"{total_advance:,.0f} ₽", "#FFD700"),
            ("💳 ДОЛГИ", f"{total_debt:,.0f} ₽", "#FF4B2B" if total_debt > 0 else "#28A745"),
            ("💵 КАССА", f"{total_cash:,.0f} ₽", "#28A745")
        ]
        
        for title, value, color in stats:
            stat_widget = self.create_stat_widget(title, value, color)
            self.dash_layout.addWidget(stat_widget)
        
        self.dash_layout.addStretch()

    def create_stat_widget(self, title, value, color):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 10, 15, 10)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #AAAAAA; font-size: 12px;")
        
        value_label = QLabel(value)
        value_label.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {color};")
        
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        
        return widget

    def clear_profile_layout(self):
        while self.profile_layout.count():
            item = self.profile_layout.takeAt(0)
            widget = item.widget()
            if widget and widget != self.placeholder:
                widget.setParent(None)
                widget.deleteLater()
        
        if not self.current_client:
            self.placeholder.show()
        else:
            self.placeholder.hide()

    def select_client(self, item):
        client_id = item.data(Qt.ItemDataRole.UserRole)
        for client in self.clients:
            if client.id == client_id:
                self.current_client = client
                self.render_client_profile()
                break

    def render_client_profile(self):
        if self.current_client is None:
            return
        
        self.clear_profile_layout()
        client = self.current_client
        
        # Заголовок с именем клиента и кнопками
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)
        
        # Первая строка: имя клиента
        name_row = QHBoxLayout()
        name_label = QLabel(client.name.upper())
        name_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #00D1FF; padding: 10px 0;")
        name_row.addWidget(name_label)
        name_row.addStretch()
        header_layout.addLayout(name_row)
        
        # Вторая строка: кнопки управления
        buttons_row = QHBoxLayout()
        buttons_row.setContentsMargins(0, 0, 0, 0)
        
        # Кнопка "Заметки" с обводкой краёв
        notes_btn = QPushButton("📝 Заметки")
        notes_btn.clicked.connect(self.toggle_notes)
        notes_btn.setStyleSheet("""
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                padding: 8px 12px;
                font-size: 12px;
                min-width: 100px;
                border: 2px solid #444444;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #3D3D3D;
                border-color: #555555;
            }
        """)
        
        delete_btn = QPushButton("🗑 Удалить")
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #DC3545; 
                color: white;
                padding: 8px 12px;
                font-size: 12px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #C82333;
            }
        """)
        delete_btn.clicked.connect(self.delete_client)
        
        buttons_row.addWidget(notes_btn)
        buttons_row.addWidget(delete_btn)
        buttons_row.addStretch()
        
        header_layout.addLayout(buttons_row)
        
        self.profile_layout.addWidget(header_widget)
        
        # Поле заметок
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlainText(client.notes)
        self.notes_edit.setFixedHeight(100)
        self.notes_edit.setVisible(False)
        self.notes_edit.textChanged.connect(self.save_notes)
        self.profile_layout.addWidget(self.notes_edit)
        
        # Статистика клиента
        client_stats = self.calculate_client_stats(client)
        stats_widget = self.create_client_stats_widget(client_stats)
        self.profile_layout.addWidget(stats_widget)
        
        # Заголовок заказов
        orders_label = QLabel("📋 ЗАКАЗЫ КЛИЕНТА")
        orders_label.setStyleSheet("""
            font-size: 16px; 
            font-weight: bold; 
            color: #DDDDDD;
            margin-top: 20px;
            padding: 10px 0;
            border-bottom: 2px solid #3D3D3D;
        """)
        self.profile_layout.addWidget(orders_label)
        
        # Список заказов
        if client.orders:
            for order in client.orders:
                order_widget = OrderWidget(order, self)
                self.profile_layout.addWidget(order_widget)
        else:
            no_orders = QLabel("У клиента пока нет заказов")
            no_orders.setStyleSheet("color: #888888; font-style: italic; padding: 20px; background-color: #252525; border-radius: 8px;")
            no_orders.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.profile_layout.addWidget(no_orders)
        
        # Кнопка создания нового заказа
        new_order_btn = QPushButton("➕ Создать новый заказ")
        new_order_btn.setStyleSheet("""
            background-color: #28A745; 
            color: white; 
            font-weight: bold; 
            padding: 12px;
            font-size: 14px;
        """)
        new_order_btn.clicked.connect(self.add_order)
        self.profile_layout.addWidget(new_order_btn)
        
        self.profile_layout.addStretch()

    def calculate_client_stats(self, client):
        total_orders = len(client.orders)
        completed_orders = sum(1 for o in client.orders if o.status == "Завершен")
        total_received = sum(o.total_received for o in client.orders)
        total_advance = sum(o.advance for o in client.orders)
        total_debt = sum(o.debt for o in client.orders if o.status != "Завершен")
        
        return {
            'total_orders': total_orders,
            'completed_orders': completed_orders,
            'total_received': total_received,
            'total_advance': total_advance,
            'total_debt': total_debt
        }

    def create_client_stats_widget(self, stats):
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border-radius: 8px;
                border: 1px solid #3D3D3D;
                padding: 15px;
            }
        """)
        
        layout = QHBoxLayout(widget)
        layout.setSpacing(20)
        
        stat_items = [
            ("Всего заказов", str(stats['total_orders']), "#00D1FF"),
            ("Выполнено", str(stats['completed_orders']), "#28A745"),
            ("Аванс", f"{stats['total_advance']:,.0f} ₽", "#FFD700"),
            ("Получено", f"{stats['total_received']:,.0f} ₽", "#28A745"),
            ("Долг", f"{stats['total_debt']:,.0f} ₽", "#FF4B2B" if stats['total_debt'] > 0 else "#28A745")
        ]
        
        for title, value, color in stat_items:
            stat_widget = QWidget()
            stat_layout = QVBoxLayout(stat_widget)
            stat_layout.setContentsMargins(0, 0, 0, 0)
            
            title_label = QLabel(title)
            title_label.setStyleSheet("color: #AAAAAA; font-size: 12px;")
            
            value_label = QLabel(value)
            value_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {color};")
            
            stat_layout.addWidget(title_label)
            stat_layout.addWidget(value_label)
            layout.addWidget(stat_widget)
        
        layout.addStretch()
        return widget

    def delete_client(self):
        if self.current_client is None:
            QMessageBox.warning(self, "Внимание", "Сначала выберите клиента для удаления.")
            return
        
        reply = QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Вы уверены, что хотите удалить клиента '{self.current_client.name}'?\nВсе заказы и файлы клиента будут также удалены.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.clients.remove(self.current_client)
            self.current_client = None
            self.clear_profile_layout()
            self.refresh_list()
            self.save_db()
            QMessageBox.information(self, "Успех", "Клиент успешно удален.")

    def toggle_notes(self):
        if self.current_client:
            self.notes_edit.setVisible(not self.notes_edit.isVisible())

    def save_notes(self):
        if self.current_client:
            self.current_client.notes = self.notes_edit.toPlainText()
            self.save_db()

    def save_db(self):
        self.storage.save(self.clients)
        self.update_dash()

    def refresh_list(self):
        self.cl_list.clear()
        for client in self.clients:
            item_text = client.name
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, client.id)
            self.cl_list.addItem(item)

    def add_client(self):
        name, ok = QInputDialog.getText(
            self, 
            "Новый клиент", 
            "Введите имя нового клиента:",
            QLineEdit.EchoMode.Normal,
            ""
        )
        if ok and name.strip():
            if any(client.name.lower() == name.strip().lower() for client in self.clients):
                QMessageBox.warning(self, "Внимание", "Клиент с таким именем уже существует.")
                return
            new_client = Client(
                id=str(uuid.uuid4()),
                name=name.strip()
            )
            self.clients.append(new_client)
            self.refresh_list()
            self.save_db()
            for i in range(self.cl_list.count()):
                item = self.cl_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == new_client.id:
                    self.cl_list.setCurrentItem(item)
                    self.select_client(item)
                    break

    def add_order(self):
        if not self.current_client:
            QMessageBox.warning(self, "Внимание", "Сначала выберите клиента.")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Новый заказ")
        dialog.setFixedWidth(500)
        dialog.setFixedHeight(350)
        
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
            }
            QLabel {
                color: #FFFFFF;
                font-size: 12px;
            }
            QComboBox {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #444444;
                padding: 6px;
                border-radius: 3px;
                font-size: 12px;
            }
            QComboBox::drop-down {
                border: none;
                background: #444444;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #FFFFFF;
            }
            QComboBox QAbstractItemView {
                background-color: #333333;
                color: #FFFFFF;
                selection-background-color: #0078D7;
                border: 1px solid #444444;
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
            QPushButton:pressed {
                background-color: #4D4D4D;
            }
            QFormLayout {
                spacing: 10px;
            }
            QGroupBox {
                color: #FFFFFF;
                border: 1px solid #444444;
                border-radius: 5px;
                margin-top: 10px;
                font-size: 13px;
                font-weight: bold;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        
        service_label = QLabel("Тип услуги:")
        service_combo = QComboBox()
        service_combo.addItems(["Нотный набор", "Сведение", "Монтаж", "Аранжировка", "Мастеринг", "Консультация"])
        form_layout.addRow(service_label, service_combo)
        
        price_label = QLabel("Стоимость (руб):")
        price_edit = QLineEdit("0")
        form_layout.addRow(price_label, price_edit)
        
        deadline_label = QLabel("Срок выполнения:")
        deadline_edit = QLineEdit(datetime.now().strftime("%d.%m.%Y"))
        form_layout.addRow(deadline_label, deadline_edit)
        
        layout.addLayout(form_layout)
        
        # Группа финансов
        finance_group = QGroupBox("Финансы")
        finance_layout = QFormLayout(finance_group)
        finance_layout.setSpacing(10)
        
        advance_label = QLabel("Аванс (руб):")
        advance_edit = QLineEdit("0")
        finance_layout.addRow(advance_label, advance_edit)
        
        layout.addWidget(finance_group)
        layout.addStretch()
        
        # Кнопки
        buttons = QHBoxLayout()
        create_btn = QPushButton("Создать заказ")
        create_btn.setStyleSheet("""
            QPushButton {
                background-color: #28A745;
                color: white;
                font-weight: bold;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6C757D;
                color: white;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #5A6268;
            }
        """)
        
        buttons.addWidget(create_btn)
        buttons.addStretch()
        buttons.addWidget(cancel_btn)
        
        layout.addLayout(buttons)
        
        def create_order():
            try:
                # Заменяем запятую на точку для стоимости
                price_text = price_edit.text().replace(',', '.').replace(' ', '')
                price = float(price_text or 0)
                if price < 0:
                    QMessageBox.warning(dialog, "Ошибка", "Стоимость не может быть отрицательной.")
                    return
                
                # Заменяем запятую на точку для аванса
                advance_text = advance_edit.text().replace(',', '.').replace(' ', '')
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
                    advance=advance,
                    created_at=datetime.now().strftime("%d.%m.%Y %H:%M"),
                    deadline=deadline_edit.text(),
                    status="В работе",
                    payments=[]
                )
                
                # Если указан аванс, добавляем его как платеж
                if advance > 0:
                    new_order.add_payment(advance, "аванс", "Первоначальный аванс")
                
                self.current_client.orders.append(new_order)
                self.render_client_profile()
                self.save_db()
                dialog.accept()
                
                QMessageBox.information(self, "Успех", "Заказ успешно создан.")
                
            except ValueError as e:
                QMessageBox.warning(dialog, "Ошибка", f"Ошибка ввода данных: {e}")
        
        def cancel():
            dialog.reject()
        
        create_btn.clicked.connect(create_order)
        cancel_btn.clicked.connect(cancel)
        
        service_combo.setFocus()
        dialog.exec()

    def open_settings(self):
        SettingsDialog(self).exec()
    
    def import_from_folder(self):
        """Импорт клиентов из структуры папок"""
        dialog = FolderImportDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            imported_count = 0
            order_count = 0
            
            for result in dialog.scan_results:
                client_name = result['client_name']
                order_name = result['order_name']
                files = result['files']
                
                # Ищем существующего клиента или создаем нового
                client = None
                for c in self.clients:
                    if c.name.lower() == client_name.lower():
                        client = c
                        break
                
                if not client:
                    client = Client(
                        id=str(uuid.uuid4()),
                        name=client_name
                    )
                    self.clients.append(client)
                    imported_count += 1
                
                # Создаем заказ
                new_order = Order(
                    id=str(uuid.uuid4()),
                    service_type=order_name,
                    price=0.0,
                    advance=0.0,
                    created_at=datetime.now().strftime("%d.%m.%Y %H:%M"),
                    deadline=datetime.now().strftime("%d.%m.%Y"),
                    status="В работе",
                    files=[],
                    payments=[]
                )
                
                # Добавляем файлы в заказ
                for file_name, file_path in files:
                    project_file = ProjectFile(
                        path=file_path,
                        name=file_name,
                        is_finished=False
                    )
                    new_order.files.append(project_file)
                
                client.orders.append(new_order)
                order_count += 1
            
            # Сохраняем и обновляем интерфейс
            self.save_db()
            self.refresh_list()
            self.clear_profile_layout()
            
            QMessageBox.information(
                self,
                "Импорт завершен",
                f"Импортировано клиентов: {imported_count}\n"
                f"Создано заказов: {order_count}\n"
                f"Всего файлов: {sum(len(result['files']) for result in dialog.scan_results)}"
            )

    def export_json(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Экспорт базы данных",
            f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON файлы (*.json)"
        )
        if path:
            try:
                temp_storage = CRMStorage(path)
                temp_storage.save(self.clients)
                QMessageBox.information(self, "Успех", f"База данных экспортирована в:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось экспортировать базу данных:\n{e}")

    def import_json_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Импорт базы данных",
            "",
            "JSON файлы (*.json)"
        )
        if path:
            try:
                temp_storage = CRMStorage(path)
                imported_clients = temp_storage.load()
                if not imported_clients:
                    QMessageBox.warning(self, "Внимание", "Выбранный файл не содержит данных.")
                    return
                reply = QMessageBox.question(
                    self,
                    "Подтверждение импорта",
                    f"Найдено клиентов: {len(imported_clients)}\n\nТекущая база данных будет заменена. Продолжить?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    backup_path = self.storage.path.with_suffix(f'.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
                    if self.storage.path.exists():
                        shutil.copy2(self.storage.path, backup_path)
                    self.clients = imported_clients
                    self.current_client = None
                    self.save_db()
                    self.refresh_list()
                    self.clear_profile_layout()
                    QMessageBox.information(
                        self,
                        "Успех",
                        f"База данных успешно импортирована.\n\nИмпортировано клиентов: {len(imported_clients)}\nРезервная копия сохранена в: {backup_path}"
                    )
            except json.JSONDecodeError:
                QMessageBox.critical(self, "Ошибка", "Неверный формат JSON файла.")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось импортировать базу данных:\n{e}")

    def export_full_backup(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Создание резервной копии",
            f"full_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            "ZIP архивы (*.zip)"
        )
        if not path:
            return
        try:
            with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.write(self.storage.path, "database.json")
                file_count = 0
                for client in self.clients:
                    for order in client.orders:
                        for file in order.files:
                            if os.path.exists(file.path):
                                arcname = os.path.join(
                                    "files",
                                    client.name,
                                    order.service_type,
                                    file.name
                                )
                                zip_file.write(file.path, arcname)
                                file_count += 1
            QMessageBox.information(
                self,
                "Резервная копия создана",
                f"Полная резервная копия успешно создана:\n\nФайл: {path}\nКлиентов: {len(self.clients)}\nФайлов в архиве: {file_count}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать резервную копию:\n{e}")

    def get_database_size(self):
        if self.storage.path.exists():
            size_bytes = os.path.getsize(self.storage.path)
            if size_bytes < 1024:
                return f"{size_bytes} байт"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes / 1024:.1f} КБ"
            else:
                return f"{size_bytes / (1024 * 1024):.1f} МБ"
        return "0 байт"

    def closeEvent(self, event):
        reply = QMessageBox.question(
            self,
            "Выход",
            "Вы уверены, что хотите выйти? Все изменения сохранены автоматически.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
    dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(40, 40, 40))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(50, 50, 50))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 45))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(dark_palette)
    
    app.setStyleSheet("""
        QMessageBox {
            background-color: #1E1E1E;
        }
        QMessageBox QLabel {
            color: #FFFFFF;
        }
        QMessageBox QPushButton {
            background-color: #2D2D2D;
            color: #FFFFFF;
            border: 1px solid #3D3D3D;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 12px;
        }
        QMessageBox QPushButton:hover {
            background-color: #3D3D3D;
        }
    """)
    
    window = ProMusicCRM()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()