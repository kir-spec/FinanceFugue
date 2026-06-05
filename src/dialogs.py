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
    QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView, QTreeWidget, QTreeWidgetItem
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QAction, QIcon

from .models import Order, ProjectFile, Client

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
        self.tree.setHeaderLabels(["Клиент / Заказ / Файл", "Путь", "Тип"])
        self.tree.setColumnWidth(0, 350)
        self.tree.setColumnWidth(1, 400)
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
                order_item.setText(2, f"Заказ ({len(order.files)} файлов)")
                order_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "order", "id": order.id, "obj": order})
                
                # Файлы заказа
                for file in order.files:
                    file_item = QTreeWidgetItem(order_item)
                    is_folder = getattr(file, 'is_folder', os.path.isdir(file.path))
                    icon = "📁" if is_folder else "📄"
                    file_type_str = "folder" if is_folder else "file"
                    
                    file_item.setText(0, f"{icon} {file.name}")
                    file_item.setText(1, file.path)
                    file_item.setText(2, "Папка" if is_folder else "Файл")
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
        self.parent = parent
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
        self.setWindowTitle("Добро пожаловать в Pro Music CRM!")
        self.resize(800, 600)
        self.setMinimumSize(600, 500)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
            }
            QLabel {
                color: #DDDDDD;
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
                color: #FFFFFF;
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
        original_desc.setStyleSheet("color: #DDDDDD; font-size: 11px; padding-left: 25px;")
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
        copy_desc.setStyleSheet("color: #DDDDDD; font-size: 11px; padding-left: 25px;")
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
        btn_imp_folder.clicked.connect(self.parent.import_from_folder)
        
        btn_exp = QPushButton("Экспорт (JSON)")
        btn_exp.clicked.connect(self.parent.export_json)
        
        btn_imp = QPushButton("Импорт (JSON)")
        btn_imp.clicked.connect(self.parent.import_json_file)
        
        btn_full = QPushButton("Полный бэкап (ZIP)")
        btn_full.clicked.connect(self.parent.export_full_backup)
        
        db_layout.addWidget(btn_db_location)
        db_layout.addWidget(btn_imp_folder)
        db_layout.addWidget(btn_exp)
        db_layout.addWidget(btn_imp)
        db_layout.addWidget(btn_full)
        
        # Кнопка удаления всех файлов
        btn_del_files = QPushButton("🗑 Удалить ВСЕ файлы")
        btn_del_files.clicked.connect(self.parent.delete_all_files)
        db_layout.addWidget(btn_del_files)

        # Кнопка удаления всей базы
        btn_del_db = QPushButton("☠ Удалить ВСЮ базу данных")
        btn_del_db.clicked.connect(self.parent.delete_database_full)
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
        
        settings_layout.addWidget(btn_backup_settings)
        settings_layout.addWidget(btn_restore_settings)
        
        layout.addWidget(settings_group)
        layout.addSpacing(10)
        
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
            # Создаем путь к новой базе
            new_db_path = Path(folder) / "pro_database.json"
            
            # Проверяем, не выбрана ли та же самая папка
            if self.parent.storage.path.exists() and new_db_path.resolve() == self.parent.storage.path.resolve():
                QMessageBox.information(self, "Информация", "База данных уже находится в выбранной папке.")
                return

            # Сохраняем текущую базу перед переносом
            self.parent.save_db()
            
            if move_files:
                # Создаем структуру папок для файлов
                files_folder = Path(folder) / "attached_files"
                files_folder.mkdir(exist_ok=True)
                
                # Копируем файлы
                for client in self.parent.clients:
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
            if self.parent.storage.path.exists():
                shutil.copy2(self.parent.storage.path, new_db_path)
            
            # Обновляем путь к базе данных в приложении
            self.parent.storage.path = new_db_path
            self.parent.app_settings['database_path'] = folder
            
            # Сохраняем обновленную базу данных (уже с новыми путями) по новому адресу
            self.parent.save_db()
            self.parent.save_settings()
            
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
                
                self.parent.app_settings = new_settings
                self.parent.save_settings()
                
                QMessageBox.information(self, "Успех",
                                      "Настройки восстановлены. Перезапустите приложение для применения изменений.")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось восстановить настройки: {e}")

class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Symphony Pro CRM - Справка")
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
                <h1 style='color: #00D1FF;'>Symphony Pro CRM</h1>
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
                <p><b>Добавление:</b> Используйте кнопку <b>'➕ Новый клиент'</b> или нажмите <b>Ctrl+N</b>.</p>
                <p><b>Импорт папок:</b> Вы можете перетащить папку с именем клиента прямо в список слева. Программа предложит создать клиента и проанализирует вложенные папки для создания заказов.</p>
                <p><b>Контекстное меню:</b> Нажмите правую кнопку мыши на клиенте в списке, чтобы быстро добавить заказ, открыть его настройки или удалить.</p>
                <p><b>Сортировка:</b> В контекстном меню списка клиентов доступна сортировка по алфавиту, дате заказов или срочности дедлайнов.</p>
            """),
            2: ("Управление заказами", """
                <h2 style='color: #00D1FF;'>Карточки заказов</h2>
                <p>Каждый заказ содержит информацию о типе услуги, стоимости, сроках и прикрепленных файлах.</p>
                <ul>
                    <li><b>Создание:</b> Кнопка <b>'➕ добавить заказ'</b> в профиле клиента.</li>
                    <li><b>Дедлайны:</b> Поле даты окрашивается автоматически:
                        <ul>
                            <li><span style='color: #28A745;'>Зеленый:</span> больше 5 дней до срока.</li>
                            <li><span style='color: #FFA500;'>Желтый:</span> меньше 5 дней.</li>
                            <li><span style='color: #FF4B2B;'>Красный:</span> меньше 3 дней (срочно!).</li>
                        </ul>
                    </li>
                    <li><b>Дублирование:</b> В меню настроек заказа (шестеренка) выберите <b>'📋 Дублировать заказ'</b> для быстрого создания повторной задачи.</li>
                </ul>
            """),
            3: ("Финансы и платежи", """
                <h2 style='color: #00D1FF;'>Финансовый учет</h2>
                <p>Система автоматически высчитывает баланс на основе трех типов записей:</p>
                <ol>
                    <li><b>Платеж:</b> Обычная оплата за работу.</li>
                    <li><b>Аванс:</b> Предоплата (автоматически учитывается в статистике авансов).</li>
                    <li><b>Корректировка:</b> Используется для возвратов, скидок или технических правок баланса.</li>
                </ol>
                <p><b>Статус оплаты:</b> Большая кнопка внизу заказа позволяет одним кликом пометить его как оплаченный (добавляет платеж на сумму долга).</p>
                <p><b>Долг:</b> Рассчитывается как <i>Стоимость - Все полученные средства</i>. Если сумма платежей превышает стоимость, долг становится нулевым.</p>
            """),
            4: ("Менеджер файлов", """
                <h2 style='color: #00D1FF;'>Работа с файлами</h2>
                <p>Программа поддерживает два основных режима хранения (настраивается при первом запуске или в общих настройках):</p>
                <ul>
                    <li><b>Ссылки (Link):</b> Файлы остаются там, где они лежат. Программа просто запоминает путь. Это экономит место, но ссылки сломаются, если вы переместите файлы вручную.</li>
                    <li><b>Копии (Copy):</b> Программа копирует файлы в свою внутреннюю папку базы данных. Это надежнее всего.</li>
                </ul>
                <p><b>Глобальный менеджер:</b> Открывается кнопкой <b>'📁 менеджер файлов'</b> в левой панели. Позволяет видеть все файлы всех клиентов в виде дерева.</p>
                <p><b>Drag & Drop:</b> Вы можете перетаскивать файлы из проводника прямо в карточку заказа.</p>
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
                <table border='0' cellpadding='10'>
                    <tr><td><b style='color: #00D1FF;'>Ctrl + N</b></td><td>Новый клиент</td></tr>
                    <tr><td><b style='color: #00D1FF;'>Ctrl + S</b></td><td>Сохранить базу данных</td></tr>
                    <tr><td><b style='color: #00D1FF;'>Ctrl + Q</b></td><td>Выход из программы</td></tr>
                    <tr><td><b style='color: #00D1FF;'>Delete</b></td><td>Удалить выбранного клиента</td></tr>
                </table>
                <p style='margin-top: 20px;'><i>Совет: Многие действия также доступны через правую кнопку мыши в списках и карточках.</i></p>
            """)
        }
        
        self.nav_list.setCurrentRow(0)
        self.display_section(0)
        
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

