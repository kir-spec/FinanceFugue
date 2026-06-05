
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
    QDialog, QFormLayout, QComboBox, QGroupBox, QGridLayout,
    QCalendarWidget, QToolButton, QGraphicsDropShadowEffect, QSizePolicy
)
from PySide6.QtGui import QPalette, QColor, QAction, QKeySequence, QShortcut, QDesktopServices, QIcon, QGuiApplication
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QSequentialAnimationGroup, QSize, QPoint, QAbstractAnimation, QUrl

from .models import Client, Order, ProjectFile
from .sqlite_storage import SQLiteStorage # Keep import for type hinting/reference
from .dialogs import (
    FirstRunDialog, SettingsDialog, ClientSettingsDialog,
    ClientOrdersExportDialog, FolderImportDialog, StatsDetailDialog,
    animate_dialog_open
)
from .widgets import OrderWidget, AdaptiveDashLabel, ClientStatsWidget, ClientListWidget, HoverShadowFrame, AutoResizeLabel
from .backend import CRMBackend # Импортируем backend

# --- ГЛАВНОЕ ОКНО ---
class FinanceFugue(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.info("Инициализация приложения")
        self.app_settings = self.load_settings()
        
        self.backend = CRMBackend(main_window_settings=self.app_settings)
        
        self.backend.securityRequest.connect(self.handle_security_request)
        
        self.backend.init_security_check()
        
        self.clients = self.backend.get_all_clients_from_backend()
        self.current_client = None
        self.init_ui()
        self.setup_shortcuts()

    def handle_security_request(self, request_type):
        if request_type == "setup":
            if not self.show_first_run_dialog():
                sys.exit(0)
        elif request_type == "unlock":
            self.show_unlock_dialog()
            
        self.clients = self.backend.get_all_clients_from_backend()
        self.refresh_list()
        self.update_dash()

        if self.app_settings.get('create_shortcut', False):
            self.app_settings['create_shortcut'] = False
            self.save_settings()
            logger.info("Флаг создания ярлыка обработан.")

    def show_unlock_dialog(self):
        while True:
            pwd, ok = QInputDialog.getText(self, "Вход в систему", "Введите пароль:", QLineEdit.EchoMode.Password)
            if not ok:
                sys.exit(0)
            
            if self.backend.unlock_database(pwd):
                break
            else:
                QMessageBox.warning(self, "Ошибка", "Неверный пароль")

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
            first_run_settings = dialog.get_settings()
            
            self.app_settings.update(first_run_settings)
            
            db_path = first_run_settings.get('database_path')
            file_storage_mode = first_run_settings.get('file_storage_mode')
            encryption_enabled = first_run_settings.get('encryption_enabled')
            app_password = first_run_settings.get('app_password')
            
            if self.backend.setup_initial_config(db_path, file_storage_mode, encryption_enabled, app_password):
                self.app_settings['first_run_completed'] = True
                self.save_settings()
                logger.info("Первоначальная настройка завершена и сохранена.")
                return True
            else:
                logger.error("Ошибка при применении первоначальных настроек.")
                QMessageBox.critical(self, "Ошибка", "Не удалось применить настройки безопасности.")
                return False
        return False

    def init_ui(self):
        self.setWindowTitle(" ")
        self.resize(900, 750)
        self.setWindowIcon(QIcon("images/FinanceFugue.ico"))
        
        # Center on screen (Fixed)
        screen = QGuiApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            x = (screen_geometry.width() - self.width()) // 2
            y = (screen_geometry.height() - self.height()) // 2
            self.move(x, y)
        
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

        self.title_label = AutoResizeLabel("FinanceFugue", min_size=20, max_size=50)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-weight: bold; color: #00D1FF; padding: 5px 0;")
        main_layout.addWidget(self.title_label)
        
        # Панель статистики
        self.dash = HoverShadowFrame()
        self.dash.setObjectName("DashboardFrame")
        self.dash.setStyleSheet("""
            QFrame#DashboardFrame {
                background-color: #252525;
                border: 1px solid #3D3D3D;
                border-radius: 8px;
            }
        """)
        self.dash.setFixedHeight(80)
        self.dash_layout = QHBoxLayout(self.dash)
        self.dash_layout.setContentsMargins(0, 0, 0, 0)
        self.dash_layout.setSpacing(8)
        self.dash_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.dash)

        # Основная рабочая область
        self.work_area = QHBoxLayout()
        self.work_area.setSpacing(5)

        # Левая панель с клиентами
        self.left_panel = QWidget()
        self.left_panel.setMinimumWidth(250)
        self.left_panel.setMaximumWidth(250)
        
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        # Верхний блок заголовка панели
        self.header_panel = QWidget()
        # Увеличиваем высоту для поиска, если нужно, но пока оставим компактным
        self.header_panel.setFixedHeight(34)
        header_layout = QHBoxLayout(self.header_panel)
        header_layout.setContentsMargins(5, 0, 5, 0)
        header_layout.setSpacing(5)
        
        # Кнопка сворачивания/разворачивания
        self.toggle_btn = QPushButton("👤 КЛИЕНТЫ")
        self.toggle_btn.clicked.connect(self.toggle_sidebar)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setFixedHeight(30)
        self.toggle_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
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
        
        # Поле поиска
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск...")
        self.search_input.textChanged.connect(self.filter_clients)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #1A1A1A;
                border: 1px solid #3D3D3D;
                border-radius: 12px;
                padding: 4px 10px;
                font-size: 12px;
                color: white;
            }
            QLineEdit:focus {
                border-color: #00D1FF;
            }
        """)
        header_layout.addWidget(self.search_input)
        
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
        
        self.cl_list = ClientListWidget()
        self.cl_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.cl_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.cl_list.customContextMenuRequested.connect(self.show_client_context_menu)
        self.cl_list.itemClicked.connect(self.select_client)
        self.cl_list.folderDropped.connect(self.handle_dropped_folder)
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
        
        btn_files = QPushButton("📁 менеджер файлов")
        btn_files.clicked.connect(self.open_global_file_manager)
        btn_files.setStyleSheet("""
            background-color: #2D2D2D;
            color: white;
            font-size: 13px;
            padding: 6px;
        """)
        bottom_layout.addWidget(btn_files)

        settings_help_layout = QHBoxLayout()
        settings_help_layout.setSpacing(5)

        btn_set = QPushButton("⚙ Настройки")
        btn_set.clicked.connect(self.open_settings)
        btn_set.setStyleSheet("""
            background-color: #2D2D2D;
            color: white;
            font-size: 13px;
            padding: 6px;
        """)
        
        btn_help = QPushButton("❓")
        btn_help.setFixedWidth(30)
        btn_help.clicked.connect(self.show_app_help)
        btn_help.setStyleSheet("""
            background-color: #2D2D2D;
            color: #00D1FF;
            font-size: 14px;
            font-weight: bold;
            padding: 4px;
        """)
        
        settings_help_layout.addWidget(btn_set, 1)
        settings_help_layout.addWidget(btn_help)
        bottom_layout.addLayout(settings_help_layout)

        self.db_info = QLabel(f"Клиентов: {len(self.clients)}")
        self.db_info.setStyleSheet("color: #888888; font-size: 11px; padding: 5px 5px; background-color: #252525; border-radius: 4px;")
        bottom_layout.addWidget(self.db_info)
        
        left_layout.addWidget(self.bottom_panel)
        left_layout.addStretch()
        
        self.work_area.addWidget(self.left_panel)

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
        self.work_area.addWidget(self.scroll, 1)

        main_layout.addLayout(self.work_area)
        
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
        
        # Новые горячие клавиши
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(lambda: self.search_input.setFocus())
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self.open_global_file_manager)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self).activated.connect(self.open_settings)
        QShortcut(QKeySequence("F5"), self).activated.connect(self.refresh_list)

    def toggle_sidebar(self):
        start_width = self.left_panel.width()
        collapsed_width = 13
        expanded_width = 250
        
        if start_width > collapsed_width:
             # Collapsing
             end_width = collapsed_width
             self.toggle_btn.setText("▶")
             self.search_input.hide() # Прячем поиск
             
             if self.header_panel.layout():
                 self.header_panel.layout().setContentsMargins(0, 0, 0, 0)

             # Сбрасываем ограничения размера
             self.toggle_btn.setMinimumSize(0, 30)
             self.toggle_btn.setMaximumSize(16777215, 30)
             
             # Выравниваем стрелку по центру
             self.toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #00D1FF;
                    border: none;
                    font-weight: bold;
                    font-size: 10px;
                    text-align: center;
                    padding: 0px;
                }
                QPushButton:hover {
                    color: #FFFFFF;
                    background-color: #333333;
                }
            """)
             # Убираем фон панели заголовка
             self.header_panel.setStyleSheet("background: transparent; border: none;")
             self.work_area.setSpacing(2)
             
        else:
             # Expanding
             end_width = expanded_width
             self.toggle_btn.setText("👤 КЛИЕНТЫ")
             self.search_input.show()
             
             if self.header_panel.layout():
                 self.header_panel.layout().setContentsMargins(5, 0, 5, 0)
             
             # Возвращаем фон панели заголовка
             self.header_panel.setStyleSheet("border-bottom: 1px solid #3D3D3D; background-color: #252525;")
             self.work_area.setSpacing(15)

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
            ("📋 В РАБОТЕ", in_work, "#00D1FF", False),
            ("✅ ВЫПОЛНЕНО", done, "#28A745", False),
            ("💰 АВАНСЫ", total_advance, "#FFD700", True),
            ("💳 ДОЛГИ", total_debt, "#FF4B2B" if total_debt > 0 else "#28A745", True),
            ("💵 КАССА", total_cash, "#28A745", True)
        ]
        
        # Проверяем, созданы ли уже виджеты. Если да - обновляем их значения для анимации.
        # Если нет - создаем заново.
        if self.dash_layout.count() == 0:
            self.dash_widgets = {} # Map: title -> AdaptiveDashLabel
            for title, value, color, is_money in stats:
                stat_widget, label = self.create_stat_widget(title, value, color, is_money)
                self.dash_layout.addWidget(stat_widget, 2 if is_money else 1)
                self.dash_widgets[title] = label
        else:
            # Обновляем существующие
            for title, value, color, is_money in stats:
                if title in self.dash_widgets:
                    self.dash_widgets[title].set_value(value)
                    self.dash_widgets[title].text_color = color # Update color in case debt changed sign

    def create_stat_widget(self, title, value, color, is_money):
        widget = QFrame()
        widget.setStyleSheet("""
            QFrame {
                background-color: transparent; /* Теперь фон у родительского дашборда */
                border: none;
                /* border-right: 1px solid #3D3D3D; */ /* Разделители можно добавить по желанию */
            }
        """)
        
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 11px; color: #888888; font-weight: bold; border: none; background: transparent;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFixedHeight(20)
        
        value_label = AdaptiveDashLabel(value, color, is_money)
        # Эффект "жидкого стекла" для цифр
        value_label.setStyleSheet(f"""
            color: {color};
            font-weight: bold;
            border: 1px solid rgba(255, 255, 255, 0.1);
            background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                            stop:0 rgba(255, 255, 255, 0.05),
                                            stop:1 rgba(255, 255, 255, 0.01));
            border-radius: 4px;
            padding: 2px 0;
        """)
        
        layout.addWidget(value_label)
        layout.addWidget(title_label)
        
        return widget, value_label

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
        # Используем AutoResizeLabel для длинных имен
        name_label = AutoResizeLabel(client.name.upper(), max_size=24, min_size=14)
        name_label.setStyleSheet("font-weight: bold; color: #00D1FF; padding: 5px 0;")
        name_row.addWidget(name_label)
        # Убираем addStretch, чтобы label мог занимать всю ширину для расчета
        # name_row.addStretch()
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

        # --- Блок иконок соцсетей ---
        social_buttons_widget = QWidget()
        social_buttons_widget.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border: none;
            }
        """)
        social_buttons_layout = QHBoxLayout(social_buttons_widget)
        social_buttons_layout.setContentsMargins(10, 0, 0, 0)
        social_buttons_layout.setSpacing(5)

        # Словарь: атрибут -> (иконка, префикс URL)
        social_links = {
            'telegram': ('T', 'https://t.me/'),
            'vk': ('VK', 'https://'),
            'facebook': ('F', 'https://'),
            'email': ('@', 'mailto:')
        }

        for attr, (icon, prefix) in social_links.items():
            link = getattr(client, attr, '')
            btn = QPushButton(icon)
            btn.setFixedSize(36, 36)

            colors = {
                'telegram': ("#0088cc", "#00AADD"),
                'vk':       ("#4c75a3", "#5C85B3"),
                'facebook': ("#3b5998", "#4B69A8"),
                'email':    ("#757575", "#858585")
            }
            normal_color, hover_color = colors.get(attr, ("#666666", "#777777"))

            btn.setStyleSheet(f"""
                QPushButton {{
                    font-size: 12px;
                    font-weight: bold;
                    color: white;
                    background-color: {normal_color};
                    border-radius: 8px; /* Rounded corners */
                    border: none;
                }}
                QPushButton:hover {{
                    background-color: {hover_color};
                }}
                QPushButton:pressed {{
                    background-color: {normal_color};
                }}
            """)

            btn.setToolTip(f"Открыть {attr.capitalize()}")
            btn.clicked.connect(lambda checked=False, a=attr, p=prefix: self.open_social_link(a, p))
            social_buttons_layout.addWidget(btn)

        buttons_row.addWidget(social_buttons_widget)
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
        # Изначально скрыто и высота 0 для анимации
        self.notes_edit.setMaximumHeight(0)
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
        self.client_stats_widget = ClientStatsWidget(client_stats)
        self.client_stats_widget.sum_clicked.connect(self.show_sum_details)
        self.client_stats_widget.paid_clicked.connect(self.show_paid_details)
        self.client_stats_widget.adv_clicked.connect(self.show_adv_details)
        self.client_stats_widget.debt_clicked.connect(self.show_debt_details)
        self.profile_layout.addWidget(self.client_stats_widget)
        
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
            empty_layout.addWidget(empty_btn, 0, Qt.AlignmentFlag.AlignCenter)
            
            self.profile_layout.addWidget(empty_frame)
        
        self.profile_layout.addStretch()

    def calculate_client_stats(self, client):
        # Сумма всех заказов (price)
        total_sum = sum(o.price for o in client.orders)
        
        # Всего оплачено (received)
        total_received = sum(o.total_received for o in client.orders)
        
        # Авансы (advance)
        total_advance = sum(o.advance for o in client.orders)
        
        # Долг рассчитывается по всем заказам, так как статус "Завершен" не означает оплату
        total_debt = sum(o.debt for o in client.orders)
        
        return {
            'total_sum': total_sum,
            'total_received': total_received,
            'total_advance': total_advance,
            'total_debt': total_debt
        }

    def update_client_stats(self):
        """Обновление статистики текущего клиента"""
        if self.current_client and hasattr(self, 'client_stats_widget'):
            stats = self.calculate_client_stats(self.current_client)
            self.client_stats_widget.update_stats(stats)

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
        btn_help = msg_box.addButton("❓ Справка", QMessageBox.ButtonRole.HelpRole)
        btn_cancel = msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        
        delete_from_disk = (clicked == btn_delete_disk)
        
        if self.backend.delete_clients_with_files(target_clients, delete_from_disk):
            self.clients = self.backend.get_all_clients_from_backend()
            
            if self.current_client in target_clients:
                self.current_client = None
                self.clear_profile_layout()
            
            self.refresh_list()
            self.update_dash()
            self.backend.successMessage.emit("Клиент(ы) успешно удален(ы).")
        else:
            self.backend.errorMessage.emit("Ошибка при удалении клиента(ов).")

    def toggle_notes(self):
        if not self.current_client:
            return

        is_visible = self.notes_edit.isVisible() and self.notes_edit.maximumHeight() > 0

        if not is_visible:
            # === ОТКРЫТИЕ (OPENING) ===
            self.notes_edit.setVisible(True)
            self.notes_edit.setMinimumHeight(0)
            
            # Эффект свечения (Fire/Glow)
            shadow = QGraphicsDropShadowEffect(self.notes_edit)
            shadow.setBlurRadius(20)
            shadow.setColor(QColor(0, 0, 0, 0)) # Start transparent
            shadow.setOffset(0, 0)
            self.notes_edit.setGraphicsEffect(shadow)
            
            # Группа анимаций
            self.notes_anim_group = QParallelAnimationGroup()
            
            # 1. Анимация высоты (Раскрытие)
            anim_height = QPropertyAnimation(self.notes_edit, b"maximumHeight")
            anim_height.setDuration(600)
            anim_height.setStartValue(0)
            anim_height.setEndValue(120)
            anim_height.setEasingCurve(QEasingCurve.OutBack) # Эффект пружины
            
            # 2. Анимация "Огня/Перелива" (Последовательная смена цветов)
            anim_color_seq = QSequentialAnimationGroup()
            
            # Фаза 1: Вспышка (Оранжевый)
            a1 = QPropertyAnimation(shadow, b"color")
            a1.setDuration(200)
            a1.setStartValue(QColor(0, 0, 0, 0))
            a1.setEndValue(QColor(255, 69, 0, 200)) # Red-Orange
            
            # Фаза 2: Горение (Золотой)
            a2 = QPropertyAnimation(shadow, b"color")
            a2.setDuration(400)
            a2.setStartValue(QColor(255, 69, 0, 200))
            a2.setEndValue(QColor(255, 215, 0, 150)) # Gold
            
            # Фаза 3: Остывание (в цвет темы)
            a3 = QPropertyAnimation(shadow, b"color")
            a3.setDuration(600)
            a3.setStartValue(QColor(255, 215, 0, 150))
            a3.setEndValue(QColor(0, 209, 255, 100)) # Cyan/Blue (Theme glow)
            
            anim_color_seq.addAnimation(a1)
            anim_color_seq.addAnimation(a2)
            anim_color_seq.addAnimation(a3)
            
            self.notes_anim_group.addAnimation(anim_height)
            self.notes_anim_group.addAnimation(anim_color_seq)
            
            self.notes_anim_group.start()
            
        else:
            # === ЗАКРЫТИЕ (CLOSING) ===
            self.notes_anim_group = QParallelAnimationGroup()
            
            # Схлопывание высоты
            anim_height = QPropertyAnimation(self.notes_edit, b"maximumHeight")
            anim_height.setDuration(300)
            anim_height.setStartValue(self.notes_edit.height())
            anim_height.setEndValue(0)
            anim_height.setEasingCurve(QEasingCurve.InCubic)
            
            # Затухание свечения
            if self.notes_edit.graphicsEffect():
                anim_shadow = QPropertyAnimation(self.notes_edit.graphicsEffect(), b"color")
                anim_shadow.setDuration(200)
                anim_shadow.setEndValue(QColor(0, 0, 0, 0))
                self.notes_anim_group.addAnimation(anim_shadow)
            
            self.notes_anim_group.addAnimation(anim_height)
            
            self.notes_anim_group.finished.connect(lambda: self.notes_edit.setVisible(False))
            self.notes_anim_group.start()


    def filter_clients(self, text):
        search_text = text.lower().strip()
        
        # Получаем все элементы
        for i in range(self.cl_list.count()):
            item = self.cl_list.item(i)
            # Проверяем видимость
            if not search_text or search_text in item.text().lower():
                item.setHidden(False)
            else:
                item.setHidden(True)

    def save_notes(self):
        if self.current_client:
            self.current_client.notes = self.notes_edit.toPlainText()
            self.save_db()

    def save_db(self):
        if self.current_client:
            self.backend.update_client_full(self.current_client)
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
                    
                    copy_email_action = QAction("📧 Копировать Email", self)
                    copy_email_action.triggered.connect(lambda: self.copy_client_email(client))
                    menu.addAction(copy_email_action)
                    
                    export_zip_action = QAction("📦 Экспорт всех файлов (ZIP)", self)
                    export_zip_action.triggered.connect(lambda: self.export_client_files_by_obj(client))
                    menu.addAction(export_zip_action)
                    
                    menu.addSeparator()
                    
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

    def copy_client_email(self, client):
        if client.email:
            from PySide6.QtGui import QGuiApplication
            QGuiApplication.clipboard().setText(client.email)
        else:
            QMessageBox.information(self, "Инфо", "У клиента не указан Email")

    def export_client_files_by_obj(self, client):
        self.current_client = client
        self.render_client_profile()
        self.export_client_files()

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
            if self.backend.add_client(name.strip()):
                self.clients = self.backend.get_all_clients_from_backend()
                logger.info(f"Добавлен новый клиент: {name.strip()}")
                self.refresh_list()
                self.update_dash()
                
                for i in range(self.cl_list.count()):
                    item = self.cl_list.item(i)
                    if item.text().lower() == name.strip().lower():
                        client_id = item.data(Qt.ItemDataRole.UserRole)
                        self.current_client = self.backend.get_client_by_id(client_id)
                        self.cl_list.setCurrentItem(item)
                        self.select_client(item)
                        break
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось добавить клиента.")

    def handle_dropped_folder(self, folder_path):
        folder_name = os.path.basename(folder_path)
        
        # 1. Вопрос создания клиента
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Создание клиента")
        msg_box.setText(f"Создать клиента с именем этой папки?\n'{folder_name}'")
        
        btn_yes = msg_box.addButton("Да", QMessageBox.ButtonRole.YesRole)
        btn_other = msg_box.addButton("Другое имя", QMessageBox.ButtonRole.ActionRole)
        btn_no = msg_box.addButton("Нет", QMessageBox.ButtonRole.RejectRole)
        
        msg_box.exec()
        clicked = msg_box.clickedButton()
        
        if clicked == btn_no:
            return
            
        client_name = folder_name
        if clicked == btn_other:
            name, ok = QInputDialog.getText(self, "Имя клиента", "Введите имя клиента:", text=folder_name)
            if not ok or not name.strip():
                return
            client_name = name.strip()
        
        # Создаем или находим клиента
        client = next((c for c in self.clients if c.name.lower() == client_name.lower()), None)
        if client:
            reply = QMessageBox.question(
                self,
                "Клиент существует",
                f"Клиент '{client_name}' уже существует. Добавить заказы к нему?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
        else:
            new_client_id = self.backend.add_client_get_id(client_name)
            if new_client_id:
                client = self.backend.get_client_by_id(new_client_id)
                self.clients = self.backend.get_all_clients_from_backend()
                self.refresh_list()
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось создать клиента.")
                return
            
        self.current_client = client
        self.render_client_profile()
        for i in range(self.cl_list.count()):
            item = self.cl_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == client.id:
                self.cl_list.setCurrentItem(item)
                break

        # 2. Анализ вложенных папок
        subdirs = [d for d in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, d))]
        create_multiple = False
        
        if subdirs:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Создание заказов")
            msg_box.setText("Обнаружены вложенные папки.")
            msg_box.setInformativeText("Создать отдельные карточки заказов на каждую вложенную папку?")
            
            btn_split = msg_box.addButton("Да", QMessageBox.ButtonRole.YesRole)
            btn_single = msg_box.addButton("Нет, все в один заказ", QMessageBox.ButtonRole.NoRole)
            
            msg_box.exec()
            
            if msg_box.clickedButton() == btn_split:
                create_multiple = True
        else:
            reply = QMessageBox.question(
                self,
                "Создание заказа",
                "Создать карточку заказа с файлами из этой папки?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        # 3. Вопрос хранения файлов
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Хранение файлов")
        msg_box.setText("Как поступить с файлами?")
        msg_box.setInformativeText("Выберите способ хранения файлов для создаваемых заказов.")
        
        btn_keep = msg_box.addButton("Оставить исходные", QMessageBox.ButtonRole.ActionRole)
        btn_db = msg_box.addButton("В папке программы", QMessageBox.ButtonRole.ActionRole)
        btn_custom = msg_box.addButton("В другую папку...", QMessageBox.ButtonRole.ActionRole)
        btn_help = msg_box.addButton("❓", QMessageBox.ButtonRole.HelpRole)
        
        # Цикл для возможности возврата из справки
        while True:
            msg_box.exec()
            clicked_storage = msg_box.clickedButton()
            
            if clicked_storage == btn_help:
                QMessageBox.information(self, "Справка по хранению",
                    "<b>Оставить исходные:</b>\n"
                    "Программа создаст ссылки на файлы там, где они сейчас находятся.\n"
                    "Файлы не перемещаются и не копируются.\n\n"
                    "<b>В папке программы:</b>\n"
                    "Файлы будут скопированы в защищенную папку базы данных CRM.\n"
                    "Это гарантирует их доступность для программы.\n\n"
                    "<b>В другую папку:</b>\n"
                    "Вы выберете папку, куда будут скопированы файлы."
                )
                continue # Возвращаемся к выбору
            
            break # Выход из цикла, если выбрано действие

        target_base_folder = None
        should_copy = False
        
        if clicked_storage == btn_db:
            should_copy = True
            target_base_folder = self.app_settings.get('database_path', os.path.dirname(self.storage.path))
            target_base_folder = os.path.join(target_base_folder, "attached_files")
        elif clicked_storage == btn_custom:
            should_copy = True
            folder = QFileDialog.getExistingDirectory(self, "Выберите папку для сохранения файлов")
            if not folder:
                return
            target_base_folder = folder
        else:
            # Оставить исходные
            should_copy = False

        should_delete_source = False
        if should_copy:
            reply = QMessageBox.question(
                self,
                "Удаление исходников",
                "Удалить исходную папку после копирования?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            should_delete_source = (reply == QMessageBox.StandardButton.Yes)

        # 4. Процесс создания заказов
        try:
            orders_created = 0
            
            def create_order_from_path(path, order_name):
                # Собираем файлы
                files_to_add = []
                for root, dirs, files in os.walk(path):
                    for file in files:
                        files_to_add.append(os.path.join(root, file))
                
                if not files_to_add:
                    return False

                # Создаем заказ
                new_order = Order(
                    id=str(uuid.uuid4()),
                    service_type=order_name,
                    price=0.0,
                    advance=0.0,
                    created_at=datetime.now().strftime("%d.%m.%Y %H:%M"),
                    deadline=datetime.now().strftime("%d.%m.%Y"),
                    status="В работе",
                    files=[]
                )
                
                files_dest_folder = None
                if should_copy and target_base_folder:
                    # Создаем папку для заказа внутри целевой папки
                    # Используем имя клиента и тип услуги для читаемости структуры, если это кастомная папка
                    # Или ID, если база.
                    # Для унификации используем ID заказа как уникальную папку
                    files_dest_folder = os.path.join(target_base_folder, new_order.id)
                    os.makedirs(files_dest_folder, exist_ok=True)
                
                for file_path in files_to_add:
                    if should_copy and files_dest_folder:
                        base_name = os.path.basename(file_path)
                        new_path = os.path.join(files_dest_folder, base_name)
                        
                        counter = 1
                        name, ext = os.path.splitext(base_name)
                        while os.path.exists(new_path):
                            new_path = os.path.join(files_dest_folder, f"{name}_{counter}{ext}")
                            counter += 1
                            
                        shutil.copy2(file_path, new_path)
                        final_path = new_path
                    else:
                        final_path = file_path

                    new_order.files.append(ProjectFile(
                        path=final_path,
                        name=os.path.basename(final_path),
                        is_finished=False,
                        is_folder=False
                    ))
                
                client.orders.append(new_order)
                return True

            if create_multiple:
                for subdir in subdirs:
                    full_path = os.path.join(folder_path, subdir)
                    if create_order_from_path(full_path, subdir):
                        orders_created += 1
            else:
                if create_order_from_path(folder_path, folder_name):
                    orders_created += 1

            self.backend.save_client_data(client)
            self.render_client_profile()
            self.update_dash()
            
            if should_delete_source:
                try:
                    shutil.rmtree(folder_path)
                    QMessageBox.information(self, "Успех", f"Создано заказов: {orders_created}.\nИсходная папка удалена.")
                except Exception as e:
                    QMessageBox.warning(self, "Предупреждение", f"Заказы созданы, но не удалось удалить папку: {e}")
            else:
                QMessageBox.information(self, "Успех", f"Создано заказов: {orders_created}.")
                
        except Exception as e:
            logger.error(f"Ошибка при обработке папки: {e}", exc_info=True)
            QMessageBox.critical(self, "Ошибка", f"Произошла ошибка при импорте папки: {e}")

    def add_order(self):
        if not self.current_client:
            QMessageBox.warning(self, "Внимание", "Сначала выберите клиента.")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Новый заказ")
        # Removed fixed size to allow shrink-wrap
        # dialog.setFixedWidth(360)
        
        # Stylesheet for high density / professional accounting look
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
            }
            QLabel {
                color: #CCCCCC;
                font-size: 12px;
            }
            QComboBox, QLineEdit {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
                min-height: 22px;
            }
            QComboBox::drop-down {
                border-left: 1px solid #3D3D3D;
                background: #2D2D2D;
                width: 20px;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #00D1FF;
            }
            QComboBox QAbstractItemView {
                background-color: #2D2D2D;
                color: #FFFFFF;
                selection-background-color: #0078D7;
                border: 1px solid #3D3D3D;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #0078D7;
            }
            QCalendarWidget QWidget {
                background-color: #252525;
                color: white;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        # Minimize margins to remove empty space
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize) # Auto-resize to content
        
        # --- Animation Helper ---
        def add_click_animation(button):
            # Store original press event
            original_press = button.mousePressEvent
            original_release = button.mouseReleaseEvent
            
            def animate_press(event):
                anim = QPropertyAnimation(button, b"geometry")
                anim.setDuration(100)
                anim.setStartValue(button.geometry())
                # Shrink slightly towards center
                rect = button.geometry()
                center = rect.center()
                shrink_factor = 0.95
                new_width = int(rect.width() * shrink_factor)
                new_height = int(rect.height() * shrink_factor)
                new_rect = rect
                new_rect.setWidth(new_width)
                new_rect.setHeight(new_height)
                new_rect.moveCenter(center)
                
                anim.setEndValue(new_rect)
                anim.setEasingCurve(QEasingCurve.OutQuad)
                anim.start()
                
                # Keep reference to avoid garbage collection
                button._press_anim = anim
                if original_press:
                    original_press(event)

            def animate_release(event):
                # Restore size
                anim = QPropertyAnimation(button, b"geometry")
                anim.setDuration(100)
                # We can't easily guess the "original" geometry if layout changed,
                # but for a quick effect we just assume it snaps back.
                # Actually, standard widgets might glitch with geometry animation if layout is active.
                # Better approach for buttons in layout: animate scale or transform if possible,
                # but standard widgets don't support transform easily without graphics view.
                # fallback: no-op geometry restore handled by layout on update,
                # OR we just rely on visual stylesheet states.
                
                # Let's try a simpler approach: Stylesheet animation is not supported.
                # Let's just use the standard button behavior but add a custom "glint" or visual feedback?
                # The user asked for "reveal menu animation" (раскрытие меню) OR "click animation"?
                # Text: "добавь анимацию раскрытия меню при нажатии на все кнопки..."
                # Wait, "анимацию раскрытия меню" usually means for dropdowns.
                # But "при нажатии на все кнопки" implies click feedback.
                # Let's assume click feedback (scale effect) for buttons.
                
                # Since modifying geometry in a layout is risky, we will just call the original.
                if original_release:
                    original_release(event)
            
            # actually, for "анимацию раскрытия меню" (menu reveal animation)
            # upon clicking buttons, it might mean the ComboBox popup animation?
            # Or just a general "click effect".
            # Given "все кнопки" (all buttons), I will implement a scale-down effect on press.
            # To do this safely in layout: we can't easily.
            # Let's try to animate a property that doesn't break layout, or skip geometry.
            pass

        # Since geometry animation fights with Layouts, we will implement a visual "flash"
        # or rely on the fact that we can't easily do complex geometry animations on standard widgets in layouts without glitches.
        # HOWEVER, the user asked for "анимацию раскрытия меню" (animation of menu opening).
        # This might refer to the Combo Boxes? Or is it a mistranslation/misunderstanding?
        # "при нажатии на все кнопки" -> when clicking all buttons.
        # Let's stick to a safe visual feedback:
        # We will subclass the buttons or wrap the connect to add a small delay/effect?
        # Let's try a property animation on a custom property 'scale' if we were in QML, but we are in Widgets.
        
        # Alternative: We can animate the window opacity or size? No.
        
        # Let's implement a custom `Button` wrapper that handles a "click" animation
        # by overriding mousePressEvent to slightly offset content or change style.
        # But for "Menu Reveal" on buttons?
        # User phrase: "анимацию раскрытия меню при нажатии на все кнопки"
        # Literally: "animation of menu opening when clicking on all buttons"
        # This likely means a "ripple" or "scale" effect that looks like an interaction.
        # I will implement a visual scale effect by subclassing or event filter.
        # Actually, for standard widgets, simply styling `pressed` state is best.
        # But if they want "Animation", I will try to animate the "Calendar" popup opacity.
        
        # Let's focus on "All columns same width".
        
        # --- Helper for Date Input with Calendar ---
        def create_date_input(initial_text):
            container = QWidget()
            l = QHBoxLayout(container)
            l.setContentsMargins(0, 0, 0, 0)
            l.setSpacing(2)
            
            edit = QLineEdit(initial_text)
            
            btn = QToolButton()
            btn.setText("🗓️")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedSize(26, 26)
            btn.setStyleSheet("""
                QToolButton {
                    border: none;
                    background-color: transparent;
                    font-size: 14px;
                    color: #BBBBBB;
                }
                QToolButton:hover {
                    color: #FFFFFF;
                    background-color: #333333;
                    border-radius: 3px;
                }
                QToolButton:pressed {
                    background-color: #444444;
                    padding-top: 2px;
                    padding-left: 2px;
                }
            """)
            
            def show_calendar():
                cal_dialog = QDialog(dialog)
                cal_dialog.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
                cal_layout = QVBoxLayout(cal_dialog)
                cal_layout.setContentsMargins(0, 0, 0, 0)
                
                cal = QCalendarWidget()
                cal.setGridVisible(True)
                cal.setStyleSheet("""
                    QCalendarWidget QWidget { background-color: #252525; color: white; border: 1px solid #444444; }
                    QCalendarWidget QToolButton { color: white; background-color: #333333; }
                    QCalendarWidget QMenu { background-color: #333333; color: white; }
                    QCalendarWidget QSpinBox { color: white; background-color: #333333; selection-background-color: #0078D7; }
                    QCalendarWidget QAbstractItemView:enabled {
                        background-color: #252525;
                        color: white;
                        selection-background-color: #0078D7;
                        selection-color: white;
                    }
                """)
                
                def select_date():
                    date = cal.selectedDate()
                    edit.setText(date.toString("dd.MM.yyyy"))
                    cal_dialog.accept()

                cal.activated.connect(select_date)
                cal.clicked.connect(select_date)
                
                cal_layout.addWidget(cal)
                
                pos = edit.mapToGlobal(edit.rect().bottomLeft())
                cal_dialog.move(pos)
                
                # Animation for popup
                cal_dialog.setWindowOpacity(0.0)
                anim = QPropertyAnimation(cal_dialog, b"windowOpacity")
                anim.setDuration(200)
                anim.setStartValue(0.0)
                anim.setEndValue(1.0)
                anim.setEasingCurve(QEasingCurve.OutQuad)
                anim.start()
                
                # Keep reference
                cal_dialog._anim = anim
                cal_dialog.exec()
            
            btn.clicked.connect(show_calendar)
            
            l.addWidget(edit)
            l.addWidget(btn)
            return container, edit

        # --- Main Grid ---
        grid = QGridLayout()
        grid.setVerticalSpacing(8)
        grid.setHorizontalSpacing(10)
        # Equal column widths: set stretch factor equal for both columns
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        
        # Row 0: Service Type
        lbl_service = QLabel("Тип услуги:")
        lbl_service.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        service_combo = QComboBox()
        service_combo.setEditable(True)
        
        # Load services from settings or use defaults
        default_services = ["Монтаж звука", "Монтаж аудио", "Оркестровка", "Нотный набор", "Сведение", "Аранжировка", "Мастеринг", "Консультация"]
        saved_services = self.app_settings.get("service_types", default_services)
        
        service_combo.addItems(saved_services)
        service_combo.addItem("➕ Добавить новую...")
        
        def check_service_input(index):
            if service_combo.itemText(index) == "➕ Добавить новую...":
                service_combo.setCurrentText("")
                service_combo.setFocus()
                
        service_combo.currentIndexChanged.connect(check_service_input)
        
        grid.addWidget(lbl_service, 0, 0)
        grid.addWidget(service_combo, 0, 1)
        
        # Row 1: Price + Currency
        lbl_price = QLabel("Стоимость:")
        lbl_price.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        price_container = QWidget()
        price_layout = QHBoxLayout(price_container)
        price_layout.setContentsMargins(0, 0, 0, 0)
        price_layout.setSpacing(5)
        
        price_edit = QLineEdit("0")
        price_edit.setPlaceholderText("0")
        
        currency_combo = QComboBox()
        currencies = self.app_settings.get("currencies", ["RUB", "USD", "EUR", "UAH"])
        currency_combo.addItems(currencies)
        currency_combo.addItem("Другая...")
        currency_combo.addItem("Нет")
        currency_combo.setEditable(True)
        currency_combo.setFixedWidth(85)
        
        price_layout.addWidget(price_edit)
        price_layout.addWidget(currency_combo)
        
        grid.addWidget(lbl_price, 1, 0)
        grid.addWidget(price_container, 1, 1)

        # Row 2: Order Date (New)
        lbl_date_created = QLabel("Дата заказа:")
        lbl_date_created.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        date_created_container, date_created_edit = create_date_input(datetime.now().strftime("%d.%m.%Y"))
        
        grid.addWidget(lbl_date_created, 2, 0)
        grid.addWidget(date_created_container, 2, 1)
        
        # Row 3: Deadline
        lbl_deadline = QLabel("Срок выполнения:")
        lbl_deadline.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        deadline_container, deadline_edit = create_date_input(datetime.now().strftime("%d.%m.%Y"))
        
        grid.addWidget(lbl_deadline, 3, 0)
        grid.addWidget(deadline_container, 3, 1)
        
        # Row 4: Advance (Integrated directly)
        lbl_advance = QLabel("Аванс:")
        lbl_advance.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        advance_edit = QLineEdit("0")
        advance_edit.setPlaceholderText("0")
        
        grid.addWidget(lbl_advance, 4, 0)
        grid.addWidget(advance_edit, 4, 1)
        
        layout.addLayout(grid)
        
        # Removed stretch to eliminate bottom empty space
        # layout.addStretch()
        
        # --- Buttons ---
        # Align buttons under the right column (Input column)
        # We can add them to the grid or use a horizontal layout aligned right.
        # User asked: "move right under the common menu" (inputs).
        # Since grid has 2 columns, we can put buttons in a layout spanning column 1, or just right aligned.
        
        button_container = QWidget()
        buttons_layout = QHBoxLayout(button_container)
        buttons_layout.setContentsMargins(0, 10, 0, 0)
        buttons_layout.setSpacing(10)
        buttons_layout.setAlignment(Qt.AlignmentFlag.AlignLeft) # Left of the container (which will be in right col)
        
        create_btn = QPushButton("Создать заказ")
        create_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # Increased padding slightly to ensure text is visible
        create_btn.setStyleSheet("""
            QPushButton {
                background-color: #28A745;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:pressed {
                background-color: #1E7E34;
                padding-top: 7px;
                padding-left: 13px;
            }
        """)
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #AAAAAA;
                padding: 6px 12px;
                border: 1px solid #444444;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3D3D3D;
                color: #FFFFFF;
                border-color: #666666;
            }
            QPushButton:pressed {
                background-color: #2D2D2D;
                padding-top: 7px;
                padding-left: 13px;
            }
        """)
        
        buttons_layout.addWidget(create_btn)
        buttons_layout.addWidget(cancel_btn)
        
        # Add to grid at row 5, column 1 (Right column)
        grid.addWidget(button_container, 5, 1)
        
        # --- Logic ---
        def create_order():
            # Button animation simulation
            anim = QPropertyAnimation(create_btn, b"geometry") # Dummy to keep consistent feel
            try:
                # Parse Price
                price_text = price_edit.text().replace(',', '.').replace(' ', '')
                price = float(price_text or 0)
                if price < 0:
                    QMessageBox.warning(dialog, "Ошибка", "Стоимость не может быть отрицательной.")
                    return
                
                # Parse Advance
                advance_text = advance_edit.text().replace(',', '.').replace(' ', '')
                advance = float(advance_text or 0)
                if advance < 0:
                    QMessageBox.warning(dialog, "Ошибка", "Аванс не может быть отрицательным.")
                    return
                if advance > price:
                    QMessageBox.warning(dialog, "Ошибка", "Аванс не может превышать стоимость.")
                    return
                
                # Combine date from input with current time for created_at
                order_date_str = date_created_edit.text()
                current_time = datetime.now().strftime("%H:%M")
                created_at_full = f"{order_date_str} {current_time}"
                
                service_type_val = service_combo.currentText().strip()
                if not service_type_val or service_type_val == "➕ Добавить новую...":
                    QMessageBox.warning(dialog, "Ошибка", "Введите тип услуги.")
                    return

                # Save new service type if custom
                if service_type_val not in saved_services:
                    saved_services.append(service_type_val)
                    self.app_settings['service_types'] = saved_services
                    self.save_settings()

                new_order = Order(
                    id=str(uuid.uuid4()),
                    service_type=service_type_val,
                    price=price,
                    currency=currency_combo.currentText() if currency_combo.currentText() != "Нет" else "",
                    advance=advance,
                    created_at=created_at_full,
                    deadline=deadline_edit.text(),
                    status="В работе",
                    payments=[]
                )
                
                if advance > 0:
                    new_order.add_payment(advance, "аванс", "Первоначальный аванс")
                
                if self.backend.add_order(
                    self.current_client.id,
                    service_type_val,
                    price,
                    currency_combo.currentText() if currency_combo.currentText() != "Нет" else "",
                    advance,
                    deadline_edit.text()
                ):
                    self.clients = self.backend.get_all_clients_from_backend()
                    self.render_client_profile()
                    self.update_dash()
                    dialog.accept()
                else:
                    QMessageBox.critical(dialog, "Ошибка", "Не удалось создать заказ.")
                
            except ValueError as e:
                QMessageBox.warning(dialog, "Ошибка", f"Ошибка ввода данных: {e}")
            except Exception as e:
                logger.error(f"Ошибка при создании заказа: {e}", exc_info=True)
                QMessageBox.critical(dialog, "Ошибка", f"Произошла непредвиденная ошибка: {e}")
        
        create_btn.clicked.connect(create_order)
        cancel_btn.clicked.connect(dialog.reject)
        
        service_combo.setFocus()
        animate_dialog_open(dialog)
        dialog.exec()

    def open_global_file_manager(self):
        from .dialogs import GlobalFileManagerDialog
        dialog = GlobalFileManagerDialog(self)
        dialog.exec()

    def open_settings(self):
        SettingsDialog(self).exec()

    def show_app_help(self):
        """Показывает общую справку по приложению"""
        from .dialogs import HelpDialog
        dialog = HelpDialog(self)
        dialog.exec()

    def open_client_settings(self):
        if not self.current_client:
            return
        
        dialog = ClientSettingsDialog(self.current_client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Обновляем данные клиента
            self.current_client.name = dialog.name_edit.text()
            self.current_client.email = dialog.email_edit.text()
            self.current_client.telegram = dialog.telegram_edit.text()
            self.current_client.vk = dialog.vk_edit.text()
            self.current_client.facebook = dialog.facebook_edit.text()
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
            # Removed redundant 'try' block, as backend.import_json already handles exceptions
            # and returns False on failure.
            if self.backend.import_json(path):
                # Backend уже обработал подтверждение и бэкап, только обновляем UI
                self.clients = self.backend.get_all_clients_from_backend()
                self.current_client = None
                self.refresh_list()
                self.clear_profile_layout()
                self.update_dash()
                QMessageBox.information(
                    self,
                    "Успех",
                    f"База данных успешно импортирована.\n\nИмпортировано клиентов: {len(self.clients)}\n"
                )
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось импортировать базу данных.")

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
            result_msg = self.backend.export_full_backup(path)
            if "Ошибка" in result_msg:
                QMessageBox.critical(self, "Ошибка", result_msg)
            else:
                QMessageBox.information(self, "Резервная копия создана", result_msg)
        except Exception as e:
            logger.error(f"Ошибка при создании полного бэкапа: {e}", exc_info=True)
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать резервную копию:\n{e}")

    def get_database_size(self):
        return self.backend.get_database_size()

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
        btn_disk_also = msg_box.addButton("Удалить с компьютера", QMessageBox.ButtonRole.DestructiveRole)
        btn_cancel = msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        
        msg_box.exec()
        
        clicked = msg_box.clickedButton()
        
        if clicked == btn_cancel:
            return
            
        delete_from_disk = (clicked == btn_disk_also)
        
        if self.backend.delete_all_files(delete_from_disk):
            self.clients = self.backend.get_all_clients_from_backend()
            self.render_client_profile()
            self.update_dash()
            info_text = f"Удалено ссылок на файлы: {self.backend.last_deleted_file_count}"
            if delete_from_disk:
                info_text += "\nФайлы также удалены с диска (из папки базы данных)."
            else:
                info_text += "\nФайлы на диске не были затронуты."
                
            QMessageBox.information(self, "Успех", info_text)
        else:
            QMessageBox.critical(self, "Ошибка", "Не удалось удалить все файлы.")

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
        
        msg_box.exec()
        
        clicked = msg_box.clickedButton()
        if clicked == btn_cancel:
            return
            
        delete_files_disk = (clicked == btn_disk_also)
        
        if self.backend.delete_full_database(delete_files_disk):
            self.clients = self.backend.get_all_clients_from_backend()
            self.current_client = None
            self.refresh_list()
            self.clear_profile_layout()
            self.update_dash()
            
            msg = "База данных полностью очищена."
            if delete_files_disk:
                msg += "\nФайлы также были удалены с диска."
            else:
                msg += "\nФайлы на диске остались нетронутыми."
                
            QMessageBox.information(self, "Успех", msg)
        else:
            QMessageBox.critical(self, "Ошибка", "Не удалось полностью удалить базу данных.")

    def open_client_by_id(self, client_id):
        """Находит клиента по ID и открывает его профиль."""
        client = next((c for c in self.clients if c.id == client_id), None)
        if client:
            # Визуально выделяем клиента в списке
            for i in range(self.cl_list.count()):
                item = self.cl_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == client.id:
                    self.cl_list.setCurrentItem(item)
                    self.select_client(item)
                    break

    def open_social_link(self, attr: str, prefix: str):
        """Открывает ссылку на соцсеть или предлагает ее ввести."""
        if not self.current_client:
            return

        link = getattr(self.current_client, attr, "").strip()

        if not link:
            text, ok = QInputDialog.getText(self, f"Добавить {attr.capitalize()}", f"Введите ссылку или юзернейм для {attr.capitalize()}:")
            if ok and text.strip():
                setattr(self.current_client, attr, text.strip())
                self.save_db()
                self.render_client_profile() # Перерисовать, чтобы кнопка стала активной
                link = text.strip() # Используем только что введенную ссылку
            else:
                return # Пользователь отменил ввод

        if not link: # Если ссылка все еще пуста
            return

        # Формируем полный URL
        if prefix == 'mailto:':
            url = f"{prefix}{link}"
        elif '://' not in link:
            url = f"{prefix}{link.lstrip('@')}" # Удаляем @ если есть
        else:
            url = link

        QDesktopServices.openUrl(QUrl(url))

    def show_sum_details(self):
        if not self.current_client: return
        title = f"Детализация суммы заказов: {self.current_client.name}"
        headers = ["Заказ", "Сумма", "Статус", "Дата создания"]
        data = []
        for order in self.current_client.orders:
            data.append([order.service_type, f"{order.price:,.0f} ₽", order.status, order.created_at])
        
        dialog = StatsDetailDialog(title, headers, data, self)
        dialog.exec()

    def show_paid_details(self):
        if not self.current_client: return
        title = f"Детализация оплат: {self.current_client.name}"
        headers = ["Дата", "Сумма", "Тип", "Заказ", "Комментарий"]
        data = []
        for order in self.current_client.orders:
            for payment in order.payments:
                if payment.amount > 0: # Показываем только поступления
                    data.append([payment.date, f"{payment.amount:,.0f} ₽", payment.type, order.service_type, payment.note])
        
        dialog = StatsDetailDialog(title, headers, data, self)
        dialog.exec()

    def show_adv_details(self):
        if not self.current_client: return
        title = f"Детализация авансов: {self.current_client.name}"
        headers = ["Дата", "Сумма", "Заказ", "Комментарий"]
        data = []
        for order in self.current_client.orders:
            for payment in order.payments:
                if payment.type == 'аванс' and payment.amount > 0:
                    data.append([payment.date, f"{payment.amount:,.0f} ₽", order.service_type, payment.note])
        
        dialog = StatsDetailDialog(title, headers, data, self)
        dialog.exec()

    def show_debt_details(self):
        if not self.current_client: return
        title = f"Незакрытые долги: {self.current_client.name}"
        headers = ["Заказ", "Сумма долга", "Срок выполнения"]
        data = []
        for order in self.current_client.orders:
            if order.debt > 0:
                data.append([order.service_type, f"{order.debt:,.0f} ₽", order.deadline])
        
        dialog = StatsDetailDialog(title, headers, data, self)
        dialog.exec()
