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
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QComboBox, 
    QListWidget, QListWidgetItem, QMessageBox, QScrollArea, 
    QFrame, QFileDialog, QCheckBox, QDialog, QFormLayout, QTextEdit,
    QInputDialog, QGroupBox
)
from PyQt6.QtGui import QFont, QIcon, QDoubleValidator, QPalette, QColor
from PyQt6.QtCore import Qt, pyqtSignal

# --- МОДЕЛИ ДАННЫХ ---
@dataclass
class ProjectFile:
    path: str
    name: str
    is_finished: bool = False

@dataclass
class Order:
    id: str
    service_type: str
    price: float = 0.0
    prepayment: float = 0.0
    created_at: str = ""
    deadline: str = ""
    status: str = "В работе"
    files: list[ProjectFile] = field(default_factory=list)

    @property
    def debt(self):
        return self.price - self.prepayment

@dataclass
class Client:
    id: str
    name: str
    notes: str = ""
    orders: list[Order] = field(default_factory=list)

# --- ХРАНИЛИЩЕ ---
class CRMStorage:
    def __init__(self, filename="pro_database.json"):
        self.path = Path(filename)

    def load(self) -> list[Client]:
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
                        order = Order(
                            id=o.get('id', str(uuid.uuid4())),
                            service_type=o.get('service_type', ''),
                            price=o.get('price', 0.0),
                            prepayment=o.get('prepayment', 0.0),
                            created_at=o.get('created_at', ''),
                            deadline=o.get('deadline', ''),
                            status=o.get('status', 'В работе'),
                            files=files
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

    def save(self, clients: list[Client]):
        try:
            # Создаем временный файл для безопасной записи
            temp_path = self.path.with_suffix('.tmp')
            data = [asdict(c) for c in clients]
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            # Заменяем старый файл новым
            if self.path.exists():
                os.remove(self.path)
            os.rename(temp_path, self.path)
        except Exception as e:
            print(f"Ошибка сохранения базы данных: {e}")
            QMessageBox.critical(None, "Ошибка", f"Не удалось сохранить базу данных: {e}")

    def import_from_file(self, filepath: str) -> list[Client]:
        """Импорт данных из другого JSON файла"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                clients = []
                for c_dict in data:
                    orders = []
                    for o in c_dict.get('orders', []):
                        files = [ProjectFile(**fi) for fi in o.get('files', [])]
                        order = Order(
                            id=o.get('id', str(uuid.uuid4())),
                            service_type=o.get('service_type', ''),
                            price=o.get('price', 0.0),
                            prepayment=o.get('prepayment', 0.0),
                            created_at=o.get('created_at', ''),
                            deadline=o.get('deadline', ''),
                            status=o.get('status', 'В работе'),
                            files=files
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
            print(f"Ошибка импорта базы данных: {e}")
            raise

# --- ДИАЛОГ НАСТРОЕК ---
class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Настройки системы")
        self.setFixedWidth(400)
        
        # Устанавливаем стили для диалога
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
        
        btn_exp = QPushButton("Экспорт базы данных (JSON)")
        btn_exp.clicked.connect(self.parent.export_json)
        
        btn_imp = QPushButton("Импорт базы данных (JSON)")
        btn_imp.clicked.connect(self.parent.import_json_file)
        
        btn_full = QPushButton("Экспорт базы данных + Файлы (ZIP)")
        btn_full.clicked.connect(self.parent.export_full_backup)
        
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
    def __init__(self, file_obj: ProjectFile):
        super().__init__()
        self.file_obj = file_obj
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        
        self.cb = QCheckBox()
        self.cb.setChecked(file_obj.is_finished)
        self.cb.stateChanged.connect(self.update_status)
        self.cb.setStyleSheet("""
            QCheckBox {
                color: #DDDDDD;
                spacing: 5px;
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
                border: 2px solid #00D1FF;
                background: #00D1FF;
            }
        """)
        
        lbl = QLabel(file_obj.name)
        lbl.setStyleSheet("color: #DDDDDD; font-size: 12px;")
        
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
        
        layout.addWidget(self.cb)
        layout.addWidget(lbl, 1)
        layout.addWidget(btn_open)

    def update_status(self, state):
        self.file_obj.is_finished = bool(state)
        self.statusChanged.emit()

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

        # ХЕДЕР
        header = QHBoxLayout()
        self.toggle_btn = QPushButton("▼")
        self.toggle_btn.setFixedSize(25, 25)
        self.toggle_btn.clicked.connect(self.toggle_contents)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #3D3D3D;
                color: #FFFFFF;
                border: none;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4D4D4D;
            }
        """)

        title = QLabel(f"Заказ: {self.order.service_type}")
        title.setStyleSheet("font-weight: bold; color: #00D1FF; font-size: 14px;")
        
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

        header.addWidget(self.toggle_btn)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.status_cb)
        self.main_layout.addLayout(header)

        # КОНТЕНТ (Редактируемый)
        self.content = QWidget()
        self.c_layout = QVBoxLayout(self.content)
        self.c_layout.setSpacing(8)
        
        # Информация о заказе
        info_widget = QWidget()
        info_layout = QHBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        
        # ID заказа
        id_label = QLabel(f"ID: {self.order.id[:8]}...")
        id_label.setStyleSheet("color: #888888; font-size: 10px;")
        info_layout.addWidget(id_label)
        
        # Дата создания
        if self.order.created_at:
            date_label = QLabel(f"Создан: {self.order.created_at}")
            date_label.setStyleSheet("color: #888888; font-size: 10px;")
            info_layout.addWidget(date_label)
        
        info_layout.addStretch()
        self.c_layout.addWidget(info_widget)
        
        # Поля редактирования
        grid = QHBoxLayout()
        grid.setSpacing(10)
        
        # Цена
        price_label = QLabel("Цена:")
        price_label.setStyleSheet("color: #CCCCCC; font-size: 12px;")
        grid.addWidget(price_label)
        self.price_edit = QLineEdit(str(self.order.price))
        self.price_edit.setFixedWidth(80)
        self.price_edit.textChanged.connect(self.sync_data)
        self.price_edit.setStyleSheet("""
            QLineEdit {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #444444;
                padding: 4px;
                border-radius: 3px;
                font-size: 12px;
            }
        """)
        grid.addWidget(self.price_edit)
        
        # Предоплата
        prep_label = QLabel("Аванс:")
        prep_label.setStyleSheet("color: #CCCCCC; font-size: 12px;")
        grid.addWidget(prep_label)
        self.prep_edit = QLineEdit(str(self.order.prepayment))
        self.prep_edit.setFixedWidth(80)
        self.prep_edit.textChanged.connect(self.sync_data)
        self.prep_edit.setStyleSheet("""
            QLineEdit {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #444444;
                padding: 4px;
                border-radius: 3px;
                font-size: 12px;
            }
        """)
        grid.addWidget(self.prep_edit)

        # Дедлайн
        deadline_label = QLabel("Срок:")
        deadline_label.setStyleSheet("color: #CCCCCC; font-size: 12px;")
        grid.addWidget(deadline_label)
        self.deadline_edit = QLineEdit(self.order.deadline)
        self.deadline_edit.textChanged.connect(self.sync_data)
        self.deadline_edit.setStyleSheet("""
            QLineEdit {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #444444;
                padding: 4px;
                border-radius: 3px;
                font-size: 12px;
            }
        """)
        grid.addWidget(self.deadline_edit)
        
        grid.addStretch()
        self.c_layout.addLayout(grid)

        # Статус оплаты
        payment_status = QLabel()
        self.update_payment_status(payment_status)
        self.c_layout.addWidget(payment_status)
        
        # Файлы
        files_label = QLabel("Файлы:")
        files_label.setStyleSheet("font-weight: bold; margin-top: 10px; color: #CCCCCC; font-size: 13px;")
        self.c_layout.addWidget(files_label)
        
        if self.order.files:
            for f in self.order.files:
                fw = FileItemWidget(f)
                fw.statusChanged.connect(self.parent_app.save_db)
                self.c_layout.addWidget(fw)
        else:
            no_files = QLabel("Файлы не добавлены")
            no_files.setStyleSheet("color: #888888; font-style: italic; font-size: 11px; padding: 5px;")
            self.c_layout.addWidget(no_files)

        # Кнопки
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
        btns.addStretch()
        btns.addWidget(b_z)
        self.c_layout.addLayout(btns)

        self.main_layout.addWidget(self.content)

    def toggle_contents(self):
        visible = self.content.isVisible()
        self.content.setVisible(not visible)
        self.toggle_btn.setText("▶" if visible else "▼")

    def sync_data(self):
        try:
            self.order.price = float(self.price_edit.text().replace(',', '.') or 0)
            self.order.prepayment = float(self.prep_edit.text().replace(',', '.') or 0)
            self.order.deadline = self.deadline_edit.text()
            self.parent_app.save_db()
        except ValueError:
            pass

    def update_order_status(self, state):
        self.order.status = "Завершен" if state else "В работе"
        self.parent_app.save_db()

    def update_payment_status(self, label):
        debt = self.order.debt
        if debt <= 0:
            label.setText("✅ Оплачено полностью")
            label.setStyleSheet("color: #28A745; font-size: 12px; font-weight: bold;")
        elif self.order.prepayment > 0:
            label.setText(f"⚠ Частично оплачено (долг: {debt:,.0f} руб)")
            label.setStyleSheet("color: #FFA500; font-size: 12px; font-weight: bold;")
        else:
            label.setText(f"❌ Не оплачено (долг: {debt:,.0f} руб)")
            label.setStyleSheet("color: #FF4B2B; font-size: 12px; font-weight: bold;")

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
        ready_files = [f for f in self.order.files if f.is_finished and os.path.exists(f.path)]
        if not ready_files:
            QMessageBox.information(
                self, 
                "Нет файлов", 
                "Нет готовых файлов для архивации. Отметьте файлы как готовые."
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
        self.resize(1200, 800)
        
        # Устанавливаем темную палитру для всего приложения
        self.set_dark_palette()
        
        # Основные стили
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

        # Основной контент
        work_area = QHBoxLayout()
        work_area.setSpacing(15)

        # Левая панель - список клиентов
        left_panel = QWidget()
        left_panel.setFixedWidth(300)
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
        
        # Кнопки левой панели
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
        
        # Информация о базе
        db_info = QLabel(f"Клиентов: {len(self.clients)}")
        db_info.setStyleSheet("color: #888888; font-size: 11px; padding: 10px 5px; background-color: #252525; border-radius: 4px;")
        left_layout.addWidget(db_info)
        
        work_area.addWidget(left_panel)

        # Правая панель - профиль клиента
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("border: none; background-color: transparent;")
        
        self.profile_container = QWidget()
        self.profile_layout = QVBoxLayout(self.profile_container)
        self.profile_layout.setContentsMargins(20, 20, 20, 20)
        self.profile_layout.setSpacing(15)
        
        # Заглушка при отсутствии выбранного клиента
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
        
        # Инициализация
        self.refresh_list()
        self.update_dash()

    def set_dark_palette(self):
        """Устанавливает темную палитру для всего приложения"""
        dark_palette = QPalette()
        
        # Устанавливаем цвета для различных элементов
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
        
        # Применяем палитру
        self.setPalette(dark_palette)

    def setup_shortcuts(self):
        """Настройка горячих клавиш"""
        from PyQt6.QtGui import QKeySequence, QShortcut
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self.add_client)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_db)
        QShortcut(QKeySequence("Ctrl+Q"), self).activated.connect(self.close)
        QShortcut(QKeySequence("Delete"), self).activated.connect(self.delete_client)

    def update_dash(self):
        """Обновление панели статистики"""
        # Очистка предыдущих виджетов
        while self.dash_layout.count():
            item = self.dash_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Расчет статистики
        in_work, done = 0, 0
        total_prepayment, total_debt, total_cash = 0.0, 0.0, 0.0
        
        for client in self.clients:
            for order in client.orders:
                total_prepayment += order.prepayment
                
                if order.status == "Завершен":
                    done += 1
                    total_cash += order.price
                else:
                    in_work += 1
                    total_cash += order.prepayment
                    total_debt += order.debt
        
        # Создание виджетов статистики
        stats = [
            ("📋 В РАБОТЕ", str(in_work), "#00D1FF"),
            ("✅ ВЫПОЛНЕНО", str(done), "#28A745"),
            ("💰 АВАНСЫ", f"{total_prepayment:,.0f} ₽", "#FFFFFF"),
            ("💳 ДОЛГИ", f"{total_debt:,.0f} ₽", "#FF4B2B"),
            ("💵 КАССА", f"{total_cash:,.0f} ₽", "#FFD700")
        ]
        
        for title, value, color in stats:
            stat_widget = self.create_stat_widget(title, value, color)
            self.dash_layout.addWidget(stat_widget)
        
        self.dash_layout.addStretch()

    def create_stat_widget(self, title, value, color):
        """Создание виджета статистики"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 10, 15, 10)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #AAAAAA; font-size: 12px;")
        
        value_label = QLabel(value)
        value_label.setStyleSheet(f"""
            font-size: 18px; 
            font-weight: bold; 
            color: {color};
        """)
        
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        
        return widget

    def clear_profile_layout(self):
        """Очистка содержимого профиля клиента"""
        # Удаляем все виджеты кроме заглушки
        while self.profile_layout.count():
            item = self.profile_layout.takeAt(0)
            widget = item.widget()
            if widget and widget != self.placeholder:
                widget.setParent(None)
                widget.deleteLater()
        
        # Показываем заглушку если нет клиента
        if not self.current_client:
            self.placeholder.show()
        else:
            self.placeholder.hide()

    def select_client(self, item):
        """Выбор клиента из списка"""
        client_id = item.data(Qt.ItemDataRole.UserRole)
        for client in self.clients:
            if client.id == client_id:
                self.current_client = client
                self.render_client_profile()
                break

    def render_client_profile(self):
        """Отрисовка профиля выбранного клиента"""
        if self.current_client is None:
            return
        
        self.clear_profile_layout()
        client = self.current_client
        
        # Шапка профиля
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        name_label = QLabel(client.name.upper())
        name_label.setStyleSheet("""
            font-size: 24px; 
            font-weight: bold; 
            color: #00D1FF;
            padding: 10px 0;
        """)
        
        # Кнопки управления
        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout(buttons_widget)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(10)
        
        notes_btn = QPushButton("📝 Заметки")
        notes_btn.clicked.connect(self.toggle_notes)
        notes_btn.setStyleSheet("""
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                padding: 8px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #3D3D3D;
            }
        """)
        
        delete_btn = QPushButton("🗑 Удалить")
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #DC3545; 
                color: white;
                padding: 8px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #C82333;
            }
        """)
        delete_btn.clicked.connect(self.delete_client)
        
        buttons_layout.addWidget(notes_btn)
        buttons_layout.addWidget(delete_btn)
        
        header_layout.addWidget(name_label)
        header_layout.addStretch()
        header_layout.addWidget(buttons_widget)
        
        self.profile_layout.addWidget(header)
        
        # Блокнот
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
        
        # Список заказов
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
        
        if client.orders:
            for order in client.orders:
                order_widget = OrderWidget(order, self)
                self.profile_layout.addWidget(order_widget)
        else:
            no_orders = QLabel("У клиента пока нет заказов")
            no_orders.setStyleSheet("color: #888888; font-style: italic; padding: 20px; background-color: #252525; border-radius: 8px;")
            no_orders.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.profile_layout.addWidget(no_orders)
        
        # Кнопка создания заказа
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
        """Расчет статистики по клиенту"""
        total_orders = len(client.orders)
        completed_orders = sum(1 for o in client.orders if o.status == "Завершен")
        
        # Получено денег = сумма предоплат по всем заказам
        total_received = sum(o.prepayment for o in client.orders)
        
        # Долг = сумма долгов по незавершенным заказам
        total_debt = sum(o.debt for o in client.orders if o.status != "Завершен")
        
        return {
            'total_orders': total_orders,
            'completed_orders': completed_orders,
            'total_received': total_received,
            'total_debt': total_debt
        }

    def create_client_stats_widget(self, stats):
        """Создание виджета статистики клиента"""
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
        layout.setSpacing(30)
        
        # Измененные названия и порядок
        stat_items = [
            ("Всего заказов", str(stats['total_orders']), "#00D1FF"),
            ("Выполнено", str(stats['completed_orders']), "#28A745"),
            ("Получено денег", f"{stats['total_received']:,.0f} ₽", "#FFD700"),
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
        """Удаление текущего клиента"""
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
        """Показать/скрыть блокнот"""
        if self.current_client:
            self.notes_edit.setVisible(not self.notes_edit.isVisible())

    def save_notes(self):
        """Сохранение заметок клиента"""
        if self.current_client:
            self.current_client.notes = self.notes_edit.toPlainText()
            self.save_db()

    def save_db(self):
        """Сохранение базы данных"""
        self.storage.save(self.clients)
        self.update_dash()

    def refresh_list(self):
        """Обновление списка клиентов"""
        self.cl_list.clear()
        for client in self.clients:
            # Подсчет активных заказов
            active_orders = sum(1 for o in client.orders if o.status != "Завершен")
            
            item_text = f"{client.name}"
            if active_orders > 0:
                item_text += f" ({active_orders} активн.)"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, client.id)
            
            # Подсветка клиентов с долгами
            has_debt = any(o.debt > 0 for o in client.orders if o.status != "Завершен")
            if has_debt:
                item.setForeground(QColor("#FF4B2B"))
            
            self.cl_list.addItem(item)

    def add_client(self):
        """Добавление нового клиента"""
        name, ok = QInputDialog.getText(
            self, 
            "Новый клиент", 
            "Введите имя нового клиента:",
            QLineEdit.EchoMode.Normal,
            ""
        )
        
        if ok and name.strip():
            # Проверка на дубликаты
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
            
            # Выбираем нового клиента
            for i in range(self.cl_list.count()):
                item = self.cl_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == new_client.id:
                    self.cl_list.setCurrentItem(item)
                    self.select_client(item)
                    break

    def add_order(self):
        """Добавление нового заказа"""
        if not self.current_client:
            QMessageBox.warning(self, "Внимание", "Сначала выберите клиента.")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Новый заказ")
        dialog.setFixedWidth(400)
        dialog.setFixedHeight(250)
        
        # Устанавливаем темные стили для диалога
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
        """)
        
        layout = QFormLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Тип услуги
        service_label = QLabel("Тип услуги:")
        service_combo = QComboBox()
        service_combo.addItems(["Нотный набор", "Сведение", "Монтаж", "Аранжировка", "Мастеринг", "Консультация"])
        layout.addRow(service_label, service_combo)
        
        # Цена
        price_label = QLabel("Стоимость (руб):")
        price_edit = QLineEdit("0")
        # Устанавливаем валидатор для числового ввода
        price_edit.setValidator(QDoubleValidator(0.0, 1000000.0, 2))
        layout.addRow(price_label, price_edit)
        
        # Срок
        deadline_label = QLabel("Срок выполнения:")
        deadline_edit = QLineEdit(datetime.now().strftime("%d.%m.%Y"))
        layout.addRow(deadline_label, deadline_edit)
        
        # Кнопки
        buttons = QHBoxLayout()
        create_btn = QPushButton("Создать")
        create_btn.setStyleSheet("""
            QPushButton {
                background-color: #28A745;
                color: white;
                font-weight: bold;
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
            }
            QPushButton:hover {
                background-color: #5A6268;
            }
        """)
        
        buttons.addWidget(create_btn)
        buttons.addStretch()
        buttons.addWidget(cancel_btn)
        
        layout.addRow(buttons)
        
        # Обработчики
        def create_order():
            try:
                price_text = price_edit.text().replace(',', '.')
                price = float(price_text or 0)
                if price < 0:
                    QMessageBox.warning(dialog, "Ошибка", "Цена не может быть отрицательной.")
                    return
                
                new_order = Order(
                    id=str(uuid.uuid4()),
                    service_type=service_combo.currentText(),
                    price=price,
                    prepayment=0.0,
                    created_at=datetime.now().strftime("%d.%m.%Y %H:%M"),
                    deadline=deadline_edit.text(),
                    status="В работе"
                )
                
                self.current_client.orders.append(new_order)
                self.render_client_profile()
                self.save_db()
                dialog.accept()
                
            except ValueError:
                QMessageBox.warning(dialog, "Ошибка", "Введите корректную цену.")
        
        def cancel():
            dialog.reject()
        
        create_btn.clicked.connect(create_order)
        cancel_btn.clicked.connect(cancel)
        
        # Устанавливаем фокус на поле выбора услуги
        service_combo.setFocus()
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            QMessageBox.information(self, "Успех", "Заказ успешно создан.")

    def open_settings(self):
        """Открытие диалога настроек"""
        SettingsDialog(self).exec()

    def export_json(self):
        """Экспорт базы данных в JSON"""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Экспорт базы данных",
            f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON файлы (*.json)"
        )
        
        if path:
            try:
                # Используем наш метод save для экспорта
                temp_storage = CRMStorage(path)
                temp_storage.save(self.clients)
                QMessageBox.information(self, "Успех", f"База данных экспортирована в:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось экспортировать базу данных:\n{e}")

    def import_json_file(self):
        """Импорт базы данных из JSON"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Импорт базы данных",
            "",
            "JSON файлы (*.json)"
        )
        
        if path:
            try:
                # Загружаем данные из файла
                imported_clients = self.storage.import_from_file(path)
                
                if not imported_clients:
                    QMessageBox.warning(self, "Внимание", "Выбранный файл не содержит данных.")
                    return
                
                # Подтверждение импорта
                reply = QMessageBox.question(
                    self,
                    "Подтверждение импорта",
                    f"Найдено клиентов: {len(imported_clients)}\n\n"
                    f"Текущая база данных будет заменена. Продолжить?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    # Создаем резервную копию текущей базы
                    backup_path = self.storage.path.with_suffix(f'.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
                    if self.storage.path.exists():
                        shutil.copy2(self.storage.path, backup_path)
                    
                    # Заменяем текущие данные
                    self.clients = imported_clients
                    self.current_client = None
                    self.save_db()
                    self.refresh_list()
                    self.clear_profile_layout()
                    
                    QMessageBox.information(
                        self,
                        "Успех",
                        f"База данных успешно импортирована.\n\n"
                        f"Импортировано клиентов: {len(imported_clients)}\n"
                        f"Резервная копия сохранена в: {backup_path}"
                    )
                    
            except json.JSONDecodeError:
                QMessageBox.critical(self, "Ошибка", "Неверный формат JSON файла.")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось импортировать базу данных:\n{e}")

    def export_full_backup(self):
        """Экспорт полной резервной копии (база + файлы)"""
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
                # Добавляем базу данных
                zip_file.write(self.storage.path, "database.json")
                
                # Добавляем файлы клиентов
                file_count = 0
                for client in self.clients:
                    for order in client.orders:
                        for file in order.files:
                            if os.path.exists(file.path):
                                # Создаем структуру папок в архиве
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
                f"Полная резервная копия успешно создана:\n\n"
                f"Файл: {path}\n"
                f"Клиентов: {len(self.clients)}\n"
                f"Файлов в архиве: {file_count}"
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать резервную копию:\n{e}")

    def get_database_size(self):
        """Получение размера базы данных"""
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
        """Обработка закрытия приложения"""
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
    
    # Устанавливаем темную палитру для всего приложения
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
    
    # Устанавливаем стиль для QMessageBox
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
    
    # Создание и отображение главного окна
    window = ProMusicCRM()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()