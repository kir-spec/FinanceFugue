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
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QMessageBox, QWidget,
    QLineEdit, QFileDialog, QCheckBox, QGroupBox, QRadioButton,
    QFormLayout, QTextEdit, QDialogButtonBox, QInputDialog, QDateEdit, QComboBox,
    QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView, QTreeWidget, QTreeWidgetItem,
    QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QSequentialAnimationGroup, QPoint, Signal
from PySide6.QtGui import QColor, QAction, QIcon
from .widgets import ToggleSwitch, ClickableCardWidget # Импортируем новые виджеты

def animate_dialog_open(dialog):
    # Центрирование относительно родителя или экрана
    parent = dialog.parent()
    target_rect = None
    
    if dialog.layout() and dialog.layout().sizeConstraint() == QVBoxLayout.SizeConstraint.SetFixedSize:
        dialog.adjustSize()

    if parent and parent.isVisible():
        target_rect = parent.geometry()
    else:
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen:
            target_rect = screen.availableGeometry()
    
    if target_rect:
        center_x = target_rect.x() + (target_rect.width() - dialog.width()) // 2
        center_y = target_rect.y() + (target_rect.height() - dialog.height()) // 2
        dialog.move(center_x, center_y)
    
    # Установка начальной прозрачности
    dialog.setWindowOpacity(0.0)
    
    # Группа параллельных анимаций
    anim_group = QParallelAnimationGroup(dialog)
    
    # 1. Анимация прозрачности (Fade In)
    anim_opacity = QPropertyAnimation(dialog, b"windowOpacity")
    anim_opacity.setDuration(300)
    anim_opacity.setStartValue(0.0)
    anim_opacity.setEndValue(1.0)
    anim_opacity.setEasingCurve(QEasingCurve.OutQuad)
    anim_group.addAnimation(anim_opacity)
    
    # 2. Анимация "Прыжка" (Bounce) - имитация через геометрию
    # Слегка смещаем окно снизу вверх относительно вычисленного центра
    final_geo = dialog.geometry()
    start_geo = final_geo.translated(0, 20)
    
    # Важно: сначала ставим в стартовую позицию
    dialog.setGeometry(start_geo)
    
    anim_pos = QPropertyAnimation(dialog, b"geometry")
    anim_pos.setDuration(400)
    anim_pos.setStartValue(start_geo)
    anim_pos.setEndValue(final_geo)
    anim_pos.setEasingCurve(QEasingCurve.OutBack)
    anim_group.addAnimation(anim_pos)
    
    # 3. Эффект "Вспышки" (Ignition) через тень
    # Создаем эффект тени для диалога
    shadow = QGraphicsDropShadowEffect(dialog)
    shadow.setBlurRadius(0)
    shadow.setOffset(0, 0)
    shadow.setColor(QColor(0, 0, 0, 0))
    # Важно: для QDialog тень может обрезаться границами окна ОС, если нет FramelessWindowHint.
    # Но мы попробуем применить эффект к центральному виджету или layout'у, если возможно,
    # или просто применим к самому диалогу (может работать на Custom UI).
    # Для стандартных диалогов лучше просто мигнуть фоном, но это сложно без стиля.
    # Оставим тень, она сработает на кастомных диалогах.
    dialog.setGraphicsEffect(shadow)
    
    # Последовательность цветов тени: Оранжевый -> Золотой -> Прозрачный (или цвет темы)
    anim_shadow_seq = QSequentialAnimationGroup(dialog)
    
    # Вспышка (Оранжевый)
    s1 = QPropertyAnimation(shadow, b"color")
    s1.setDuration(150)
    s1.setStartValue(QColor(0, 0, 0, 0))
    s1.setEndValue(QColor(255, 69, 0, 180)) # Orange-Red
    
    b1 = QPropertyAnimation(shadow, b"blurRadius")
    b1.setDuration(150)
    b1.setStartValue(0)
    b1.setEndValue(30)
    
    step1 = QParallelAnimationGroup()
    step1.addAnimation(s1)
    step1.addAnimation(b1)
    
    # Горение (Золотой)
    s2 = QPropertyAnimation(shadow, b"color")
    s2.setDuration(300)
    s2.setStartValue(QColor(255, 69, 0, 180))
    s2.setEndValue(QColor(255, 215, 0, 150)) # Gold
    
    # Затухание
    s3 = QPropertyAnimation(shadow, b"color")
    s3.setDuration(500)
    s3.setStartValue(QColor(255, 215, 0, 150))
    s3.setEndValue(QColor(0, 0, 0, 0)) # Fade out
    
    anim_shadow_seq.addAnimation(step1)
    anim_shadow_seq.addAnimation(s2)
    anim_shadow_seq.addAnimation(s3)
    
    anim_group.addAnimation(anim_shadow_seq)
    
    # Сохраняем ссылку на анимацию, чтобы сборщик мусора не удалил её
    dialog._open_anim = anim_group
    anim_group.start()

from .models import Order, ProjectFile, Client

# --- ДИАЛОГ ДЕТАЛИЗАЦИИ СТАТИСТИКИ ---
class StatsDetailDialog(QDialog):
    def __init__(self, title, headers, data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(600, 400)

        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; }
            QTableWidget {
                background-color: #252525;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                gridline-color: #333333;
                font-size: 13px;
            }
            QHeaderView::section {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                padding: 6px;
                font-weight: bold;
            }
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #3D3D3D; }
        """)

        layout = QVBoxLayout(self)
        
        table = QTableWidget(len(data), len(headers))
        table.setHorizontalHeaderLabels(headers)
        
        for row, row_data in enumerate(data):
            for col, cell_data in enumerate(row_data):
                item = QTableWidgetItem(str(cell_data))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(row, col, item)
                
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table)
        
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        animate_dialog_open(self)


# --- ДИАЛОГ ВЫБОРА КЛИЕНТА ---
class ClientSelectionDialog(QDialog):
    def __init__(self, parent_app, parent=None):
        super().__init__(parent)
        self.parent_app = parent_app
        self.selected_client = None
        self.setWindowTitle("Выбор клиента")
        self.resize(400, 500)
        
        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; }
            QLabel { color: #FFFFFF; font-size: 12px; }
            QListWidget {
                background-color: #252525;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                font-size: 13px;
            }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #333333; }
            QListWidget::item:selected { background-color: #0078D7; color: white; }
            QListWidget::item:hover { background-color: #333333; }
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #3D3D3D; }
        """)
        
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Выберите клиента для привязки файлов:"))
        
        self.client_list = QListWidget()
        self.populate_list()
        self.client_list.itemDoubleClicked.connect(self.accept_selection)
        layout.addWidget(self.client_list)
        
        btn_new = QPushButton("➕ Создать нового клиента")
        btn_new.setStyleSheet("""
            QPushButton {
                background-color: #28A745;
                color: white;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover { background-color: #218838; }
        """)
        btn_new.clicked.connect(self.create_new_client)
        layout.addWidget(btn_new)
        
        # Buttons OK/Cancel
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self.accept_selection)
        btn_box.rejected.connect(self.reject)
        
        # Стилизация кнопок QDialogButtonBox через stylesheet выше работает, но можно уточнить
        layout.addWidget(btn_box)
        
        animate_dialog_open(self)

    def populate_list(self):
        self.client_list.clear()
        # Сортируем по имени
        sorted_clients = sorted(self.parent_app.clients, key=lambda x: x.name.lower())
        for client in sorted_clients:
            item = QListWidgetItem(client.name)
            item.setData(Qt.ItemDataRole.UserRole, client)
            self.client_list.addItem(item)
            
    def create_new_client(self):
        name, ok = QInputDialog.getText(self, "Новый клиент", "Введите имя клиента:")
        if ok and name.strip():
            # Проверка на дубликаты
            if any(c.name.lower() == name.strip().lower() for c in self.parent_app.clients):
                QMessageBox.warning(self, "Ошибка", "Клиент с таким именем уже существует")
                return
            
            new_client = Client(id=str(uuid.uuid4()), name=name.strip())
            self.parent_app.clients.append(new_client)
            self.parent_app.save_db()
            self.parent_app.refresh_list() # Обновляем главное окно
            
            self.populate_list()
            
            # Выделяем нового
            for i in range(self.client_list.count()):
                item = self.client_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == new_client:
                    self.client_list.setCurrentItem(item)
                    break
                    
    def accept_selection(self):
        if not self.client_list.currentItem():
            QMessageBox.warning(self, "Внимание", "Выберите клиента из списка")
            return
        self.selected_client = self.client_list.currentItem().data(Qt.ItemDataRole.UserRole)
        self.accept()

