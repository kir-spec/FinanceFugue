
import os
import sys
import logging
from .logger import get_logger

logger = get_logger("MainWindow")
import json
import uuid
import zipfile
import shutil
import glob
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QListWidget,
    QListWidgetItem, QMessageBox, QScrollArea,
    QFrame, QFileDialog, QMenu, QInputDialog, QTextEdit,
    QDialog, QFormLayout, QComboBox, QGroupBox
)
from PySide6.QtGui import QPalette, QColor, QAction, QKeySequence, QShortcut
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QSize

from .models import Client, Order, ProjectFile
from .storage import CRMStorage
from .dialogs import (
    FirstRunDialog, SettingsDialog, ClientSettingsDialog, 
    ClientOrdersExportDialog, FolderImportDialog
)
from .widgets import OrderWidget

# --- ГЛАВНОЕ ОКНО ---
class ProMusicCRM(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.info("Инициализация приложения")
        self.app_settings = self.load_settings()  # Загружаем настройки первым делом
        
        # Определяем путь к базе данных
        db_filename = "pro_database.json"
        if 'database_path' in self.app_settings:
            db_path = self.app_settings['database_path']
            if os.path.exists(db_path):
                db_filename = os.path.join(db_path, "pro_database.json")
        
        self.storage = CRMStorage(db_filename)
        self.clients = self.storage.load()
        logger.info(f"Загружено клиентов: {len(self.clients)}")
        self.current_client = None
        
        self.init_ui()
        self.setup_shortcuts()
        
        # Проверяем первый запуск
        if self.is_first_run():
            if not self.show_first_run_dialog():
                sys.exit(0)

    def load_settings(self):
        """Загружает настройки приложения"""
        settings_path = Path("crm_settings.json")
        if settings_path.exists():
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_settings(self):
        """Сохраняет настройки приложения"""
        settings_path = Path("crm_settings.json")
        try:
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(self.app_settings, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Ошибка сохранения настроек: {e}")

    def is_first_run(self):
        """Проверяет, первый ли это запуск приложения"""
        return 'first_run_completed' not in self.app_settings

    def show_first_run_dialog(self):
        """Показывает диалог первого запуска"""
        dialog = FirstRunDialog(self)
        result = dialog.exec()
        
        if result == QDialog.DialogCode.Accepted:
            settings = dialog.get_settings()
            self.app_settings.update(settings)
            self.app_settings['first_run_completed'] = True
            self.save_settings()
            
            # Если был выбран новый путь, обновляем storage
            if 'database_path' in settings:
                new_db_path = os.path.join(settings['database_path'], "pro_database.json")
                self.storage = CRMStorage(new_db_path)
                # Перезагружаем (пустую) базу по новому пути или сохраняем текущую туда, если она была
                self.clients = self.storage.load()
                self.update_dash()
                self.refresh_list()
            
            # Если выбрано копирование файлов в базу данных, создаем структуру папок
            if settings.get('file_storage_mode') == 'copy':
                db_folder = settings.get('database_path', os.path.dirname(self.storage.path))
                files_folder = os.path.join(db_folder, "attached_files")
                os.makedirs(files_folder, exist_ok=True)
            return True
        return False

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
                padding: 5px 10px;
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
                padding: 4px 8px;
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
                border-left: 1px solid #444444;
                background: #3D3D3D;
                width: 25px;
                border-top-right-radius: 3px;
                border-bottom-right-radius: 3px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 6px solid #00D1FF;
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
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # Панель статистики
        self.dash = QFrame()
        self.dash.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
            }
        """)
        self.dash.setFixedHeight(60)
        self.dash_layout = QHBoxLayout(self.dash)
        self.dash_layout.setContentsMargins(0, 0, 0, 0)
        self.dash_layout.setSpacing(8)
        self.dash_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.dash)

        # Основная рабочая область
        work_area = QHBoxLayout()
        work_area.setSpacing(15)

        # Левая панель с клиентами
        self.left_panel = QWidget()
        self.left_panel.setMinimumWidth(250)
        self.left_panel.setMaximumWidth(250)
        
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        # Верхний блок заголовка панели
        self.header_panel = QWidget()
        self.header_panel.setFixedHeight(30)
        header_layout = QHBoxLayout(self.header_panel)
        header_layout.setContentsMargins(5, 0, 0, 0)
        header_layout.setSpacing(0)
        
        # Кнопка сворачивания/разворачивания
        self.toggle_btn = QPushButton("👤 КЛИЕНТЫ")
        self.toggle_btn.clicked.connect(self.toggle_sidebar)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setFixedHeight(30)
        # Стиль будет меняться в toggle_sidebar
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #00D1FF;
                border: none;
                font-weight: bold;
                font-size: 14px;
                text-align: left;
                padding-left: 5px;
            }
            QPushButton:hover {
                color: #FFFFFF;
            }
        """)
        
        header_layout.addWidget(self.toggle_btn)
        
        # Линия-разделитель (будет видна при развернутом состоянии)
        self.header_panel.setStyleSheet("border-bottom: 1px solid #3D3D3D; background-color: #252525;")
        
        left_layout.addWidget(self.header_panel)

        # Обертка для контента с прокруткой (для clipping эффекта)
        self.left_wrapper = QScrollArea()
        self.left_wrapper.setWidgetResizable(True)
        self.left_wrapper.setFrameShape(QFrame.Shape.NoFrame)
        self.left_wrapper.setStyleSheet("background: transparent; border: none;")
        self.left_wrapper.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.left_wrapper.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Контент левой панели
        self.left_content = QWidget()
        self.left_content.setMinimumWidth(250) # Фиксируем мин. ширину, чтобы не сжимался
        
        content_layout = QVBoxLayout(self.left_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        self.cl_list = QListWidget()
        self.cl_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.cl_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.cl_list.customContextMenuRequested.connect(self.show_client_context_menu)
        self.cl_list.itemClicked.connect(self.select_client)
        content_layout.addWidget(self.cl_list)
        
        self.left_wrapper.setWidget(self.left_content)
        left_layout.addWidget(self.left_wrapper, 1)
        
        # Нижняя панель с кнопками
        self.bottom_panel = QWidget()
        bottom_layout = QVBoxLayout(self.bottom_panel)
        bottom_layout.setContentsMargins(5, 5, 5, 5)
        bottom_layout.setSpacing(5)
        
        btn_add = QPushButton("➕ Новый клиент")
        btn_add.clicked.connect(self.add_client)
        btn_add.setStyleSheet("""
            background-color: #0078D7;
            color: white;
            font-weight: bold;
            font-size: 13px;
            padding: 6px;
        """)
        bottom_layout.addWidget(btn_add)
        
        btn_set = QPushButton("⚙ Настройки")
        btn_set.clicked.connect(self.open_settings)
        btn_set.setStyleSheet("""
            background-color: #2D2D2D;
            color: white;
            font-size: 13px;
            padding: 6px;
        """)
        bottom_layout.addWidget(btn_set)

        self.db_info = QLabel(f"Клиентов: {len(self.clients)}")
        self.db_info.setStyleSheet("color: #888888; font-size: 11px; padding: 5px 5px; background-color: #252525; border-radius: 4px;")
        bottom_layout.addWidget(self.db_info)
        
        left_layout.addWidget(self.bottom_panel)
        left_layout.addStretch()
        
        work_area.addWidget(self.left_panel)

        # Правая панель с профилем клиента
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("border: none; background-color: transparent;")
        
        self.profile_container = QWidget()
        self.profile_layout = QVBoxLayout(self.profile_container)
        self.profile_layout.setContentsMargins(15, 15, 15, 15)
        self.profile_layout.setSpacing(10)
        
        self.placeholder = QLabel("👈 Выберите клиента из списка или создайте нового")
        self.placeholder.setStyleSheet("""
            font-size: 16px;
            color: #AAAAAA;
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
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self.add_client)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_db)
        QShortcut(QKeySequence("Ctrl+Q"), self).activated.connect(self.close)
        QShortcut(QKeySequence("Delete"), self).activated.connect(self.delete_client)

    def toggle_sidebar(self):
        start_width = self.left_panel.width()
        collapsed_width = 40
        expanded_width = 250
        
        if start_width > collapsed_width:
             # Collapsing
             end_width = collapsed_width
             self.toggle_btn.setText("▶")
             # Сбрасываем ограничения размера, чтобы текст выравнивался корректно
             self.toggle_btn.setMinimumSize(0, 30)
             self.toggle_btn.setMaximumSize(16777215, 30)
             
             # Выравниваем стрелку влево (padding-left: 5px, как и у заголовка)
             self.toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #00D1FF;
                    border: none;
                    font-weight: bold;
                    font-size: 14px;
                    text-align: left;
                    padding-left: 5px;
                }
                QPushButton:hover {
                    color: #FFFFFF;
                }
            """)
        else:
             # Expanding
             end_width = expanded_width
             self.toggle_btn.setText("👤 КЛИЕНТЫ")
             
             self.toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #00D1FF;
                    border: none;
                    font-weight: bold;
                    font-size: 14px;
                    text-align: left;
                    padding-left: 5px;
                }
                QPushButton:hover {
                    color: #FFFFFF;
                }
            """)
             self.left_wrapper.show()
             self.bottom_panel.show()
        
        self.anim_group = QParallelAnimationGroup()
        
        anim_min = QPropertyAnimation(self.left_panel, b"minimumWidth")
        anim_min.setDuration(300)
        anim_min.setStartValue(start_width)
        anim_min.setEndValue(end_width)
        anim_min.setEasingCurve(QEasingCurve.InOutQuad)
        
        anim_max = QPropertyAnimation(self.left_panel, b"maximumWidth")
        anim_max.setDuration(300)
        anim_max.setStartValue(start_width)
        anim_max.setEndValue(end_width)
        anim_max.setEasingCurve(QEasingCurve.InOutQuad)

        self.anim_group.addAnimation(anim_min)
        self.anim_group.addAnimation(anim_max)
        
        if end_width == collapsed_width:
            self.anim_group.finished.connect(self.left_wrapper.hide)
            self.anim_group.finished.connect(self.bottom_panel.hide)
            
        self.anim_group.start()

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
        widget = QFrame()
        widget.setStyleSheet(f"""
            QFrame {{
                background-color: transparent;
                border: none;
            }}
        """)
        
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(2)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #AAAAAA; font-size: 11px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        value_label = QLabel(value)
        value_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {color};")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
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
        header_layout.setSpacing(5)
        
        # Первая строка: имя клиента
        name_row = QHBoxLayout()
        name_label = QLabel(client.name.upper())
        name_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #00D1FF; padding: 5px 0;")
        name_row.addWidget(name_label)
        name_row.addStretch()
        header_layout.addLayout(name_row)
        
        # Вторая строка: кнопки управления
        buttons_row = QHBoxLayout()
        buttons_row.setContentsMargins(0, 0, 0, 0)
        buttons_row.setSpacing(10)
        
        # Кнопка добавления заказа
        add_order_btn = QPushButton("➕ добавить заказ")
        add_order_btn.setFixedWidth(140)
        add_order_btn.setFixedHeight(36)
        add_order_btn.setStyleSheet("""
            QPushButton {
                background-color: #28A745;
                color: white;
                border: 1px solid #28A745;
                border-radius: 4px;
                font-size: 13px;
                padding: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
                border-color: #1E7E34;
            }
        """)
        add_order_btn.clicked.connect(self.add_order)
        buttons_row.addWidget(add_order_btn)
        
        # Кнопка настроек (шестеренка) - ТЕПЕРЬ "настройки"
        settings_btn = QPushButton("⚙ настройки")
        settings_btn.setFixedWidth(120)
        settings_btn.setFixedHeight(36)
        settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #2D2D2D;
                color: white;
                border: 1px solid #444444;
                border-radius: 4px;
                font-size: 13px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #3D3D3D;
                border-color: #555555;
            }
        """)
        settings_btn.clicked.connect(self.open_client_settings)
        buttons_row.addWidget(settings_btn)

        # Кнопка "Заметки"
        notes_btn = QPushButton("📝 заметки")
        notes_btn.setFixedWidth(120)
        notes_btn.setFixedHeight(36)
        notes_btn.setStyleSheet("""
            QPushButton {
                background-color: #2D2D2D;
                color: white;
                border: 1px solid #444444;
                border-radius: 4px;
                font-size: 13px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #3D3D3D;
                border-color: #555555;
            }
        """)
        notes_btn.clicked.connect(self.toggle_notes)
        buttons_row.addWidget(notes_btn)
        
        buttons_row.addStretch()
        
        header_layout.addLayout(buttons_row)
        
        self.profile_layout.addWidget(header_widget)
        
        # Разделитель после заголовка
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("background-color: #3D3D3D; min-height: 1px; max-height: 1px; border: none; margin: 5px 0;")
        self.profile_layout.addWidget(sep1)
        
        # Поле заметок
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlainText(client.notes)
        self.notes_edit.setFixedHeight(100)
        self.notes_edit.setVisible(False)
        self.notes_edit.textChanged.connect(self.save_notes)
        self.notes_edit.setStyleSheet("""
            QTextEdit {
                background-color: #252525;
                color: #FFFFFF;
                border: 2px solid #444444;
                padding: 8px;
                border-radius: 4px;
                font-size: 12px;
            }
            QTextEdit:focus {
                border-color: #0078D7;
            }
        """)
        self.profile_layout.addWidget(self.notes_edit)
        
        # Статистика клиента
        client_stats = self.calculate_client_stats(client)
        stats_widget = self.create_client_stats_widget(client_stats)
        self.profile_layout.addWidget(stats_widget)
        
        # Разделитель после статистики
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("background-color: #3D3D3D; min-height: 1px; max-height: 1px; border: none; margin: 5px 0;")
        self.profile_layout.addWidget(sep2)
        
        # Заголовок заказов
        orders_label = QLabel("📋 ЗАКАЗЫ КЛИЕНТА")
        orders_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #DDDDDD;
            margin-top: 20px;
            padding: 5px 0;
            border-bottom: 1px solid #3D3D3D;
        """)
        self.profile_layout.addWidget(orders_label)
        
        # Список заказов
        if client.orders:
            for order in client.orders:
                order_widget = OrderWidget(order, self)
                self.profile_layout.addWidget(order_widget)
        else:
            # Empty state как на скриншоте
            empty_frame = QFrame()
            empty_frame.setStyleSheet("""
                QFrame {
                    background-color: #1A1A1A;
                    border-radius: 10px;
                    border: 1px solid #333333;
                }
            """)
            empty_layout = QVBoxLayout(empty_frame)
            empty_layout.setContentsMargins(40, 40, 40, 40)
            empty_layout.setSpacing(15)
            empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Иконка коробки (текстом, так как нет ассета)
            box_icon = QLabel("📦")
            box_icon.setStyleSheet("font-size: 64px; border: none; background: transparent;")
            box_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.addWidget(box_icon)
            
            # Заголовок
            empty_title = QLabel("У клиента пока нет заказов")
            empty_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFFFFF; border: none; background: transparent;")
            empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.addWidget(empty_title)
            
            # Подзаголовок
            empty_sub = QLabel("Создайте первый заказ, чтобы начать работу с клиентом")
            empty_sub.setStyleSheet("font-size: 14px; color: #888888; border: none; background: transparent;")
            empty_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.addWidget(empty_sub)
            
            # Кнопка создания
            empty_btn = QPushButton("➕ Добавить заказ")
            empty_btn.setFixedSize(200, 40)
            empty_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            empty_btn.setStyleSheet("""
                QPushButton {
                    background-color: #28A745;
                    color: white;
                    border-radius: 5px;
                    font-size: 14px;
                    font-weight: bold;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #218838;
                }
            """)
            empty_btn.clicked.connect(self.add_order)
            empty_layout.addWidget(empty_btn)
            
            self.profile_layout.addWidget(empty_frame)
        
        self.profile_layout.addStretch()

    def calculate_client_stats(self, client):
        # Сумма всех заказов (price)
        total_sum = sum(o.price for o in client.orders)
        
        # Всего оплачено (received)
        total_received = sum(o.total_received for o in client.orders)
        
        # Авансы (advance)
        total_advance = sum(o.advance for o in client.orders)
        
        # Долг (только по активным заказам, либо общий долг - в ТЗ было "по незавершенным", но обычно долг это общий остаток)
        # Вернем "общий остаток к оплате"
        total_debt = sum(o.debt for o in client.orders if o.status != "Завершен")
        
        return {
            'total_sum': total_sum,
            'total_received': total_received,
            'total_advance': total_advance,
            'total_debt': total_debt
        }

    def create_client_stats_widget(self, stats):
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
                padding: 0px;
            }
        """)
        
        layout = QHBoxLayout(widget)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 10, 0, 10)
        
        # Helper for box style
        box_style = """
            QFrame {
                background-color: #252525;
                border: 1px solid #3D3D3D;
                border-radius: 6px;
            }
        """
        
        # 1. Сумма заказов
        box_sum = QFrame()
        box_sum.setStyleSheet(box_style)
        l_sum = QVBoxLayout(box_sum)
        val_sum = QLabel(f"{stats['total_sum']:,.0f} ₽")
        val_sum.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val_sum.setStyleSheet("font-size: 20px; color: #00D1FF; font-weight: bold; border: none; background: transparent;")
        lbl_sum = QLabel("СУММА ЗАКАЗОВ")
        lbl_sum.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_sum.setStyleSheet("font-size: 11px; color: #888888; font-weight: bold; border: none; background: transparent;")
        l_sum.addWidget(val_sum)
        l_sum.addWidget(lbl_sum)
        layout.addWidget(box_sum)

        # 2. Всего оплачено
        box_paid = QFrame()
        box_paid.setStyleSheet(box_style)
        l_paid = QVBoxLayout(box_paid)
        val_paid = QLabel(f"{stats['total_received']:,.0f} ₽")
        val_paid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val_paid.setStyleSheet("font-size: 20px; color: #28A745; font-weight: bold; border: none; background: transparent;")
        lbl_paid = QLabel("ВСЕГО ОПЛАЧЕНО")
        lbl_paid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_paid.setStyleSheet("font-size: 11px; color: #888888; font-weight: bold; border: none; background: transparent;")
        l_paid.addWidget(val_paid)
        l_paid.addWidget(lbl_paid)
        layout.addWidget(box_paid)

        # 3. Авансы
        box_adv = QFrame()
        box_adv.setStyleSheet(box_style)
        l_adv = QVBoxLayout(box_adv)
        val_adv = QLabel(f"{stats['total_advance']:,.0f} ₽")
        val_adv.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val_adv.setStyleSheet("font-size: 20px; color: #FFD700; font-weight: bold; border: none; background: transparent;")
        lbl_adv = QLabel("АВАНСЫ")
        lbl_adv.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_adv.setStyleSheet("font-size: 11px; color: #888888; font-weight: bold; border: none; background: transparent;")
        l_adv.addWidget(val_adv)
        l_adv.addWidget(lbl_adv)
        layout.addWidget(box_adv)

        # 4. Долг (один элемент)
        box_debt = QFrame()
        box_debt.setStyleSheet(box_style)
        l_debt = QVBoxLayout(box_debt)
        val_debt = QLabel(f"{stats['total_debt']:,.0f} ₽")
        val_debt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        debt_color = "#777777" if stats['total_debt'] <= 0 else "#FF4B2B"
        val_debt.setStyleSheet(f"font-size: 20px; color: {debt_color}; font-weight: bold; border: none; background: transparent;")
        lbl_debt = QLabel("ДОЛГ")
        lbl_debt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_debt.setStyleSheet("font-size: 11px; color: #888888; font-weight: bold; border: none; background: transparent;")
        l_debt.addWidget(val_debt)
        l_debt.addWidget(lbl_debt)
        layout.addWidget(box_debt)
        
        return widget

    def export_client_files(self):
        """Экспорт всех файлов клиента с объяснением"""
        if not self.current_client:
            return
            
        # Диалог с объяснением
        explanation = QMessageBox(self)
        explanation.setWindowTitle("Экспорт файлов клиента")
        explanation.setText(
            "Эта функция экспортирует все файлы из всех заказов клиента.\n\n"
            "Для каждого заказа будет создан отдельный ZIP архив, содержащий все файлы этого заказа.\n"
            "Архивы будут сохранены в выбранной вами папке, сгруппированные по датам заказов."
        )
        explanation.setIcon(QMessageBox.Icon.Information)
        explanation.addButton("Продолжить", QMessageBox.ButtonRole.AcceptRole)
        explanation.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        
        if explanation.exec() != 0:  # Если нажата "Отмена"
            return
        
        # Выбор папки для экспорта
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку для экспорта файлов")
        if not folder:
            return
        
        total_files = 0
        exported_orders = 0
        
        for order in self.current_client.orders:
            if not order.files:
                continue
                
            ready_files = [f for f in order.files if os.path.exists(f.path)]
            if not ready_files:
                continue
            
            # Создаем папку с датой заказа
            try:
                order_date = datetime.strptime(order.created_at.split()[0], "%d.%m.%Y")
                date_folder = os.path.join(folder, order_date.strftime("%Y-%m-%d"))
            except:
                date_folder = os.path.join(folder, "без_даты")
            
            os.makedirs(date_folder, exist_ok=True)
            
            # Создаем архив
            archive_name = f"{order.service_type}_{order.id[:8]}.zip"
            archive_path = os.path.join(date_folder, archive_name)
            
            try:
                with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as z:
                    for f in ready_files:
                        z.write(f.path, f.name)
                        total_files += 1
                
                exported_orders += 1
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось создать архив для заказа '{order.service_type}': {e}")
        
        if exported_orders > 0:
            QMessageBox.information(
                self,
                "Экспорт завершен",
                f"Экспортировано заказов: {exported_orders}\n"
                f"Экспортировано файлов: {total_files}\n"
                f"Папка: {folder}"
            )
        else:
            QMessageBox.information(self, "Нет файлов", "У клиента нет файлов для экспорта.")

    def export_client_orders(self):
        """Экспорт заказов клиента с выбором опций"""
        if not self.current_client:
            return
            
        dialog = ClientOrdersExportDialog(self.current_client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            export_data = dialog.get_export_data()
            
            if not export_data['selected_orders']:
                QMessageBox.warning(self, "Ошибка", "Не выбрано ни одного заказа для экспорта")
                return
            
            # Выбор папки для экспорта
            folder = QFileDialog.getExistingDirectory(self, "Выберите папку для экспорта")
            if not folder:
                return
            
            # Экспорт JSON
            json_path = os.path.join(folder, f"{self.current_client.name}_заказы.json")
            try:
                orders_data = []
                for order in export_data['selected_orders']:
                    order_dict = {
                        'id': order.id,
                        'service_type': order.service_type,
                        'price': order.price,
                        'advance': order.advance,
                        'created_at': order.created_at,
                        'deadline': order.deadline,
                        'status': order.status,
                        'files': [{'name': f.name, 'path': f.path} for f in order.files],
                        'payments': [p.to_dict() for p in order.payments]
                    }
                    orders_data.append(order_dict)
                
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(orders_data, f, ensure_ascii=False, indent=4)
                
                # Если нужно экспортировать файлы
                if export_data['include_files']:
                    files_folder = os.path.join(folder, "файлы_заказов")
                    os.makedirs(files_folder, exist_ok=True)
                    
                    for order in export_data['selected_orders']:
                        order_folder = os.path.join(files_folder, order.service_type)
                        os.makedirs(order_folder, exist_ok=True)
                        
                        for file in order.files:
                            if os.path.exists(file.path):
                                try:
                                    shutil.copy2(file.path, os.path.join(order_folder, file.name))
                                except Exception as e:
                                    print(f"Ошибка копирования файла {file.name}: {e}")
                
                QMessageBox.information(
                    self,
                    "Экспорт завершен",
                    f"Экспортировано заказов: {len(export_data['selected_orders'])}\n"
                    f"JSON файл: {json_path}\n"
                    f"{'Файлы экспортированы в отдельную папку' if export_data['include_files'] else 'Файлы не экспортированы'}"
                )
                
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось экспортировать заказы: {e}")

    def delete_client(self, clients=None):
        target_clients = []
        if clients:
            target_clients = clients
        else:
            # Get from selection
            selected_items = self.cl_list.selectedItems()
            if selected_items:
                for item in selected_items:
                    c_id = item.data(Qt.ItemDataRole.UserRole)
                    client = next((c for c in self.clients if c.id == c_id), None)
                    if client:
                        target_clients.append(client)
            elif self.current_client:
                target_clients = [self.current_client]
        
        if not target_clients:
            QMessageBox.warning(self, "Внимание", "Выберите клиентов для удаления.")
            return
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Подтверждение удаления")
        
        if len(target_clients) == 1:
            msg_box.setText(f"Вы уверены, что хотите удалить клиента '{target_clients[0].name}'?")
        else:
            msg_box.setText(f"Вы уверены, что хотите удалить {len(target_clients)} клиентов?")
            
        msg_box.setInformativeText("Как удалить файлы клиентов?")
        msg_box.setIcon(QMessageBox.Icon.Warning)
        
        btn_delete_prog = msg_box.addButton("Удалить только из программы", QMessageBox.ButtonRole.YesRole)
        btn_delete_disk = msg_box.addButton("Удалить с компьютера", QMessageBox.ButtonRole.DestructiveRole)
        btn_cancel = msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        
        # Получаем путь к папке с файлами для отображения в пояснении
        db_folder = os.path.dirname(self.storage.path)
        attached_files_dir = os.path.join(db_folder, "attached_files")
        
        msg_box.exec()
        
        clicked = msg_box.clickedButton()
        if clicked == btn_cancel:
            return
            
        delete_from_disk = (clicked == btn_delete_disk)
        
        if delete_from_disk:
            # Показываем дополнительное предупреждение с путем
            warn_box = QMessageBox(self)
            warn_box.setWindowTitle("Удаление файлов")
            warn_box.setText(f"Файлы из папки:\n{attached_files_dir}\n\nбудут удалены.")
            warn_box.setInformativeText("Продолжить?")
            warn_box.setIcon(QMessageBox.Icon.Critical)
            
            btn_yes = warn_box.addButton("Да", QMessageBox.ButtonRole.YesRole)
            btn_no = warn_box.addButton("Отмена", QMessageBox.ButtonRole.NoRole)
            
            warn_box.exec()
            
            if warn_box.clickedButton() != btn_yes:
                return

        def is_safe_to_delete(file_path, safe_root):
            try:
                return os.path.commonpath([os.path.abspath(file_path), os.path.abspath(safe_root)]) == os.path.abspath(safe_root)
            except:
                return False
            
        for c in target_clients:
            if c in self.clients:
                # Если нужно удалить с диска, проходимся по файлам
                if delete_from_disk:
                     for order in c.orders:
                        for file in order.files:
                            # Удаляем файл, если он существует и находится внутри папки базы данных
                            if os.path.exists(file.path) and is_safe_to_delete(file.path, db_folder):
                                try:
                                    os.remove(file.path)
                                except Exception as e:
                                    logger.error(f"Не удалось удалить файл {file.path}: {e}")
                                    
                self.clients.remove(c)
        
        # Reset current client if it was deleted
        if self.current_client in target_clients:
            self.current_client = None
            self.clear_profile_layout()
        
        self.refresh_list()
        self.save_db()
        
        if delete_from_disk:
            # Пытаемся удалить пустые папки в attached_files если они остались
            # Это опционально, но полезно для чистоты
            try:
                db_folder = os.path.dirname(self.storage.path)
                attached_files_dir = os.path.join(db_folder, "attached_files")
                if os.path.exists(attached_files_dir):
                    # Удаляем пустые папки рекурсивно
                     for root, dirs, files in os.walk(attached_files_dir, topdown=False):
                        for name in dirs:
                            try:
                                os.rmdir(os.path.join(root, name))
                            except:
                                pass
            except:
                pass

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

    def show_client_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
            }
            QMenu::item {
                padding: 5px 20px;
            }
            QMenu::item:selected {
                background-color: #3D3D3D;
            }
        """)

        selected_items = self.cl_list.selectedItems()
        item_at_pos = self.cl_list.itemAt(pos)

        # Если кликнули по элементу или есть выделение
        if item_at_pos or selected_items:
            if len(selected_items) > 1:
                # Если выбрано несколько клиентов - только удаление
                delete_action = QAction(f"🗑 Удалить выбранных ({len(selected_items)})", self)
                delete_action.triggered.connect(self.delete_client)
                menu.addAction(delete_action)
                menu.addSeparator()
            elif item_at_pos:
                # Если выбран один - полный функционал
                client_id = item_at_pos.data(Qt.ItemDataRole.UserRole)
                client = next((c for c in self.clients if c.id == client_id), None)
                
                if client:
                    add_order_action = QAction("➕ Добавить заказ", self)
                    add_order_action.triggered.connect(lambda: self.quick_add_order(client))
                    menu.addAction(add_order_action)
                    
                    settings_action = QAction("⚙ Настройки клиента", self)
                    settings_action.triggered.connect(lambda: self.open_specific_client_settings(client))
                    menu.addAction(settings_action)
                    
                    delete_action = QAction("🗑 Удалить клиента", self)
                    delete_action.triggered.connect(lambda: self.delete_specific_client(client))
                    menu.addAction(delete_action)
                    menu.addSeparator()

        # Меню сортировки (всегда доступно)
        sort_menu = menu.addMenu("🔃 Сортировка")
        sort_options = ["Имя (А-Я)", "Имя (Я-А)", "Новые заказы", "Старые заказы", "Срочные"]
        for option in sort_options:
            action = QAction(option, self)
            action.triggered.connect(lambda checked=False, o=option: self.sort_clients(o))
            sort_menu.addAction(action)
        
        menu.exec(self.cl_list.mapToGlobal(pos))

    def open_specific_client_settings(self, client):
        self.current_client = client
        self.render_client_profile()
        self.open_client_settings()

    def delete_specific_client(self, client):
        self.delete_client([client])

    def sort_clients(self, mode):
        if mode == "Имя (А-Я)":
            self.clients.sort(key=lambda x: x.name.lower())
        elif mode == "Имя (Я-А)":
            self.clients.sort(key=lambda x: x.name.lower(), reverse=True)
        elif mode == "Новые заказы":
            # Сортировка по дате создания последнего заказа
            def get_last_order_date(client):
                if not client.orders:
                    return datetime.min
                try:
                    # Берем самый свежий заказ
                    dates = []
                    for o in client.orders:
                         # Парсим дату. Формат "dd.MM.yyyy HH:mm" или "dd.MM.yyyy"
                        d_str = o.created_at
                        if " " in d_str:
                            dt = datetime.strptime(d_str, "%d.%m.%Y %H:%M")
                        else:
                            dt = datetime.strptime(d_str, "%d.%m.%Y")
                        dates.append(dt)
                    return max(dates)
                except:
                    return datetime.min
            
            self.clients.sort(key=get_last_order_date, reverse=True)
            
        elif mode == "Старые заказы":
             # Сортировка по дате создания последнего заказа (наоборот)
            def get_last_order_date(client):
                if not client.orders:
                    return datetime.min
                try:
                    # Берем самый свежий заказ
                    dates = []
                    for o in client.orders:
                        d_str = o.created_at
                        if " " in d_str:
                            dt = datetime.strptime(d_str, "%d.%m.%Y %H:%M")
                        else:
                            dt = datetime.strptime(d_str, "%d.%m.%Y")
                        dates.append(dt)
                    return max(dates)
                except:
                    return datetime.min
                    
            self.clients.sort(key=get_last_order_date)

        elif mode == "Срочные":
            # Сортировка по дедлайну (ближайший дедлайн сверху)
            def get_nearest_deadline(client):
                if not client.orders:
                    return datetime.max
                
                deadlines = []
                for o in client.orders:
                    if o.status != "Завершен" and o.deadline:
                        try:
                            dt = datetime.strptime(o.deadline, "%d.%m.%Y")
                            deadlines.append(dt)
                        except:
                            pass
                
                if not deadlines:
                    return datetime.max
                return min(deadlines)
            
            self.clients.sort(key=get_nearest_deadline)

        self.refresh_list()

    def refresh_list(self):
        self.cl_list.clear()
        if hasattr(self, 'db_info'):
            self.db_info.setText(f"Клиентов: {len(self.clients)}")
        
        # Если вызвана не из sort_clients, возможно стоит сохранить порядок?
        # Но у нас есть self.clients, который мы сортируем in-place.
        # Поэтому просто отображаем текущее состояние self.clients
        
        for client in self.clients:
            item = QListWidgetItem(client.name)
            item.setData(Qt.ItemDataRole.UserRole, client.id)
            
            # Настройка шрифта для соответствия предыдущему стилю
            font = item.font()
            font.setPixelSize(13)
            font.setBold(True)
            item.setFont(font)
            
            self.cl_list.addItem(item)

    def quick_add_order(self, client):
        self.current_client = client
        # Визуально выделяем клиента
        for i in range(self.cl_list.count()):
            item = self.cl_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == client.id:
                self.cl_list.setCurrentItem(item)
                self.select_client(item)
                break
        self.add_order()

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
            logger.info(f"Добавлен новый клиент: {new_client.name} (ID: {new_client.id})")
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
                border-left: 1px solid #444444;
                background: #3D3D3D;
                width: 25px;
                border-top-right-radius: 3px;
                border-bottom-right-radius: 3px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 6px solid #00D1FF;
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
        service_combo.addItems(["Монтаж звука", "Монтаж аудио", "Оркестровка", "Нотный набор", "Сведение", "Аранжировка", "Мастеринг", "Консультация"])
        form_layout.addRow(service_label, service_combo)
        
        # Стоимость и валюта
        price_layout = QHBoxLayout()
        price_edit = QLineEdit("0")
        
        currency_combo = QComboBox()
        currency_combo.addItems(["RUB", "USD", "EUR", "UAH"])
        currency_combo.setFixedWidth(70)
        
        price_layout.addWidget(price_edit)
        price_layout.addWidget(currency_combo)
        
        form_layout.addRow("Стоимость:", price_layout)
        
        deadline_label = QLabel("Срок выполнения:")
        deadline_edit = QLineEdit(datetime.now().strftime("%d.%m.%Y"))
        form_layout.addRow(deadline_label, deadline_edit)
        
        layout.addLayout(form_layout)
        
        # Группа финансов
        finance_group = QGroupBox("Финансы")
        finance_layout = QFormLayout(finance_group)
        finance_layout.setSpacing(10)
        
        advance_label = QLabel("Аванс:")
        advance_edit = QLineEdit("0")
        finance_layout.addRow(advance_label, advance_edit)
        
        layout.addWidget(finance_group)
        layout.addStretch()
        
        # Кнопки
        buttons = QHBoxLayout()
        create_btn = QPushButton("Создать заказ")
        create_btn.setFixedWidth(140)
        create_btn.setStyleSheet("""
            QPushButton {
                background-color: #28A745;
                color: white;
                font-weight: bold;
                padding: 8px 15px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setFixedWidth(100)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6C757D;
                color: white;
                padding: 8px 15px;
                border-radius: 4px;
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
                    currency=currency_combo.currentText(),
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
                logger.info(f"Добавлен новый заказ для {self.current_client.name}: {new_order.service_type} (ID: {new_order.id})")
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

    def open_settings(self):
        SettingsDialog(self).exec()

    def open_client_settings(self):
        if not self.current_client:
            return
        
        dialog = ClientSettingsDialog(self.current_client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Обновляем данные клиента
            self.current_client.name = dialog.name_edit.text()
            self.current_client.email = dialog.email_edit.text()
            self.current_client.social_link = dialog.link_edit.text()
            self.current_client.notes = dialog.notes_edit.toPlainText()
            self.save_db()
            self.render_client_profile()
            self.refresh_list()
    
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
                
                # Ищем существующий заказ или создаем новый
                target_order = next((o for o in client.orders if o.service_type == order_name), None)
                
                if not target_order:
                    # Пытаемся определить дату заказа по дате создания самого раннего файла
                    order_date = datetime.now()
                    if files:
                        try:
                            # Берем дату модификации первого файла
                            first_file_path = files[0][1] # files это список кортежей (name, path)
                            timestamp = os.path.getmtime(first_file_path)
                            order_date = datetime.fromtimestamp(timestamp)
                        except Exception:
                            pass
                    
                    target_order = Order(
                        id=str(uuid.uuid4()),
                        service_type=order_name,
                        price=0.0,
                        advance=0.0,
                        created_at=order_date.strftime("%d.%m.%Y %H:%M"),
                        deadline=order_date.strftime("%d.%m.%Y"), # Ставим дедлайн как дату создания пока
                        status="В работе",
                        files=[],
                        payments=[]
                    )
                    client.orders.append(target_order)
                    order_count += 1
                
                # Добавляем файлы в заказ
                for file_name, file_path in files:
                    # Проверяем на дубликаты файлов
                    if not any(f.path == file_path for f in target_order.files):
                        project_file = ProjectFile(
                            path=file_path,
                            name=file_name,
                            is_finished=False
                        )
                        target_order.files.append(project_file)
            
            # Сохраняем и обновляем интерфейс
            self.save_db()
            self.refresh_list()
            
            # Если есть клиенты, выбираем первого
            if self.clients and self.current_client is None:
                self.current_client = self.clients[0]
                self.render_client_profile()
            
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
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Подтверждение импорта")
                msg_box.setText(f"Найдено клиентов: {len(imported_clients)}")
                msg_box.setInformativeText("Текущая база данных будет заменена. Продолжить?")
                msg_box.setIcon(QMessageBox.Icon.Warning)
                
                btn_yes = msg_box.addButton("Да", QMessageBox.ButtonRole.YesRole)
                btn_no = msg_box.addButton("Нет", QMessageBox.ButtonRole.NoRole)
                
                msg_box.exec()
                
                if msg_box.clickedButton() == btn_yes:
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
        self.backup_settings()
        event.accept()

    def backup_settings(self):
        """Создает резервную копию настроек"""
        try:
            backup_dir = "settings_backups"
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = os.path.join(backup_dir, f"crm_settings_{timestamp}.json")
            
            # Сохраняем текущие настройки в backup
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(self.app_settings, f, ensure_ascii=False, indent=4)
                
            # Удаляем старые, оставляем только 5 последних
            backups = sorted(glob.glob(os.path.join(backup_dir, "crm_settings_*.json")))
            while len(backups) > 5:
                os.remove(backups.pop(0))
                
        except Exception as e:
            print(f"Ошибка создания бэкапа настроек: {e}")

    def delete_all_files(self):
        """Удаляет все файлы из базы данных (физически и ссылки)"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Удаление ВСЕХ файлов")
        msg_box.setText("Как вы хотите удалить файлы?")
        msg_box.setInformativeText(
            "Выберите вариант очистки:\n\n"
            "• Удалить только из программы: удалятся ссылки, файлы на диске останутся нетронутыми.\n"
            "• Удалить с компьютера: удалятся ссылки И сами файлы."
        )
        msg_box.setIcon(QMessageBox.Icon.Warning)
        
        btn_program_only = msg_box.addButton("Удалить только из программы", QMessageBox.ButtonRole.YesRole)
        # Определяем путь к папке с файлами базы
        db_folder = os.path.dirname(self.storage.path)
        attached_files_dir = os.path.join(db_folder, "attached_files")
        
        msg_box.exec()
        
        clicked = msg_box.clickedButton()
        
        if clicked == btn_cancel:
            return
            
        delete_from_disk = (clicked == btn_disk_also)
        
        if delete_from_disk:
            # Показываем дополнительное предупреждение с путем
            warn_box = QMessageBox(self)
            warn_box.setWindowTitle("Удаление файлов")
            warn_box.setText(f"Файлы из папки:\n{attached_files_dir}\n\nбудут удалены.")
            warn_box.setInformativeText("Продолжить?")
            warn_box.setIcon(QMessageBox.Icon.Critical)
            
            btn_yes = warn_box.addButton("Да", QMessageBox.ButtonRole.YesRole)
            btn_no = warn_box.addButton("Отмена", QMessageBox.ButtonRole.NoRole)
            
            warn_box.exec()
            
            if warn_box.clickedButton() != btn_yes:
                return
        
        deleted_count = 0
        
        # 1. Очищаем списки файлов в объектах
        for client in self.clients:
            for order in client.orders:
                deleted_count += len(order.files)
                order.files = []
        
        # 2. Удаляем физическую папку attached_files если нужно
        if delete_from_disk and os.path.exists(attached_files_dir):
            try:
                shutil.rmtree(attached_files_dir)
                # Создаем пустую обратно, чтобы не было ошибок при добавлении
                os.makedirs(attached_files_dir, exist_ok=True)
            except Exception as e:
                logger.error(f"Ошибка удаления папки с файлами: {e}")
                QMessageBox.warning(self, "Ошибка", f"Не удалось полностью удалить файлы с диска: {e}")
        
        self.save_db()
        self.render_client_profile()
        
        info_text = f"Удалено ссылок на файлы: {deleted_count}"
        if delete_from_disk:
            info_text += "\nФайлы также удалены с диска (из папки базы данных)."
        else:
            info_text += "\nФайлы на диске не были затронуты."
            
        QMessageBox.information(self, "Успех", info_text)

    def delete_database_full(self):
        """Полное удаление базы данных"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Удаление ВСЕЙ базы данных")
        msg_box.setText("ВНИМАНИЕ! Вы собираетесь удалить ВСЮ базу данных.")
        msg_box.setInformativeText(
            "Это удалит всех клиентов и все заказы из программы.\n"
            "Восстановить данные будет невозможно (если нет бэкапа).\n\n"
            "Что делать с файлами на диске?"
        )
        msg_box.setIcon(QMessageBox.Icon.Critical)
        
        btn_prog_only = msg_box.addButton("Оставить файлы на диске", QMessageBox.ButtonRole.YesRole)
        btn_disk_also = msg_box.addButton("Удалить с диска", QMessageBox.ButtonRole.DestructiveRole)
        btn_cancel = msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        
        # Определяем путь к папке с файлами базы
        db_folder = os.path.dirname(self.storage.path)
        attached_files_dir = os.path.join(db_folder, "attached_files")
        
        msg_box.exec()
        
        clicked = msg_box.clickedButton()
        if clicked == btn_cancel:
            return
            
        delete_files_disk = (clicked == btn_disk_also)
        
        if delete_files_disk:
            # Показываем дополнительное предупреждение с путем
            warn_box = QMessageBox(self)
            warn_box.setWindowTitle("Удаление файлов")
            warn_box.setText(f"Файлы из папки:\n{attached_files_dir}\n\nбудут удалены.")
            warn_box.setInformativeText("Продолжить?")
            warn_box.setIcon(QMessageBox.Icon.Critical)
            
            btn_yes = warn_box.addButton("Да", QMessageBox.ButtonRole.YesRole)
            btn_no = warn_box.addButton("Отмена", QMessageBox.ButtonRole.NoRole)
            
            warn_box.exec()
            
            if warn_box.clickedButton() != btn_yes:
                return
        
        # 1. Удаляем файлы с диска если нужно
        if delete_files_disk:
            db_folder = os.path.dirname(self.storage.path)
            attached_files_dir = os.path.join(db_folder, "attached_files")
            if os.path.exists(attached_files_dir):
                try:
                    shutil.rmtree(attached_files_dir)
                except Exception as e:
                    logger.error(f"Ошибка удаления папки файлов: {e}")
        
        # 2. Очищаем список клиентов в памяти
        self.clients = []
        self.current_client = None
        
        # 3. Сохраняем пустую базу (это перезапишет файл json)
        self.save_db()
        
        # 4. Обновляем интерфейс
        self.refresh_list()
        self.clear_profile_layout()
        self.update_dash()
        
        msg = "База данных полностью очищена."
        if delete_files_disk:
            msg += "\nФайлы также были удалены с диска."
        else:
            msg += "\nФайлы на диске остались нетронутыми."
            
        QMessageBox.information(self, "Успех", msg)