# --- ДИАЛОГ ВЫБОРА ЗАКАЗА ---
class OrderSelectionDialog(QDialog):
    def __init__(self, client, parent=None):
        super().__init__(parent)
        self.client = client
        self.selected_order = None
        self.setWindowTitle("Выбор заказа")
        self.resize(400, 400)
        
        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; }
            QLabel { color: #FFFFFF; font-size: 12px; }
            QListWidget {
                background-color: #252525;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                font-size: 13px;
            }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #333333; }
            QListWidget::item:selected { background-color: #0078D7; color: white; }
            QListWidget::item:hover { background-color: #333333; }
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #3D3D3D; }
        """)
        
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel(f"Клиент: {client.name}"))
        layout.addWidget(QLabel("Выберите заказ или создайте новый:"))
        
        self.order_list = QListWidget()
        self.populate_list()
        self.order_list.itemDoubleClicked.connect(self.accept_selection)
        layout.addWidget(self.order_list)
        
        btn_new = QPushButton("➕ Создать новый заказ")
        btn_new.setStyleSheet("""
            QPushButton {
                background-color: #28A745;
                color: white;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover { background-color: #218838; }
        """)
        btn_new.clicked.connect(self.create_new_order)
        layout.addWidget(btn_new)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self.accept_selection)
        btn_box.rejected.connect(self.reject)
        
        # Кнопка справки в углу
        h_layout = QHBoxLayout()
        help_btn = QPushButton("❓ Справка")
        help_btn.setFixedWidth(100)
        help_btn.clicked.connect(self.show_help)
        h_layout.addWidget(help_btn)
        h_layout.addWidget(btn_box)
        
        layout.addLayout(h_layout)
        
        animate_dialog_open(self)

    def show_help(self):
        help_dialog = HelpDialog(self)
        help_dialog.select_section("Управление заказами")
        help_dialog.exec()
        
    def populate_list(self):
        self.order_list.clear()
        # Сортируем заказы по дате (свежие сверху)
        # Предполагаем формат даты dd.MM.yyyy или dd.MM.yyyy HH:mm
        def parse_date(d_str):
            try:
                if " " in d_str:
                    return datetime.strptime(d_str, "%d.%m.%Y %H:%M")
                return datetime.strptime(d_str, "%d.%m.%Y")
            except:
                return datetime.min

        sorted_orders = sorted(self.client.orders, key=lambda x: parse_date(x.created_at), reverse=True)
        
        for order in sorted_orders:
            text = f"{order.service_type} (от {order.created_at})"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, order)
            self.order_list.addItem(item)
            
    def create_new_order(self):
        order_name, ok = QInputDialog.getText(self, "Новый заказ", "Название услуги/заказа:")
        if ok and order_name.strip():
            new_order = Order(
                id=str(uuid.uuid4()),
                service_type=order_name.strip(),
                price=0.0,
                advance=0.0,
                created_at=datetime.now().strftime("%d.%m.%Y %H:%M"),
                deadline=datetime.now().strftime("%d.%m.%Y"),
                status="В работе",
                files=[]
            )
            self.client.orders.append(new_order)
            
            # Нужно сохранить базу, так как мы изменили клиента
            # Но у нас нет доступа к app.save_db() напрямую, но Client передается по ссылке
            # Мы можем сохранить базу в accept_selection, если есть доступ к parent_app,
            # или просто обновить список, а сохранение произойдет позже в GlobalFileManager
            
            self.populate_list()
            
            # Выделяем новый
            for i in range(self.order_list.count()):
                item = self.order_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == new_order:
                    self.order_list.setCurrentItem(item)
                    break
                    
    def accept_selection(self):
        if not self.order_list.currentItem():
            QMessageBox.warning(self, "Внимание", "Выберите заказ из списка")
            return
        self.selected_order = self.order_list.currentItem().data(Qt.ItemDataRole.UserRole)
        self.accept()

# --- GLOBAL FILE MANAGER ---
class GlobalFileManagerDialog(QDialog):
    def __init__(self, parent_app):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.setWindowTitle("Менеджер файлов")
        self.resize(900, 600)
        self.setAcceptDrops(True)
        
        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; }
            QLabel { color: #FFFFFF; font-size: 14px; }
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #3D3D3D; }
            QTreeWidget {
                background-color: #252525;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                font-size: 14px;
            }
            QHeaderView::section {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                padding: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QTreeWidget::item {
                padding: 5px;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # Дерево файлов
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Клиент / Заказ / Файл", "Статус", "Путь", "Тип"])
        self.tree.setColumnWidth(0, 350)
        self.tree.setColumnWidth(1, 120)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        
        layout.addWidget(self.tree)
        
        # Кнопки
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.load_data)
        
        del_btn = QPushButton("🗑 Удалить")
        del_btn.setStyleSheet("""
            QPushButton {
                background-color: #A12A2A; /* Менее яркий красный */
                color: white;
                border: 1px solid #B83A3A;
            }
            QPushButton:hover { background-color: #C23E3E; }
            QPushButton:pressed { background-color: #912424; }
        """)
        del_btn.clicked.connect(self.delete_selected)
        
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        
        help_btn = QPushButton("❓ Справка")
        help_btn.clicked.connect(self.show_help)

        btn_layout.addWidget(refresh_btn)
        btn_layout.addWidget(del_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(help_btn)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
        self.load_data()
        
        animate_dialog_open(self)

    def show_help(self):
        help_dialog = QDialog(self)
        help_dialog.setWindowTitle("Справка по Менеджеру Файлов")
        help_dialog.setFixedWidth(500)
        help_dialog.setStyleSheet("""
            QDialog { background-color: #252525; border: 1px solid #3D3D3D; border-radius: 8px; }
            QLabel { color: #DDDDDD; font-size: 13px; }
            QPushButton {
                background-color: #0078D7; color: white; font-weight: bold;
                padding: 8px 16px; border-radius: 4px; border: none;
            }
            QPushButton:hover { background-color: #005FA3; }
        """)
        
        layout = QVBoxLayout(help_dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("📁 Менеджер Файлов")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #00D1FF; border: none;")
        layout.addWidget(title)

        help_text_label = QLabel()
        help_text_label.setWordWrap(True)
        help_text_label.setTextFormat(Qt.TextFormat.RichText)
        help_text_label.setText(
            """
            <p style='line-height: 150%;'>
                Этот менеджер позволяет вам управлять всеми файлами, клиентами и заказами в одном месте.
            </p>
            <p style='line-height: 150%; margin-top: 10px;'>
                <b>Основные возможности:</b>
            </p>
            <ul style='line-height: 160%; color: #AAAAAA; padding-left: 20px;'>
                <li><b>Просмотр:</b> Вся структура клиентов, заказов и файлов видна в виде дерева.</li>
                <li><b>Drag & Drop:</b> Перетаскивайте файлы и папки прямо в окно, чтобы добавить их к клиенту или заказу.</li>
                <li><b>Удаление:</b> Вы можете удалять файлы, заказы или клиентов прямо из этого окна.</li>
                <li><b>Быстрый доступ:</b> Двойной клик по файлу или папке откроет их в вашей системе.</li>
            </ul>
            """
        )
        layout.addWidget(help_text_label)

        ok_button = QPushButton("Понятно")
        ok_button.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_button.clicked.connect(help_dialog.accept)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        animate_dialog_open(help_dialog)
        animate_dialog_open(help_dialog)
        help_dialog.exec()
        
    def load_data(self):
        self.tree.clear()
        
        for client in self.parent_app.clients:
            client_item = QTreeWidgetItem(self.tree)
            client_item.setText(0, f"👤 {client.name}")
            client_item.setExpanded(True)
            # Храним ID клиента для drag&drop логики
            client_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "client", "id": client.id, "obj": client})
            
            for order in client.orders:
                order_item = QTreeWidgetItem(client_item)
                order_item.setText(0, f"📦 {order.service_type}")
                order_item.setText(1, order.status)
                order_item.setText(3, f"Заказ ({len(order.files)} файлов)")
                order_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "order", "id": order.id, "obj": order})
                
                # Файлы заказа
                for file in order.files:
                    file_item = QTreeWidgetItem(order_item)
                    is_folder = getattr(file, 'is_folder', os.path.isdir(file.path))
                    icon = "📁" if is_folder else "📄"
                    file_type_str = "folder" if is_folder else "file"
                    
                    file_item.setText(0, f"{icon} {file.name}")
                    file_item.setText(2, file.path)
                    file_item.setText(3, "Папка" if is_folder else "Файл")
                    file_item.setData(0, Qt.ItemDataRole.UserRole, {"type": file_type_str, "id": None, "obj": file})
                    
                    # Двойной клик для открытия
                    # Но QTreeWidget не имеет сигнала doubleClicked с item, нужно через сигнал itemDoubleClicked
                    
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)

    def on_item_double_clicked(self, item, column):
        # Открытие файла/папки
        path = item.text(1)
        if path and os.path.exists(path):
            try:
                os.startfile(path)
            except Exception as e:
                logger.error(f"Не удалось открыть {path}: {e}")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return
            
        # Определяем, куда сбросили
        item = self.tree.itemAt(event.position().toPoint())
        
        target_client = None
        target_order = None
        
        # Если это папка, и мы сбросили её на клиента, попробуем использовать её имя для заказа?
        # Но сначала определим цель
        if item:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                if data["type"] == "client":
                    target_client = data["obj"]
                elif data["type"] == "order":
                    target_order = data["obj"]
                    # Находим клиента через parent
                    parent_data = item.parent().data(0, Qt.ItemDataRole.UserRole)
                    if parent_data and parent_data["type"] == "client":
                        target_client = parent_data["obj"]
        
        # Если не попали на элемент, спрашиваем
        if not target_client and not target_order:
            # Используем новый диалог выбора клиента
            dialog = ClientSelectionDialog(self.parent_app, self)
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_client:
                target_client = dialog.selected_client
                # Обновляем дерево на случай если был создан новый клиент
                self.load_data()
            else:
                return

        if not target_client:
            return

        # Если заказ не выбран (сбросили на клиента), предлагаем создать новый или выбрать существующий
        if not target_order:
            # Если перетаскивается одна папка и она сброшена на клиента -> создаем заказ с именем папки автоматически?
            # Или предлагаем это как опцию.
            # По условию: "даже если перетаскивать на заказ, то добавляла папку прямо в тот заказ" - это уже работает.
            # "при перетаскивании папки на имя клиента, она сразу выбирала именно этого клиента" - это уже работает.
            
            # Проверим, если перетаскивается одна папка, предложим создать заказ с её именем
            suggested_name = ""
            if len(urls) == 1:
                path = urls[0].toLocalFile()
                if os.path.isdir(path):
                    suggested_name = os.path.basename(path)
            
            # Создаем диалог выбора заказа
            dialog = OrderSelectionDialog(target_client, self)
            # Если есть предположительное имя, можно было бы авто-создать, но лучше дать выбор.
            # Но если пользователь хочет "сразу", то диалог всё равно нужен для подтверждения или выбора существующего.
            
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_order:
                target_order = dialog.selected_order
            else:
                return

        # Теперь добавляем файлы в target_order
        # Используем логику из InternalFileManagerDialog для вопроса о хранении
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Хранение файлов")
        msg_box.setText(f"Добавление файлов к заказу '{target_order.service_type}'")
        msg_box.setInformativeText("Где хранить файлы?")
        
        btn_db = msg_box.addButton("В папке программы", QMessageBox.ButtonRole.ActionRole)
        btn_orig = msg_box.addButton("В исходном расположении", QMessageBox.ButtonRole.ActionRole)
        btn_custom = msg_box.addButton("Выбрать папку...", QMessageBox.ButtonRole.ActionRole)
        btn_help = msg_box.addButton("❓", QMessageBox.ButtonRole.HelpRole)
        btn_cancel = msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        
        # Цикл для возможности возврата из справки
        while True:
            msg_box.exec()
            clicked = msg_box.clickedButton()
            
            if clicked == btn_help:
                QMessageBox.information(self, "Справка по хранению",
                    "<b>В папке программы:</b>\n"
                    "Файлы копируются в папку базы данных. Надежно и централизованно.\n\n"
                    "<b>В исходном расположении:</b>\n"
                    "Файлы остаются там, где были. Программа просто запоминает путь.\n\n"
                    "<b>Выбрать папку:</b>\n"
                    "Копирование файлов в выбранную вами папку."
                )
                continue # Возвращаемся к выбору
            
            if clicked == btn_cancel:
                return
            
            break # Выход из цикла, если выбрано действие
        
        storage_mode = 'link'
        target_folder = None
        
        if clicked == btn_db:
            storage_mode = 'copy_db'
            db_root = self.parent_app.app_settings.get('database_path', os.path.dirname(self.parent_app.storage.path))
            target_folder = os.path.join(db_root, "attached_files", target_order.id)
            os.makedirs(target_folder, exist_ok=True)
        elif clicked == btn_custom:
            storage_mode = 'copy_custom'
            folder = QFileDialog.getExistingDirectory(self, "Выберите папку")
            if not folder: return
            target_folder = os.path.join(folder, target_order.id)
            os.makedirs(target_folder, exist_ok=True)
            
        added_count = 0
        for url in urls:
            source_path = url.toLocalFile()
            if not os.path.exists(source_path): continue
            
            final_path = source_path
            is_dir = os.path.isdir(source_path)
            
            if storage_mode in ['copy_db', 'copy_custom']:
                try:
                    base_name = os.path.basename(source_path)
                    new_path = os.path.join(target_folder, base_name)
                    counter = 1
                    name_part, ext_part = os.path.splitext(base_name)
                    while os.path.exists(new_path):
                        new_path = os.path.join(target_folder, f"{name_part}_{counter}{ext_part}")
                        counter += 1
                    
                    if is_dir:
                        # При копировании папки, если целевая папка (внутри заказа) уже существует, shutil.copytree упадет (до python 3.8 с dirs_exist_ok).
                        # Но мы выше проверяем exists(new_path) и генерируем уникальное имя, так что коллизии быть не должно на уровне корня копируемой папки.
                        shutil.copytree(source_path, new_path)
                    else:
                        shutil.copy2(source_path, new_path)
                    final_path = new_path
                except Exception as e:
                    logger.error(f"Error copying {source_path}: {e}")
                    continue
            
            if not any(f.path == final_path for f in target_order.files):
                target_order.files.append(ProjectFile(
                    path=final_path,
                    name=os.path.basename(final_path),
                    is_finished=False,
                    is_folder=is_dir
                ))
                added_count += 1
        
        if added_count > 0:
            self.parent_app.save_db()
            self.load_data() # Обновляем дерево
            # Обновляем профиль если открыт этот клиент
            if self.parent_app.current_client == target_client:
                self.parent_app.render_client_profile()
            QMessageBox.information(self, "Успех", f"Добавлено файлов: {added_count}")

    def show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item: return
        
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction

        context = QMenu(self)
        context.setStyleSheet("""
            QMenu {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #444444;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #3D3D3D;
            }
        """)

        data = item.data(0, Qt.ItemDataRole.UserRole)
        item_type = data.get("type") if data else None

        # --- Определение типа элемента и добавление действий ---
        
        if item_type == "client":
            edit_action = QAction("✏️ Редактировать карточку", self)
            edit_action.triggered.connect(lambda: self.edit_client_card(data.get("obj")))
            context.addAction(edit_action)
            context.addSeparator()

        elif item_type == "order":
            edit_action = QAction("✏️ Редактировать карточку заказа", self)
            edit_action.triggered.connect(lambda: self.edit_order_card(item))
            context.addAction(edit_action)
            
            rename_action = QAction("📝 Переименовать услугу", self)
            rename_action.triggered.connect(lambda: self.rename_order_service(item))
            context.addAction(rename_action)
            context.addSeparator()

        elif item_type == "file" or item_type == "folder":
            open_text = "📂 Открыть папку" if item_type == "folder" else "📄 Открыть файл"
            open_action = QAction(open_text, self)
            open_action.triggered.connect(lambda: self.open_path(data.get("obj").path))
            context.addAction(open_action)
            
            copy_path_action = QAction("📋 Копировать путь", self)
            copy_path_action.triggered.connect(lambda: self.copy_path_to_clipboard(data.get("obj").path))
            context.addAction(copy_path_action)
            
            rename_action = QAction("✏️ Переименовать", self)
            rename_action.triggered.connect(lambda: self.rename_file_item(item))
            context.addAction(rename_action)
            context.addSeparator()

        # Действие "Удалить"
        delete_action = QAction("🗑️ Удалить", self)
        delete_action.triggered.connect(self.delete_selected)
        context.addAction(delete_action)
        
        # Показываем меню
        global_pos = self.tree.viewport().mapToGlobal(pos)
        context.exec(global_pos)

    def edit_client_card(self, client):
        if client and hasattr(self.parent_app, 'open_client_by_id'):
            self.parent_app.open_client_by_id(client.id)
            self.accept() # Закрываем файловый менеджер

    def edit_order_card(self, item):
        # Находим клиента (родитель заказа в дереве)
        parent_item = item.parent()
        if parent_item:
            client_data = parent_item.data(0, Qt.ItemDataRole.UserRole)
            client = client_data.get("obj")
            if client and hasattr(self.parent_app, 'open_client_by_id'):
                self.parent_app.open_client_by_id(client.id)
                self.accept()

    def rename_order_service(self, item):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        order = data.get("obj")
        new_name, ok = QInputDialog.getText(self, "Переименование", "Новое название услуги:", text=order.service_type)
        if ok and new_name.strip():
            order.service_type = new_name.strip()
            item.setText(0, f"📦 {order.service_type}")
            self.parent_app.save_db()
            if self.parent_app.current_client and any(o == order for o in self.parent_app.current_client.orders):
                self.parent_app.render_client_profile()

    def rename_file_item(self, item):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        file_obj = data.get("obj")
        new_name, ok = QInputDialog.getText(self, "Переименование", "Новое имя:", text=file_obj.name)
        if ok and new_name.strip() and new_name != file_obj.name:
            old_path = file_obj.path
            new_path = os.path.join(os.path.dirname(old_path), new_name.strip())
            try:
                os.rename(old_path, new_path)
                file_obj.path = new_path
                file_obj.name = new_name.strip()
                item.setText(0, f"{'📁' if data.get('type') == 'folder' else '📄'} {file_obj.name}")
                item.setText(1, file_obj.path)
                self.parent_app.save_db()
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось переименовать: {e}")

    def copy_path_to_clipboard(self, path):
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText(path)

    def open_path(self, path):
        if path and os.path.exists(path):
            try:
                import platform
                import subprocess
                if platform.system() == "Windows":
                    os.startfile(path)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", path])
                else:
                    subprocess.Popen(["xdg-open", path])
            except Exception as e:
                logger.error(f"Не удалось открыть путь {path}: {e}")
                QMessageBox.warning(self, "Ошибка", f"Не удалось открыть: {e}")

    def delete_selected(self):
        item = self.tree.currentItem()
        if not item:
            QMessageBox.warning(self, "Внимание", "Выберите элемент для удаления")
            return
            
        data = item.data(0, Qt.ItemDataRole.UserRole)
        # В дереве нет data для файлов, так как мы их не добавляли в data role при создании
        # Исправим это в load_data или определим по родителю
        
        # Проверяем уровень вложенности
        # Уровень 0: Клиент
        # Уровень 1: Заказ
        # Уровень 2: Файл/Папка
        
        parent = item.parent()
        if not parent:
            # --- УДАЛЕНИЕ КЛИЕНТА ---
            # Это клиент (корневой элемент)
            client_data = item.data(0, Qt.ItemDataRole.UserRole)
            if not client_data or client_data["type"] != "client": return
            client = client_data["obj"]
            
            # Используем функцию удаления из главного окна
            self.parent_app.delete_client([client])
            self.load_data() # Перезагружаем дерево
            return
            
        grandparent = parent.parent()
        if not grandparent:
            # --- УДАЛЕНИЕ ЗАКАЗА ---
            # Это заказ (элемент второго уровня)
            order_data = item.data(0, Qt.ItemDataRole.UserRole)
            if not order_data or order_data["type"] != "order": return
            order = order_data["obj"]
            
            client_data = parent.data(0, Qt.ItemDataRole.UserRole)
            if not client_data or client_data["type"] != "client": return
            client = client_data["obj"]
            
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Удаление заказа")
            msg_box.setText(f"Удалить заказ '{order.service_type}'?")
            msg_box.setInformativeText(
                f"Сумма: {order.price} {getattr(order, 'currency', 'RUB')}\n"
                f"Получено: {order.total_received} {getattr(order, 'currency', 'RUB')}\n\n"
                "Это действие удалит заказ из истории и статистики.\n"
                "Деньги будут вычтены из дашбордов и общей кассы."
            )
            msg_box.setIcon(QMessageBox.Icon.Warning)
            
            btn_yes = msg_box.addButton("Удалить", QMessageBox.ButtonRole.YesRole)
            btn_cancel = msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
            
            msg_box.exec()
            
            if msg_box.clickedButton() == btn_yes:
                if order in client.orders:
                    client.orders.remove(order)
                    self.parent_app.save_db()
                    
                    # Обновляем UI
                    self.load_data()
                    
                    # Если этот клиент сейчас открыт в главном окне, обновляем его профиль и дашборд
                    if self.parent_app.current_client == client:
                        self.parent_app.render_client_profile()
                    
                    # Всегда обновляем общий дашборд, так как суммы изменились
                    self.parent_app.update_dash()
            return
            
        # --- УДАЛЕНИЕ ФАЙЛА ---
        # Это файл или папка внутри заказа
        # parent = заказ, grandparent = клиент
        order_data = parent.data(0, Qt.ItemDataRole.UserRole)
        if not order_data or order_data["type"] != "order": return
        
        order = order_data["obj"]
        file_path = item.text(1)
        
        # Находим файл в заказе
        target_file = next((f for f in order.files if f.path == file_path), None)
        
        if target_file:
            reply = QMessageBox.question(self, "Удаление", f"Удалить '{target_file.name}' из заказа?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                order.files.remove(target_file)
                self.parent_app.save_db()
                
                # Запоминаем состояние развернутости веток
                expanded_states = {}
                for i in range(self.tree.topLevelItemCount()):
                    client_item = self.tree.topLevelItem(i)
                    expanded_states[client_item.text(0)] = client_item.isExpanded()
                    for j in range(client_item.childCount()):
                        order_item = client_item.child(j)
                        # Ключ для заказа: ИмяКлиента|ИмяЗаказа
                        key = f"{client_item.text(0)}|{order_item.text(0)}"
                        expanded_states[key] = order_item.isExpanded()
                
                self.load_data()
                
                # Восстанавливаем состояние
                for i in range(self.tree.topLevelItemCount()):
                    client_item = self.tree.topLevelItem(i)
                    if expanded_states.get(client_item.text(0), False):
                        client_item.setExpanded(True)
                        
                    for j in range(client_item.childCount()):
                        order_item = client_item.child(j)
                        key = f"{client_item.text(0)}|{order_item.text(0)}"
                        if expanded_states.get(key, False):
                            order_item.setExpanded(True)
                
                if self.parent_app.current_client and any(o == order for o in self.parent_app.current_client.orders):
                    self.parent_app.render_client_profile()

# --- INTERNAL FILE MANAGER ---
class InternalFileManagerDialog(QDialog):
    def __init__(self, order: Order, parent=None):
        super().__init__(parent)
        self.order = order
        self.parent_app = parent
        self.setAcceptDrops(True)  # Enable Drag & Drop
        self.setWindowTitle(f"Файлы заказа: {order.service_type}")
        self.resize(800, 500)
        
        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; }
            QLabel { color: #FFFFFF; font-size: 12px; }
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #3D3D3D; }
            QTableWidget {
                background-color: #252525;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                gridline-color: #333333;
            }
            QHeaderView::section {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                padding: 4px;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # Инфо панель
        info_layout = QHBoxLayout()
        info_layout.addWidget(QLabel(f"Всего файлов: {len(self.order.files)}"))
        info_layout.addStretch()
        
        add_btn = QPushButton("➕ Добавить файлы")
        add_btn.clicked.connect(self.add_files)
        info_layout.addWidget(add_btn)
        
        layout.addLayout(info_layout)
        
        # Таблица файлов
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Имя", "Путь / Тип", "Действия"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 150)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        # Пересылаем события drag&drop от таблицы к диалогу
        self.table.viewport().installEventFilter(self)
        
        layout.addWidget(self.table)
        
        # Кнопки внизу
        btn_layout = QHBoxLayout()
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        
        self.refresh_table()
        
        animate_dialog_open(self)
        
    def refresh_table(self):
        self.table.setRowCount(0)
        
        # Сортировка: Папки сверху
        sorted_files = sorted(self.order.files, key=lambda x: (not getattr(x, 'is_folder', os.path.isdir(x.path)), x.name.lower()))
        
        for file_obj in sorted_files:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Имя
            is_folder = getattr(file_obj, 'is_folder', os.path.isdir(file_obj.path))
            prefix = "📁 " if is_folder else "📄 "
            
            name_item = QTableWidgetItem(f"{prefix}{file_obj.name}")
            name_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 0, name_item)
            
            # Путь
            path_item = QTableWidgetItem(file_obj.path)
            path_item.setToolTip(file_obj.path)
            path_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 1, path_item)
            
            # Действия
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(2, 2, 2, 2)
            actions_layout.setSpacing(4)
            
            open_btn = QPushButton("Открыть")
            open_btn.setStyleSheet("font-size: 10px; padding: 2px 5px;")
            open_btn.clicked.connect(lambda checked=False, f=file_obj: self.open_file(f))
            
            del_btn = QPushButton("❌")
            del_btn.setStyleSheet("font-size: 10px; padding: 2px 5px; color: #FF4B2B; border-color: #FF4B2B;")
            del_btn.clicked.connect(lambda checked=False, f=file_obj: self.delete_file(f))
            
            actions_layout.addWidget(open_btn)
            actions_layout.addWidget(del_btn)
            
            self.table.setCellWidget(row, 2, actions_widget)
            
    def open_file(self, file_obj):
        try:
            if os.path.exists(file_obj.path):
                os.startfile(file_obj.path)
            else:
                QMessageBox.warning(self, "Ошибка", f"Файл не найден:\n{file_obj.path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
            
    def delete_file(self, file_obj):
        reply = QMessageBox.question(self, "Удаление", f"Удалить '{file_obj.name}' из списка?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.order.files.remove(file_obj)
            self.parent_app.save_db()
            self.refresh_table()
            
    def add_files(self):
        # Используем существующий метод из виджета, но немного адаптируем
        # Или простейший вариант:
        files, _ = QFileDialog.getOpenFileNames(self, "Выберите файлы")
        if files:
            for f in files:
                self.order.files.append(ProjectFile(
                    path=f,
                    name=os.path.basename(f),
                    is_finished=False,
                    is_folder=False
                ))
            self.parent_app.save_db()
            self.refresh_table()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            item = self.tree.itemAt(event.position().toPoint())
            if item:
                self.tree.setCurrentItem(item)
                event.acceptProposedAction()
            else:
                self.tree.clearSelection()
                event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return
            
        # Запрашиваем место хранения один раз для всех файлов
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Хранение файлов")
        msg_box.setText("Где хранить файлы клиента?")
        msg_box.setInformativeText("Выберите способ хранения для добавляемых файлов.")
        
        btn_db = msg_box.addButton("В базе данных программы", QMessageBox.ButtonRole.ActionRole)
        btn_orig = msg_box.addButton("В исходном расположении", QMessageBox.ButtonRole.ActionRole)
        btn_custom = msg_box.addButton("Выбрать папку...", QMessageBox.ButtonRole.ActionRole)
        btn_cancel = msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        
        msg_box.exec()
        clicked = msg_box.clickedButton()
        
        if clicked == btn_cancel:
            return
            
        storage_mode = 'link' # default
        target_folder = None
        
        if clicked == btn_db:
            storage_mode = 'copy_db'
            # Путь к папке базы данных
            db_root = self.parent_app.app_settings.get('database_path', os.path.dirname(self.parent_app.storage.path))
            target_folder = os.path.join(db_root, "attached_files", self.order.id)
            os.makedirs(target_folder, exist_ok=True)
            
        elif clicked == btn_custom:
            storage_mode = 'copy_custom'
            folder = QFileDialog.getExistingDirectory(self, "Выберите папку для сохранения")
            if not folder:
                return
            # Создаем подпапку заказа для порядка
            target_folder = os.path.join(folder, self.order.id)
            os.makedirs(target_folder, exist_ok=True)
            
        added = False
        
        for url in urls:
            source_path = url.toLocalFile()
            if not os.path.exists(source_path):
                continue
                
            final_path = source_path
            is_dir = os.path.isdir(source_path)
            
            if storage_mode in ['copy_db', 'copy_custom']:
                try:
                    base_name = os.path.basename(source_path)
                    new_path = os.path.join(target_folder, base_name)
                    
                    # Обработка дубликатов имен
                    counter = 1
                    name_part, ext_part = os.path.splitext(base_name)
                    while os.path.exists(new_path):
                        new_path = os.path.join(target_folder, f"{name_part}_{counter}{ext_part}")
                        counter += 1
                    
                    if is_dir:
                        shutil.copytree(source_path, new_path)
                    else:
                        shutil.copy2(source_path, new_path)
                        
                    final_path = new_path
                except Exception as e:
                    logger.error(f"Ошибка копирования {source_path}: {e}")
                    QMessageBox.warning(self, "Ошибка", f"Не удалось скопировать {base_name}: {e}")
                    continue # Пропускаем файл при ошибке копирования
            
            # Проверяем дубликаты в списке файлов заказа (по пути)
            if any(f.path == final_path for f in self.order.files):
                continue
                
            self.order.files.append(ProjectFile(
                path=final_path,
                name=os.path.basename(final_path),
                is_finished=False,
                is_folder=is_dir
            ))
            added = True
        
        if added:
            self.parent_app.save_db()
            self.refresh_table()

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
            title_label.setStyleSheet("color: #DDDDDD; font-size: 12px;")
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
        
        animate_dialog_open(self)
    
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
                # MessageBox removed as per user request
            except ValueError as e:
                logger.error(f"Ошибка удаления платежа: {e}")
                QMessageBox.warning(self, "Ошибка", str(e))

# --- ДИАЛОГ ИМПОРТА ИЗ ПАПКИ ---
class FolderImportDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Импорт клиентов из папки")
        self.setFixedSize(500, 400)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
            }
            QLabel {
                color: #DDDDDD;
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
            QCheckBox {
                color: #DDDDDD;
                font-size: 12px;
                padding: 3px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #555555;
                background: #222222;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #00D1FF;
                background: #00D1FF;
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

        # Опция импорта пустых
        self.import_empty_cb = QCheckBox("Импортировать папки без файлов")
        layout.addWidget(self.import_empty_cb)
        
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
        
        animate_dialog_open(self)
    
    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку для импорта")
        if folder:
            self.folder_edit.setText(folder)
    
    def scan_folder(self):
        folder = self.folder_edit.text()
        if not folder or not os.path.exists(folder):
            QMessageBox.warning(self, "Ошибка", "Выберите существующую папку")
            return
        
        # 1. Исходная структура папок: Программа получает на вход путь к Папке Клиента.
        # Внутри неё структура строго следующая:
        # Папка Клиента (Пример: "Верди")
        #   Папка Заказа (Пример: "Травиата") — это уровень создания карточек.
        #     Вложенные элементы (Пример: "Действие 1", "Действие 2", "Файл_инфо.txt") — это содержимое карточки.
        
        self.preview_list.clear()
        self.scan_results = []
        
        # Просканируй все папки внутри выбранной "Папки Клиента" (корневой папки импорта)
        # В контексте диалога: пользователь выбирает "Корневую папку", в которой лежат папки КЛИЕНТОВ.
        # Т.е. структура: Root -> Client -> Order -> Files/Dirs
        
        # Если пользователь выбирает сразу папку Клиента (например "Верди"), то мы должны это определить.
        # Но для универсальности будем считать, что пользователь выбирает папку,
        # В КОТОРОЙ лежат папки клиентов.
        
        # ИЛИ, следуя задаче: "Программа получает на вход путь к Папке Клиента".
        # Если диалог называется "Импорт из папки", логичнее выбирать корневую папку с клиентами.
        # Давайте поддержим оба варианта:
        # 1. Выбрана папка с клиентами (внутри папки клиентов, внутри папки заказов)
        # 2. Выбрана папка одного клиента (внутри папки заказов)
        
        root_items = [os.path.join(folder, item) for item in os.listdir(folder)]
        subfolders = [d for d in root_items if os.path.isdir(d)]
        
        # Предполагаем, что выбрана корневая папка, содержащая КЛИЕНТОВ.
        # Проходимся по каждой папке (Клиенту)
        for client_path in subfolders:
            client_name = os.path.basename(client_path)
            
            # Внутри папки Клиента ищем папки Заказов
            client_items = [os.path.join(client_path, item) for item in os.listdir(client_path)]
            order_folders = [d for d in client_items if os.path.isdir(d)]
            
            for order_path in order_folders:
                order_name = os.path.basename(order_path)
                
                # Важное ограничение: Внутри "Папки Заказа" учитывай только первый уровень вложенности.
                # Не нужно заходить внутрь папок "Действие 1" и т.д.
                # Собираем все элементы (папки и файлы) внутри папки заказа
                
                order_content = []
                try:
                    for item in os.listdir(order_path):
                        item_path = os.path.join(order_path, item)
                        # Сохраняем имя и полный путь
                        order_content.append((item, item_path))
                except Exception as e:
                    logger.error(f"Ошибка чтения папки {order_path}: {e}")
                    continue
                
                if order_content:
                    self.scan_results.append({
                        'client_name': client_name,
                        'order_name': order_name,
                        'files': order_content # Теперь здесь и файлы и папки
                    })
                    
                    count = len(order_content)
                    self.preview_list.addItem(f"Клиент: {client_name} -> Заказ: {order_name} (Обнаружено элементов: {count})")

        if self.scan_results:
            self.import_btn.setEnabled(True)
            self.preview_list.addItem(f"\nВсего будет создано: {len(self.scan_results)} заказов")
        else:
            self.preview_list.addItem("Структура не распознана. Убедитесь, что структура папок соответствует:\nПапка Клиента -> Папка Заказа -> Содержимое")

# --- ДИАЛОГ ПЕРВОГО ЗАПУСКА ---
class FirstRunDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добро пожаловать в FinanceFugue")
        self.resize(700, 580)
        self.setMinimumSize(600, 480)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
            }
            QLabel {
                color: #DDDDDD;
                font-size: 13px; /* Увеличил базовый размер */
            }
            QGroupBox {
                color: #FFFFFF;
                border: 2px solid #444444;
                border-radius: 6px; /* Чуть больше радиус */
                margin-top: 12px; /* Чуть больше отступ сверху */
                font-size: 15px; /* Увеличил размер шрифта */
                font-weight: bold;
                padding-top: 18px; /* Чуть больше padding */
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px; /* Чуть больше отступ слева */
                padding: 0 8px 0 8px; /* Немного уменьшил padding для компактности */
                color: #00D1FF;
            }
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                padding: 8px 16px; /* Уменьшил padding */
                border-radius: 4px;
                border: 1px solid #3D3D3D;
                font-size: 13px; /* Уменьшил размер шрифта для кнопок */
            }
            QPushButton:hover {
                background-color: #3D3D3D;
            }
            /* Стили для ToggleSwitch */
            ToggleSwitch {
                background-color: #333333;
                border-radius: 14px;
            }
            QRadioButton {
                color: #DDDDDD;
                font-size: 13px;
                padding: 4px 0; /* Добавил padding для читаемости */
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
        
        # Приветствие (H1 и Sub)
        title_label = QLabel("<h1><b>FinanceFugue</b></h1>")
        title_label.setStyleSheet("font-size: 38px; color: #00D1FF; letter-spacing: 1px;") # Увеличил шрифт, добавил letter-spacing
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        subtitle_label = QLabel("Профессиональная система управления заказами для творческих команд") # Более полный текст
        subtitle_label.setStyleSheet("font-size: 15px; color: #AAAAAA; font-style: italic;") # Уменьшил шрифт
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle_label)
        
        layout.addSpacing(15)
        
        # Выбор места хранения базы данных (Секция 1)
        db_group = QGroupBox("Расположение базы данных") # Изменил заголовок группы
        db_layout = QVBoxLayout(db_group)
        db_layout.setContentsMargins(15, 15, 15, 15)
        
        db_layout.addWidget(QLabel("Укажите, где будет храниться файл базы данных:")) # Уточнил текст
        
        self.db_path_app_folder_rb = QRadioButton("В папке с программой (Портативно)")
        self.db_path_custom_rb = QRadioButton("Выбрать другую папку...")
        
        self.db_path_app_folder_rb.setChecked(True)
        
        self.db_path_app_folder_rb.toggled.connect(self.update_db_path_ui)
        self.db_path_custom_rb.toggled.connect(self.update_db_path_ui)

        db_layout.addWidget(self.db_path_app_folder_rb)
        db_layout.addWidget(self.db_path_custom_rb)
        
        self.custom_db_path_widget = QWidget()
        custom_db_path_layout = QHBoxLayout(self.custom_db_path_widget)
        custom_db_path_layout.setContentsMargins(0, 0, 0, 0)
        
        self.db_path_edit = QLineEdit(os.getcwd())
        self.db_path_edit.setReadOnly(True)
        self.db_path_edit.setStyleSheet("""
            QLineEdit {
                background-color: #252525;
                color: #FFFFFF;
                border: 1px solid #444444;
                padding: 6px; /* Уменьшил padding */
                border-radius: 4px;
                font-size: 12px; /* Уменьшил шрифт */
            }
        """)
        
        browse_btn = QPushButton("Обзор...")
        browse_btn.clicked.connect(self.browse_db_folder)
        browse_btn.setFixedWidth(80) # Уменьшил ширину кнопки
        
        custom_db_path_layout.addWidget(self.db_path_edit, 1)
        custom_db_path_layout.addWidget(browse_btn)
        self.custom_db_path_widget.setVisible(False)
        
        db_layout.addWidget(self.custom_db_path_widget)
        layout.addWidget(db_group)

        # Настройка безопасности (Секция 2)
        # Настройка безопасности (Секция 2)
        sec_group = QGroupBox("Безопасность")
        sec_layout = QVBoxLayout(sec_group)
        sec_layout.setContentsMargins(15, 15, 15, 15)
        
        # Шифрование данных (ToggleSwitch)
        enc_inner_layout = QHBoxLayout()
        enc_inner_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        security_label = QLabel("Шифрование базы данных:")
        security_label.setStyleSheet("font-size: 13px; color: #FFFFFF; font-weight: bold;")
        
        self.encryption_switch = ToggleSwitch(width=110, height=26, on_text="шифровать", off_text="не шифровать")
        self.encryption_switch.setChecked(True) # По умолчанию включен
        self.encryption_switch.toggled.connect(self.update_security_ui)
        
        enc_inner_layout.addWidget(security_label)
        enc_inner_layout.addSpacing(10)
        enc_inner_layout.addWidget(self.encryption_switch)
        enc_inner_layout.addStretch()
        sec_layout.addLayout(enc_inner_layout)
        
        self.encryption_hint_label = QLabel("Рекомендуется для защиты конфиденциальной информации. Может снизить производительность.") # Сократил текст
        self.encryption_hint_label.setStyleSheet("color: #AAAAAA; font-size: 11px; margin-left: 5px;")
        self.encryption_hint_label.setWordWrap(True)
        sec_layout.addWidget(self.encryption_hint_label)
        
        sec_layout.addSpacing(15)
        
        # Запрос пароля при запуске программы (Чекбокс)
        pass_access_layout = QHBoxLayout()
        pass_access_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.app_password_cb = QCheckBox("Запрашивать пароль при запуске") # Сократил текст
        self.app_password_cb.setStyleSheet("font-size: 13px; color: #FFFFFF; font-weight: bold;")
        self.app_password_cb.setChecked(False)
        self.app_password_cb.toggled.connect(self.update_security_ui)
        
        pass_access_layout.addWidget(self.app_password_cb)
        pass_access_layout.addStretch()
        sec_layout.addLayout(pass_access_layout)

        self.password_hint_label = QLabel("Задает пароль для входа. Если шифрование включено, этот пароль будет использоваться и для него.")
        self.password_hint_label.setStyleSheet("color: #AAAAAA; font-size: 11px; margin-left: 5px;")
        self.password_hint_label.setWordWrap(True)
        sec_layout.addWidget(self.password_hint_label)

        self.password_widget = QWidget()
        self.password_widget.setVisible(False) # По умолчанию скрыто
        pass_layout_fields = QVBoxLayout(self.password_widget)
        pass_layout_fields.setContentsMargins(0, 10, 0, 0)
        
        pass_layout_fields.addWidget(QLabel("Придумайте пароль:"))
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_edit.setPlaceholderText("Пароль...")
        self.pass_edit.setStyleSheet("background-color: #252525; color: #FFFFFF; border: 1px solid #444444; padding: 8px; border-radius: 4px;")
        
        self.pass_confirm = QLineEdit()
        self.pass_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_confirm.setPlaceholderText("Подтверждение пароля...")
        self.pass_confirm.setStyleSheet("background-color: #252525; color: #FFFFFF; border: 1px solid #444444; padding: 8px; border-radius: 4px;")
        
        pass_layout_fields.addWidget(self.pass_edit)
        pass_layout_fields.addWidget(self.pass_confirm)
        
        self.warning_label_password = QLabel("⚠️ Внимание: Если вы забудете пароль, данные могут быть утеряны навсегда! Запишите его.")
        self.warning_label_password.setStyleSheet("color: #FF4B2B; font-size: 11px;")
        self.warning_label_password.setWordWrap(True)
        pass_layout_fields.addWidget(self.warning_label_password)
        
        sec_layout.addWidget(self.password_widget)
        layout.addWidget(sec_group)
        
        # Выбор способа хранения файлов (Секция 3)
        section_label = QLabel("<b>Хранение файлов клиентов</b>")
        section_label.setStyleSheet("font-size: 15px; color: #00D1FF; margin-bottom: 8px; margin-top: 10px;")
        layout.addWidget(section_label)
        layout.addWidget(QLabel("Выберите способ хранения добавляемых файлов:"))
        
        self.cb_file_link = QCheckBox("В исходной папке")
        self.cb_file_copy = QCheckBox("В папке программы")
        
        self.cb_file_link.setChecked(True)
        self.cb_file_link.toggled.connect(self.update_file_storage_ui)
        self.cb_file_copy.toggled.connect(self.update_file_storage_ui)
        
        layout.addWidget(self.cb_file_link)
        layout.addWidget(self.cb_file_copy)
        
        # Опция шифрования файлов (только для копирования)
        self.file_encryption_widget = QWidget()
        fe_layout = QHBoxLayout(self.file_encryption_widget)
        fe_layout.setContentsMargins(20, 0, 0, 0)
        
        self.file_encryption_cb = QCheckBox("Шифровать файлы на диске")
        self.file_encryption_cb.setToolTip("Файлы будут зашифрованы в папке программы. Доступ к ним будет только через это приложение.")
        fe_layout.addWidget(self.file_encryption_cb)
        
        self.file_encryption_widget.setVisible(False)
        layout.addWidget(self.file_encryption_widget)
        
        # Прочие настройки (Секция 4)
        misc_group = QGroupBox("Прочие настройки")
        misc_layout = QVBoxLayout(misc_group)
        misc_layout.setContentsMargins(15, 15, 15, 15)

        self.create_shortcut_cb = QCheckBox("Создать ярлык программы на рабочем столе")
        self.create_shortcut_cb.setChecked(False) # По умолчанию не создавать
        misc_layout.addWidget(self.create_shortcut_cb)

        layout.addWidget(misc_group)

        # Кнопки (ОК/Отмена)
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        start_btn = QPushButton("Начать работу")
        start_btn.setStyleSheet("""
            QPushButton {
                background-color: #28A745;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        start_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(start_btn)
        
        layout.addLayout(buttons_layout)
        
        # Обновляем UI после инициализации всех элементов
        self.update_db_path_ui()
        self.update_security_ui()
        self.update_file_storage_ui()

        animate_dialog_open(self)
    
    def update_file_storage_ui(self):
        is_copy = self.cb_file_copy.isChecked()
        self.file_encryption_widget.setVisible(is_copy)
        if not is_copy:
            self.file_encryption_cb.setChecked(False)

    def browse_db_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку для базы данных")
        if folder:
            self.db_path_edit.setText(folder)
            self.db_path_custom_rb.setChecked(True) # Выбираем "Выбрать папку вручную" если пользователь выбрал папку

    def update_db_path_ui(self):
        if self.db_path_app_folder_rb.isChecked():
            self.db_path_edit.setText(os.getcwd())
            self.custom_db_path_widget.setVisible(False)
        elif self.db_path_custom_rb.isChecked():
            self.custom_db_path_widget.setVisible(True)

    def get_final_db_path(self):
        return self.db_path_edit.text()

    def update_security_ui(self):
        enc_on = self.encryption_switch.isChecked()
        app_pass_on = self.app_password_cb.isChecked()
        
        self.encryption_hint_label.setVisible(True) # Всегда показываем подсказку по шифрованию
        self.password_widget.setVisible(app_pass_on)
        
        # Обновляем текст подсказок
        if enc_on:
            self.encryption_hint_label.setText("Рекомендуется для защиты конфиденциальной информации. База данных будет зашифрована.")
            if app_pass_on:
                self.password_hint_label.setText("Пароль будет использоваться для шифрования и входа в программу.")
                self.password_hint_label.setVisible(True)
            else:
                self.password_hint_label.setText("База данных будет зашифрована внутренним ключом и не будет требовать пароль для доступа.")
                self.password_hint_label.setVisible(True)
        else:
            self.encryption_hint_label.setText("База данных не будет зашифрована. Это снижает защиту конфиденциальной информации.")
            if app_pass_on:
                self.password_hint_label.setText("Пароль будет запрашиваться только для входа в программу. Данные не шифруются.")
                self.password_hint_label.setVisible(True)
            else:
                self.password_hint_label.setVisible(False) # Скрываем, если ни шифрования, ни пароля на вход
                self.password_widget.setVisible(False)


    def accept(self):
        # Проверяем пароль, только если установлен флажок "Запрашивать пароль при запуске"
        if self.app_password_cb.isChecked():
            p1 = self.pass_edit.text()
            p2 = self.pass_confirm.text()
            if not p1:
                QMessageBox.warning(self, "Ошибка", "Введите пароль для входа в программу")
                return
            if p1 != p2:
                QMessageBox.warning(self, "Ошибка", "Пароли не совпадают")
                return
        
        # Проверяем выбранную папку для БД, если выбрана кастомная
        if self.db_path_custom_rb.isChecked():
            folder = self.db_path_edit.text()
            if not folder or not os.path.isdir(folder):
                QMessageBox.warning(self, "Ошибка", "Выберите существующую папку для базы данных.")
                return

        super().accept()
    
    def get_settings(self):
        # Определение пути к базе данных
        database_path = self.get_final_db_path()

        # Определение режима хранения файлов
        file_storage_mode = 'copy' if self.cb_file_copy.isChecked() else 'link'
        
        # Определение пароля (только если установлен флажок "Запрашивать пароль")
        password = self.pass_edit.text() if self.app_password_cb.isChecked() else None
        
        # Определение состояния создания ярлыка
        create_shortcut = self.create_shortcut_cb.isChecked()

        return {
            'database_path': database_path,
            'file_storage_mode': file_storage_mode,
            'encryption_enabled': self.encryption_switch.isChecked(), # Добавляем флаг шифрования
            'file_encryption_enabled': self.file_encryption_cb.isChecked(), # Шифрование файлов
            'app_password': password, # Это пароль на запуск программы (может быть None)
            'create_shortcut': create_shortcut
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
                color: #DDDDDD;
                font-size: 12px;
            }
            QCheckBox {
                color: #FFFFFF;
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
        
        animate_dialog_open(self)
    
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
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
        form = QFormLayout()
        
        self.name_edit = QLineEdit(client.name)
        form.addRow("Имя:", self.name_edit)

        # Добавляем новые поля для соцсетей
        self.email_edit = QLineEdit(getattr(client, 'email', ''))
        form.addRow("Email:", self.email_edit)

        self.telegram_edit = QLineEdit(getattr(client, 'telegram', ''))
        self.telegram_edit.setPlaceholderText("username или t.me/username")
        form.addRow("Telegram:", self.telegram_edit)

        self.vk_edit = QLineEdit(getattr(client, 'vk', ''))
        self.vk_edit.setPlaceholderText("vk.com/id12345")
        form.addRow("ВКонтакте:", self.vk_edit)
        
        self.facebook_edit = QLineEdit(getattr(client, 'facebook', ''))
        self.facebook_edit.setPlaceholderText("facebook.com/profile.php?id=...")
        form.addRow("Facebook:", self.facebook_edit)
        
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
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
            }
        """)
        export_layout = QVBoxLayout(export_group)
        export_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Кнопка "Экспорт файлов" клиента
        export_files_btn = QPushButton("📁 Экспорт файлов")
        export_files_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        export_files_btn.clicked.connect(self.parent_app.export_client_files)
        
        # Кнопка "Экспорт заказов" клиента
        export_orders_btn = QPushButton("📊 Экспорт заказов")
        export_orders_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        export_orders_btn.clicked.connect(self.parent_app.export_client_orders)
        
        export_layout.addWidget(export_files_btn)
        export_layout.addWidget(export_orders_btn)
        layout.addWidget(export_group)
        
        # Удаление клиента
        del_btn = QPushButton("🗑️ Удалить клиента")
        del_btn.setStyleSheet("""
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
                margin-top: 15px;
            }
            QPushButton:hover {
                background-color: #3D3D3D;
            }
        """)
        del_btn.clicked.connect(self.delete_client)
        layout.addWidget(del_btn)
        
        # Кнопки ОК/Отмена
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        
        animate_dialog_open(self)
        
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
        self.main_window = parent
        self.setWindowTitle("Настройки")
        
        self.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
            }
            QLabel {
                color: #FFFFFF;
                font-size: 14px;
                padding: 5px;
            }
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                padding: 10px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #3D3D3D;
            }
            QPushButton:pressed {
                background-color: #4D4D4D;
            }
            QGroupBox {
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                border-radius: 5px;
                margin-top: 10px;
                font-size: 14px;
                font-weight: bold;
                padding-top: 15px;
            }
            QCheckBox {
                color: #DDDDDD;
                font-size: 12px;
                padding: 3px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #555555;
                background: #222222;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #00D1FF;
                background: #00D1FF;
            }
            QGroupBox#DatabaseGroup {
                background-color: #1F2630; /* Темный серо-синий */
                border-color: #30363D;
            }
            QGroupBox#SettingsGroup {
                background-color: #2A2A2A; /* Темный серый */
                border-color: #3D3D3D;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px 0 5px;
                color: #00D1FF;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
        layout.setSpacing(5)
        
        # Группа управления базой данных
        db_group = QGroupBox("База данных")
        db_group.setObjectName("DatabaseGroup")
        db_layout = QVBoxLayout(db_group)
        db_layout.setSpacing(5)
        db_layout.setContentsMargins(10, 10, 10, 10)
        
        btn_db_location = QPushButton("Выбрать место хранения")
        btn_db_location.clicked.connect(self.change_database_location)
        
        btn_imp_folder = QPushButton("Импорт из папки")
        btn_imp_folder.clicked.connect(self.main_window.import_from_folder)
        
        btn_exp = QPushButton("Экспорт (JSON)")
        btn_exp.clicked.connect(self.main_window.export_json)
        
        btn_imp = QPushButton("Импорт (JSON)")
        btn_imp.clicked.connect(self.main_window.import_json_file)
        
        btn_full = QPushButton("Полный бэкап (ZIP)")
        btn_full.clicked.connect(self.main_window.export_full_backup)
        
        db_layout.addWidget(btn_db_location)
        db_layout.addWidget(btn_imp_folder)
        db_layout.addWidget(btn_exp)
        db_layout.addWidget(btn_imp)
        db_layout.addWidget(btn_full)
        
        # Кнопка удаления всех файлов
        btn_del_files = QPushButton("🗑 Удалить ВСЕ файлы")
        btn_del_files.clicked.connect(self.main_window.delete_all_files)
        db_layout.addWidget(btn_del_files)

        # Кнопка удаления всей базы
        btn_del_db = QPushButton("☠ Удалить ВСЮ базу данных")
        btn_del_db.clicked.connect(self.main_window.delete_database_full)
        db_layout.addWidget(btn_del_db)

        layout.addWidget(db_group)

        # Группа настроек приложения
        settings_group = QGroupBox("Настройки")
        settings_group.setObjectName("SettingsGroup")
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setSpacing(5)
        settings_layout.setContentsMargins(10, 10, 10, 10)
        
        btn_backup_settings = QPushButton("Создать копию настроек")
        btn_backup_settings.clicked.connect(self.manual_backup_settings)
        
        btn_restore_settings = QPushButton("Восстановить настройки")
        btn_restore_settings.clicked.connect(self.restore_settings_dialog)

        btn_security = QPushButton("🔐 Настройки безопасности")
        btn_security.clicked.connect(self.open_security_settings)
        
        settings_layout.addWidget(btn_backup_settings)
        settings_layout.addWidget(btn_restore_settings)
        settings_layout.addWidget(btn_security)
        
        layout.addWidget(settings_group)
        layout.addSpacing(10)
        
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
        
        animate_dialog_open(self)
    
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
            self.main_window.backup_settings()
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
            # Создаем путь к новой базе
            new_db_path = Path(folder) / "pro_database.json"
            
            # Проверяем, не выбрана ли та же самая папка
            if self.main_window.storage.path.exists() and new_db_path.resolve() == self.main_window.storage.path.resolve():
                QMessageBox.information(self, "Информация", "База данных уже находится в выбранной папке.")
                return

            # Сохраняем текущую базу перед переносом
            self.main_window.save_db()
            
            if move_files:
                # Создаем структуру папок для файлов
                files_folder = Path(folder) / "attached_files"
                files_folder.mkdir(exist_ok=True)
                
                # Копируем файлы
                for client in self.main_window.clients:
                    for order in client.orders:
                        # Мы должны обновить пути в объектах файлов
                        # При этом мы не удаляем старые файлы (как просил пользователь)
                        # Мы просто копируем их в новое место и обновляем ссылки
                        for file in order.files:
                            if os.path.exists(file.path):
                                # Создаем папку для заказа
                                order_folder = files_folder / order.id
                                order_folder.mkdir(exist_ok=True)
                                
                                new_file_path = order_folder / file.name
                                # Если это папка, копируем как папку
                                if os.path.isdir(file.path):
                                    if os.path.exists(new_file_path):
                                        # Если папка уже есть, возможно стоит добавить суффикс,
                                        # но пока просто перезапишем/объединим (copytree требует отсутствия)
                                        # shutil.copytree(file.path, new_file_path, dirs_exist_ok=True) # py3.8+
                                        pass
                                        # Для простоты пропустим сложные случаи с папками пока,
                                        # или используем distutils.dir_util.copy_tree
                                else:
                                    shutil.copy2(file.path, new_file_path)
                                
                                # Обновляем путь в базе данных на новый
                                file.path = str(new_file_path)
            
            # Копируем саму базу данных, если она существует
            if self.main_window.storage.path.exists():
                shutil.copy2(self.main_window.storage.path, new_db_path)
            
            # Обновляем путь к базе данных в приложении
            self.main_window.storage.path = new_db_path
            self.main_window.app_settings['database_path'] = folder
            
            # Сохраняем обновленную базу данных (уже с новыми путями) по новому адресу
            self.main_window.save_db()
            self.main_window.save_settings()
            
            QMessageBox.information(
                self,
                "Успех",
                f"База данных успешно перенесена в:\n{folder}\n\n"
                f"{'Файлы были скопированы в новую базу данных и привязаны к новому месту' if move_files else 'Файлы остались на старых местах'}"
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
                
                self.main_window.app_settings = new_settings
                self.main_window.save_settings()
                
                QMessageBox.information(self, "Успех",
                                      "Настройки восстановлены. Перезапустите приложение для применения изменений.")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось восстановить настройки: {e}")

    def open_security_settings(self):
        """Открытие настроек безопасности"""
        # Сначала запрашиваем текущий пароль, если он установлен
        if hasattr(self.main_window, 'backend') and self.main_window.backend.security.is_encrypted():
            pwd, ok = QInputDialog.getText(self, "Проверка доступа", "Введите текущий пароль:", QLineEdit.EchoMode.Password)
            if not ok: return
            if not self.main_window.backend.check_password(pwd):
                QMessageBox.critical(self, "Ошибка", "Неверный пароль")
                return
            current_password = pwd
        else:
            current_password = None

        dialog = SecuritySettingsDialog(self.main_window, current_password)
        dialog.exec()

class SecuritySettingsDialog(QDialog):
    def __init__(self, main_window, current_password=None):
        super().__init__(main_window)
        self.main_window = main_window
        self.current_password = current_password
        self.backend = main_window.backend
        self.setWindowTitle("Настройки безопасности")
        self.setFixedWidth(450)
        
        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; }
            QLabel { color: #FFFFFF; font-size: 12px; }
            QLineEdit { background-color: #333333; color: white; border: 1px solid #444444; padding: 5px; border-radius: 3px; }
            QPushButton { background-color: #2D2D2D; color: white; border: 1px solid #3D3D3D; padding: 8px; border-radius: 4px; }
            QPushButton:hover { background-color: #3D3D3D; }
            QRadioButton, QCheckBox { color: white; font-size: 13px; }
            QGroupBox { color: #00D1FF; font-weight: bold; border: 1px solid #444444; border-radius: 5px; margin-top: 10px; padding-top: 15px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        is_encrypted = self.backend.security.is_encrypted()
        has_password = self.backend.security.has_app_password()
        
        # 1. Секция Шифрования
        self.gb_enc = QGroupBox("Шифрование базы данных")
        enc_layout = QVBoxLayout(self.gb_enc)
        
        self.rb_enc_on = QRadioButton("Зашифровать (Максимальная защита)")
        self.rb_enc_off = QRadioButton("Не шифровать (Высокая скорость)")
        
        if is_encrypted:
            self.rb_enc_on.setChecked(True)
        else:
            self.rb_enc_off.setChecked(True)
            
        enc_layout.addWidget(self.rb_enc_on)
        enc_layout.addWidget(self.rb_enc_off)
        layout.addWidget(self.gb_enc)
        
        # 2. Секция Доступа
        self.gb_access = QGroupBox("Контроль доступа")
        access_layout = QVBoxLayout(self.gb_access)
        
        self.cb_app_pass = QCheckBox("Запрашивать пароль при запуске программы")
        if has_password or is_encrypted:
            self.cb_app_pass.setChecked(True)
            
        access_layout.addWidget(self.cb_app_pass)
        layout.addWidget(self.gb_access)
        
        # 3. Поля пароля
        self.pass_widget = QWidget()
        pass_layout = QFormLayout(self.pass_widget)
        pass_layout.setContentsMargins(5, 5, 5, 5)
        
        self.lbl_pass_info = QLabel("") # Динамический текст
        self.lbl_pass_info.setStyleSheet("color: #AAAAAA; font-style: italic; margin-bottom: 5px;")
        pass_layout.addRow(self.lbl_pass_info)
        
        self.new_pass = QLineEdit()
        self.new_pass.setEchoMode(QLineEdit.EchoMode.Password)
        pass_layout.addRow("Новый пароль:", self.new_pass)
        
        self.confirm_pass = QLineEdit()
        self.confirm_pass.setEchoMode(QLineEdit.EchoMode.Password)
        pass_layout.addRow("Подтверждение:", self.confirm_pass)
        
        layout.addWidget(self.pass_widget)
        
        # Кнопки
        btn_apply = QPushButton("Применить")
        btn_apply.setStyleSheet("background-color: #0078D7; font-weight: bold;")
        btn_apply.clicked.connect(self.apply_changes)
        
        layout.addStretch()
        layout.addWidget(btn_apply)
        
        # Signals
        self.rb_enc_on.toggled.connect(self.update_ui)
        self.cb_app_pass.toggled.connect(self.update_ui)
        
        self.update_ui()
        animate_dialog_open(self)

    def update_ui(self):
        enc_on = self.rb_enc_on.isChecked()
        
        if enc_on:
            # Если шифрование включено -> пароль обязателен для шифрования
            self.gb_access.setEnabled(False)
            self.cb_app_pass.setChecked(True)
            self.pass_widget.setVisible(True)
            self.lbl_pass_info.setText("Пароль используется для шифрования и входа.")
        else:
            # Если шифрование выключено -> пароль опционален для доступа
            self.gb_access.setEnabled(True)
            pass_enabled = self.cb_app_pass.isChecked()
            self.pass_widget.setVisible(pass_enabled)
            self.lbl_pass_info.setText("Пароль будет запрашиваться только для входа.")

    def apply_changes(self):
        want_enc = self.rb_enc_on.isChecked()
        want_pass = self.cb_app_pass.isChecked()
        
        cur_enc = self.backend.security.is_encrypted()
        cur_has_pass = self.backend.security.has_app_password()
        
        p1 = self.new_pass.text()
        p2 = self.confirm_pass.text()
        
        # Сценарий 1: Включение шифрования
        if want_enc and not cur_enc:
            if not p1:
                QMessageBox.warning(self, "Ошибка", "Для шифрования необходимо задать пароль")
                return
            if p1 != p2:
                QMessageBox.warning(self, "Ошибка", "Пароли не совпадают")
                return
                
            reply = QMessageBox.warning(self, "Шифрование",
                "Внимание! Если вы забудете пароль, данные восстановить будет НЕВОЗМОЖНО.\nПродолжить?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No: return
            
            if self.backend.change_encryption_mode(p1, True):
                QMessageBox.information(self, "Успех", "База данных зашифрована.")
                self.accept()
            return

        # Сценарий 2: Отключение шифрования
        if not want_enc and cur_enc:
            reply = QMessageBox.warning(self, "Расшифровка",
                "База данных будет расшифрована и сохранена в открытом виде.\nПродолжить?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No: return
            
            if self.backend.change_encryption_mode(self.current_password, False):
                # После расшифровки настраиваем пароль на вход
                if want_pass:
                    # Если ввели новый - ставим новый, иначе текущий
                    if p1:
                        if p1 != p2:
                            QMessageBox.warning(self, "Ошибка", "Пароли не совпадают")
                            self.backend.security.set_app_password(self.current_password)
                        else:
                            self.backend.security.set_app_password(p1)
                    else:
                        self.backend.security.set_app_password(self.current_password)
                else:
                    self.backend.security.remove_app_password()
                    
                QMessageBox.information(self, "Успех", "Шифрование отключено.")
                self.accept()
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось отключить шифрование.")
            return

        # Сценарий 3: Изменение настроек доступа (без изменения шифрования)
        if not want_enc and not cur_enc:
            if want_pass:
                if p1: # Ввели новый
                    if p1 != p2:
                        QMessageBox.warning(self, "Ошибка", "Пароли не совпадают")
                        return
                    self.backend.security.set_app_password(p1)
                    msg = "Пароль на вход установлен/изменен."
                elif not cur_has_pass: # Не ввели, и пароля не было
                    QMessageBox.warning(self, "Ошибка", "Введите пароль")
                    return
                else:
                    msg = "Настройки сохранены."
                
                QMessageBox.information(self, "Успех", msg)
                self.accept()
            else: # Не хотят пароль
                if cur_has_pass:
                    self.backend.security.remove_app_password()
                    QMessageBox.information(self, "Успех", "Пароль на вход удален.")
                self.accept()
            return
            
        # Сценарий 4: Смена пароля при включенном шифровании
        if want_enc and cur_enc:
            if p1:
                QMessageBox.information(self, "Инфо", "Для смены пароля шифрования сначала отключите его, затем включите снова.")
            else:
                self.accept()

class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FinanceFugue - Справка")
        self.resize(950, 650)
        self.setStyleSheet("""
            QDialog { background-color: #1A1A1A; }
            QListWidget {
                background-color: #252525;
                color: #FFFFFF;
                border: none;
                border-right: 1px solid #333333;
                font-size: 14px;
                outline: none;
            }
            QListWidget::item { padding: 15px; border-bottom: 1px solid #2D2D2D; }
            QListWidget::item:selected { background-color: #0078D7; color: white; }
            QTextBrowser {
                background-color: #1A1A1A;
                color: #DDDDDD;
                border: none;
                padding: 20px;
                font-size: 15px;
                line-height: 160%;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Навигация
        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(220)
        self.nav_list.addItem("🚀 Введение")
        self.nav_list.addItem("👤 Работа с клиентами")
        self.nav_list.addItem("📦 Управление заказами")
        self.nav_list.addItem("💰 Финансы и платежи")
        self.nav_list.addItem("📁 Менеджер файлов")
        self.nav_list.addItem("⚙️ Настройки и бэкапы")
        self.nav_list.addItem("⌨️ Горячие клавиши")
        self.nav_list.addItem("💡 Полезные советы")
        self.nav_list.addItem("📄 О программе")
        
        # Контент
        from PySide6.QtWidgets import QTextBrowser
        self.content_view = QTextBrowser()
        self.content_view.setOpenExternalLinks(True)
        
        layout.addWidget(self.nav_list)
        layout.addWidget(self.content_view)
        
        self.nav_list.currentRowChanged.connect(self.display_section)
        
        # Данные справки
        self.sections = {
            0: ("Введение", """
                <h1 style='color: #00D1FF;'>FinanceFugue</h1>
                <p>Профессиональная система управления заказами для музыкальных студий, звукорежиссеров и творческих команд.</p>
                <p>Программа позволяет вести базу клиентов, отслеживать платежи, управлять сроками выполнения работ и хранить все связанные файлы в одном месте.</p>
                <h3>Основные возможности:</h3>
                <ul>
                    <li>Учет клиентов и полная история их заказов.</li>
                    <li>Автоматический расчет долгов, авансов и общей кассы.</li>
                    <li>Умный менеджер файлов с поддержкой Drag & Drop.</li>
                    <li>Система уведомлений о приближающихся дедлайнах.</li>
                    <li>Безопасное хранение данных с возможностью резервного копирования.</li>
                </ul>
            """),
            1: ("Работа с клиентами", """
                <h2 style='color: #00D1FF;'>Управление клиентами</h2>
                <p>Клиенты — основа вашей базы данных. Вся работа строится вокруг карточек клиентов, к которым привязываются заказы и платежи.</p>
                
                <h3>Способы создания клиентов:</h3>
                <ul>
                    <li><b>Вручную:</b> Нажмите кнопку <b>'➕ Новый клиент'</b> на левой панели или используйте горячую клавишу <b>Ctrl+N</b>. Введите имя, и клиент сразу появится в списке.</li>
                    <li><b>Автоматически из папки:</b> Просто перетащите папку с именем клиента из вашего проводника в левую панель со списком клиентов. Программа сама предложит создать клиента с таким именем и импортировать содержимое папки как заказы. Это самый быстрый способ начать работу с существующими архивами.</li>
                </ul>

                <h3>Взаимодействие со списком:</h3>
                <p><b>Выбор клиента:</b> Нажмите на имя клиента, чтобы открыть его профиль в правой части окна. Там отобразится вся информация: статистика, заказы, заметки.</p>
                <p><b>Поиск:</b> Используйте поле "Поиск..." над списком, чтобы мгновенно отфильтровать клиентов по имени. Это удобно, когда база становится большой.</p>
                <p><b>Контекстное меню:</b> Нажмите <b>правой кнопкой мыши</b> на клиенте, чтобы получить доступ к быстрым действиям:</p>
                <ul>
                    <li><b>Добавить заказ:</b> Мгновенное создание нового заказа для этого клиента.</li>
                    <li><b>Настройки клиента:</b> Редактирование имени, добавление контактных данных (Email, Telegram, VK) и заметок.</li>
                    <li><b>Экспорт всех файлов (ZIP):</b> Экспорт всех файлов клиента в ZIP-архив.</li>
                    <li><b>Удаление:</b> Удаление клиента и всех связанных с ним данных.</li>
                </ul>
                <p><b>Сортировка:</b> Через контекстное меню (правая кнопка мыши на пустом месте списка) можно отсортировать клиентов по имени, дате создания новых/старых заказов или по срочности дедлайна.</p>
            """),
            2: ("Управление заказами", """
                <h2 style='color: #00D1FF;'>Карточки заказов</h2>
                <p>Карточка заказа — это центральный элемент для отслеживания конкретной работы. Здесь собрана вся финансовая и файловая информация по задаче.</p>
                <h3>Создание и редактирование</h3>
                <ul>
                    <li><b>Создание заказа:</b> Откройте профиль клиента и нажмите большую зеленую кнопку <b>'➕ добавить заказ'</b>. Заполните поля и нажмите "Создать".</li>
                    <li><b>Редактирование:</b> Большинство параметров заказа (стоимость, аванс, дата заказа и срок выполнения) можно изменить прямо в его карточке, кликнув на соответствующее поле.</li>
                    <li><b>Дополнительные действия:</b> Нажмите на иконку шестеренки (⚙️), чтобы получить доступ к дополнительным функциям:
                        <ul>
                            <li style='color: #DDDDDD;'>Изменить название услуги</li>
                            <li style='color: #DDDDDD;'>Копировать ID заказа</li>
                            <li style='color: #DDDDDD;'>Экспортировать файлы в ZIP-архив</li>
                            <li style='color: #DDDDDD;'>Дублировать заказ</li>
                            <li style='color: #DDDDDD;'>Удалить заказ</li>
                        </ul>
                    </li>
                </ul>
                <h3>Работа со статусами и сроками</h3>
                <ul>
                    <li><b>Статус выполнения:</b> Статус заказа ('В работе' / 'Завершен') меняется с помощью большого переключателя в заголовке карточки. Этот переключатель имеет умную логику:
                        <ul>
                            <li style='color: #DDDDDD;'>При <b>завершении</b> заказа с долгом, программа предложит автоматически погасить его. Вы можете согласиться, и тогда будет создан платеж на сумму долга. Либо вы можете отказаться, и заказ все равно будет помечен как "Завершен", но долг останется.</li>
                            <li style='color: #DDDDDD;'>При возврате заказа <b>в работу</b>, если последний платеж был автоматическим, программа предложит отменить его и вернуть сумму в долг. Это удобно для доработок, когда оплата уже прошла.</li>
                        </ul>
                    </li>
                    <li><b>Дедлайны:</b> Программа визуально помогает отслеживать сроки. Дата дедлайна подсвечивается разными цветами в зависимости от срочности:
                        <ul>
                            <li style='color: #28A745;'><b>Зеленый:</b> В запасе больше 5 дней.</li>
                            <li style='color: #FFA500;'><b>Желтый:</b> Осталось меньше 5 дней.</li>
                            <li style='color: #FF4B2B;'><b>Красный:</b> Срок истекает через 3 дня или уже прошел.</li>
                        </ul>
                    </li>
                </ul>
            """),
            3: ("Финансы и платежи", """
                <h2 style='color: #00D1FF;'>Финансовый учет</h2>
                <p>Программа автоматически ведет учет всех финансов по каждому заказу и клиенту, а также отображает общую статистику в дашборде. Все расчеты происходят в реальном времени по формуле: <b>Долг = Стоимость − Сумма всех платежей</b>.</p>
                
                <h3>Способы управления финансами:</h3>
                <ul>
                    <li><b>Тумблер статуса ('НЕ ВЫПОЛНЕН' / 'ВЫПОЛНЕН'):</b> Этот переключатель в заголовке карточки заказа напрямую связан с финансами. При переводе заказа в статус <b>'ВЫПОЛНЕН'</b>, если имеется долг, программа предложит автоматически его погасить. И наоборот, при возврате заказа в работу, если последний платеж был автоматическим, система предложит его отменить.</li>
                    <li><b>Ручное редактирование:</b> Вы можете напрямую изменять значения в полях <b>'СТОИМОСТЬ'</b>, <b>'АВАНС'</b> и <b>'ДОЛГ'</b>. Программа обладает умной логикой:
                        <ul>
                           <li style='color: #DDDDDD;'>При уменьшении <b>стоимости</b> ниже уже оплаченной суммы, программа предложит оформить возврат.</li>
                           <li style='color: #DDDDDD;'>При изменении <b>долга</b>, будет автоматически создана "корректировка" для выравнивания баланса.</li>
                        </ul>
                    </li>
                    <li><b>Добавление платежа:</b> Нажмите кнопку <b>'✚ добавить'</b>, чтобы открыть диалог внесения платежа. Это основной способ фиксации всех финансовых операций.</li>
                    <li><b>Быстрая оплата:</b> Используйте кнопку-переключатель <b>'❌ НЕ ОПЛАЧЕНО' / '✅ ОПЛАЧЕНО'</b>. При нажатии на '❌ НЕ ОПЛАЧЕНО' программа предложит автоматически создать платеж на всю сумму долга. При выключении статуса '✅ ОПЛАЧЕНО' программа предложит отменить последнюю транзакцию.</li>
                </ul>

                <h3>Типы платежей:</h3>
                <p>При добавлении платежа через диалог (кнопка <b>'✚ добавить'</b>) вы можете выбрать его тип:</p>
                <ol>
                    <li><b>Платеж:</b> Стандартная оплата за работу. Уменьшает долг.</li>
                    <li><b>Аванс:</b> Предоплата. Также уменьшает долг и дополнительно учитывается в общей статистике авансов.</li>
                    <li><b>Корректировка:</b> Специальный тип для нетипичных операций. Включает в себя подтипы для точного учета:
                         <ul>
                           <li style='color: #DDDDDD;'><b>Возврат средств:</b> Для оформления возврата клиенту (сумма будет отрицательной).</li>
                           <li style='color: #DDDDDD;'><b>Скидка / Списание:</b> Уменьшает долг без изменения общей стоимости заказа (сумма будет положительной).</li>
                           <li style='color: #DDDDDD;'><b>Техническая правка (+/-):</b> Для ручной корректировки баланса в любую сторону.</li>
                        </ul>
                    </li>
                </ol>
                <p>Вся история платежей по заказу доступна по кнопке <b>'📋 история'</b>. В этом окне можно просмотреть детали каждой транзакции или удалить ее.</p>
            """),
            4: ("Менеджер файлов", """
                <h2 style='color: #00D1FF;'>Работа с файлами</h2>
                <p>FinanceFugue предлагает гибкие инструменты для управления файлами проектов.</p>
                <h3>Режимы хранения:</h3>
                <p>Способ хранения файлов выбирается при первом запуске программы, но его можно изменить в настройках при переносе базы данных.</p>
                <ul>
                    <li><b>Ссылки (рекомендуется для начала):</b> Программа просто запоминает путь к вашим файлам. Это экономит место, так как не создаются дубликаты. Минус: если вы переместите или удалите оригинальный файл, программа потеряет к нему доступ.</li>
                    <li><b>Копии в базе данных:</b> Программа создает копию каждого файла и сохраняет ее в специальной папке рядом с базой данных. Это самый надежный способ, гарантирующий, что файлы никогда не потеряются. Идеально подходит для переноса базы на другой компьютер.</li>
                </ul>
                <h3>Способы добавления файлов:</h3>
                <ul>
                    <li><b>Перетаскивание (Drag & Drop):</b> Просто перетащите файлы или папки из проводника прямо на карточку заказа.</li>
                    <li><b>Кнопка "Добавить файлы":</b> Внутри карточки заказа, в разделе файлов, есть кнопка для стандартного диалога выбора файлов.</li>
                    <li><b>Глобальный менеджер:</b> Откройте его кнопкой <b>'📁 менеджер файлов'</b> на левой панели. Это мощный инструмент, который показывает дерево всех клиентов, заказов и файлов. Вы можете перетаскивать файлы прямо на имя клиента или заказа в этом окне.</li>
                </ul>
            """),
            5: ("Настройки и бэкапы", """
                <h2 style='color: #00D1FF;'>Безопасность данных</h2>
                <p><b>База данных:</b> Все данные хранятся в одном JSON файле. Вы можете изменить его расположение в настройках (например, перенести в облачную папку Dropbox/Google Drive для синхронизации).</p>
                <p><b>Резервные копии:</b>
                    <ul>
                        <li><b>JSON Экспорт:</b> Только база данных (клиенты, заказы, платежи).</li>
                        <li><b>Полный ZIP бэкап:</b> База данных + ВСЕ прикрепленные файлы в одном архиве.</li>
                    </ul>
                </p>
                <p>Программа автоматически делает бэкапы файлов конфигурации при каждом выходе.</p>
            """),
            6: ("Горячие клавиши", """
                <h2 style='color: #00D1FF;'>Клавиатурные сокращения</h2>
                <p>Используйте горячие клавиши для ускорения работы:</p>
                <table border='0' cellpadding='10' width='100%'>
                    <tr><td width='30%'><b style='color: #00D1FF;'>Ctrl + N</b></td><td>Создать нового клиента</td></tr>
                    <tr><td><b style='color: #00D1FF;'>Ctrl + S</b></td><td>Принудительно сохранить базу данных</td></tr>
                    <tr><td><b style='color: #00D1FF;'>Ctrl + F</b></td><td>Установить фокус на поле поиска клиентов</td></tr>
                    <tr><td><b style='color: #00D1FF;'>Ctrl + O</b></td><td>Открыть глобальный менеджер файлов</td></tr>
                    <tr><td><b style='color: #00D1FF;'>Ctrl + Shift + S</b></td><td>Открыть окно настроек</td></tr>
                    <tr><td><b style='color: #00D1FF;'>Delete</b></td><td>Удалить выбранного клиента (из списка)</td></tr>
                    <tr><td><b style='color: #00D1FF;'>F5</b></td><td>Обновить список клиентов</td></tr>
                    <tr><td><b style='color: #00D1FF;'>Ctrl + Q</b></td><td>Выход из программы</td></tr>
                </table>
                <p style='margin-top: 20px;'><i>Совет: Многие действия также доступны через правую кнопку мыши в списках и карточках.</i></p>
            """),
             7: ("Полезные советы", """
                <h2 style='color: #00D1FF;'>💡 Полезные советы</h2>
                <ul>
                    <li><b>Drag & Drop — ваш лучший друг.</b> Вы можете перетаскивать не только файлы в карточку заказа, но и целые папки в список клиентов для автоматического создания и импорта. Это экономит массу времени.</li>
                    <li><b>Используйте облачные папки для базы данных.</b> При первом запуске или в настройках укажите папку, которая синхронизируется с облаком (Google Drive, Dropbox, Яндекс.Диск). Так вы получите доступ к своей базе с разных компьютеров и защитите данные от потери.</li>
                    <li><b>Сортировка по дедлайнам.</b> Нажмите правой кнопкой мыши на списке клиентов и выберите "Сортировка" -> "Срочные". Так вы всегда будете видеть, какие заказы требуют внимания в первую очередь.</li>
                    <li><b>Уникальный ID заказа.</b> Хотя ID может показаться технической информацией, его удобно использовать в названиях файлов или папок при экспорте, чтобы точно знать, к какому заказу они относятся, особенно если у вас много однотипных проектов.</li>
                    <li><b>Двойной клик в менеджере файлов.</b> В глобальном менеджере файлов (кнопка на главной панели) вы можете дважды щелкнуть по любому файлу или папке, чтобы мгновенно открыть их в вашей операционной системе.</li>
                    <li><b>Заметки к клиенту.</b> В настройках клиента есть поле "Заметка". Используйте его для важной информации, которая не относится к конкретному заказу: общие предпочтения клиента, история сотрудничества, важные напоминания.</li>
                </ul>
            """),
            8: ("О программе", """
                <h2 style='color: #00D1FF;'>О программе</h2>
                <p><b>KVF SOFT.</b> Авторские права - Kirill Fandeev.</p>
                <p>Написать автору: <a href='mailto:KVF_SOFT@mail.ru' style='color: #00D1FF;'>KVF_SOFT@mail.ru</a></p>
            """)
        }
        
        self.nav_list.setCurrentRow(0)
        self.display_section(0)
        
        animate_dialog_open(self)
        
    def display_section(self, index):
        if index in self.sections:
            title, html = self.sections[index]
            self.content_view.setHtml(html)
            
    def select_section(self, section_name):
        """Метод для внешнего открытия конкретного раздела"""
        for i in range(self.nav_list.count()):
            if section_name in self.nav_list.item(i).text():
                self.nav_list.setCurrentRow(i)
                break

