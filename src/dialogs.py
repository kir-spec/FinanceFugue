
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
    QLineEdit, QFileDialog, QCheckBox, QGroupBox, QRadioButton, QButtonGroup,
    QFormLayout, QTextEdit, QDialogButtonBox, QInputDialog, QDateEdit, QComboBox,
    QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView, QTreeWidget, QTreeWidgetItem,
    QGraphicsDropShadowEffect, QTextBrowser, QWizard, QWizardPage
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QSequentialAnimationGroup, QPoint, Signal
from PySide6.QtGui import QColor, QAction, QIcon, QFont
from .widgets import ToggleSwitch, ClickableCardWidget, HelpButtonMixin # Импортируем новые виджеты

# --- ADVANCED DRAG-AND-DROP IMPORT WIZARD ---

class AdvancedImportDialog(QWizard, HelpButtonMixin):
    """
    A multi-page wizard for interactively importing a folder structure.
    Allows creating clients from root folders, orders from subfolders,
    and attaching files.
    """
    def __init__(self, dropped_paths, parent_app, parent=None):
        super().__init__(parent)
        self.parent_app = parent_app
        self.dropped_paths = dropped_paths

        self.setWindowTitle("Мастер импорта")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.init_help_button(parent_app, "import_wizard")
        self.setFixedSize(800, 600)

        # Pages will be added here
        self.addPage(IntroPage(self.dropped_paths, self))
        self.client_page = ClientCreationPage(self)
        self.addPage(self.client_page)
        self.order_page = OrderCreationPage(self)
        self.addPage(self.order_page)
        self.addPage(SummaryPage(self))

        self.currentIdChanged.connect(self.on_page_changed)
        # Apply custom styling if needed
        self.setStyleSheet("QWizard { background-color: #1E1E1E; }")


    def on_page_changed(self, page_id):
        """Handle logic when moving between pages."""
        pass

    def accept(self):
        """Execute the import process when Finished is clicked."""
        self.process_import()
        super().accept()

    def process_import(self):
        """Core logic to create clients/orders/files based on wizard selection."""
        # 1. Gather options
        create_new_clients = self.client_page.rb_create_new.isChecked()
        target_client = self.client_page.existing_client_combo.currentData() if not create_new_clients else None
        
        create_orders_from_subs = self.order_page.cb_create_orders.isChecked()
        
        created_count = 0
        
        # 2. Iterate through dropped paths (root level)
        for path in self.dropped_paths:
            if not os.path.exists(path): continue
            
            is_dir = os.path.isdir(path)
            base_name = os.path.basename(path)
            
            # --- CLIENT LEVEL ---
            client = None
            if is_dir and create_new_clients:
                # Check for existing client with same name to avoid duplicates?
                # For now, just create new one or find existing
                existing = next((c for c in self.parent_app.clients if c.name == base_name), None)
                if existing:
                    client = existing
                else:
                    client = Client(id=str(uuid.uuid4()), name=base_name)
                    self.parent_app.clients.append(client)
                    created_count += 1
            elif target_client:
                client = target_client
            
            if not client:
                # Should not happen if logic is correct, but skip if no client context
                continue
                
            # --- ORDER/FILE LEVEL ---
            if is_dir:
                # Processing contents of the root folder
                try:
                    for entry in os.listdir(path):
                        entry_path = os.path.join(path, entry)
                        entry_name = os.path.basename(entry_path)
                        entry_is_dir = os.path.isdir(entry_path)
                        
                        if entry_is_dir and create_orders_from_subs:
                            # Create Order from subfolder
                            order = Order(
                                id=str(uuid.uuid4()),
                                service_type=entry_name,
                                created_at=datetime.now().strftime("%d.%m.%Y %H:%M"),
                                deadline=datetime.now().strftime("%d.%m.%Y"),
                                status="В работе",
                                files=[]
                            )
                            client.orders.append(order)
                            
                            # Add files inside this subfolder to the order
                            for sub_entry in os.listdir(entry_path):
                                sub_path = os.path.join(entry_path, sub_entry)
                                self._add_file_to_order(order, sub_path)
                                
                        else:
                            # It's a file in root, or folder but we don't want orders from folders
                            # Add to a default "General" order or ask user?
                            # For simplicity, create a "General Import" order if none exists, or use the first one
                            order = self._get_or_create_general_order(client)
                            self._add_file_to_order(order, entry_path)
                            
                except Exception as e:
                    logger.error(f"Error processing folder {path}: {e}")
            else:
                # It's a file at root level
                order = self._get_or_create_general_order(client)
                self._add_file_to_order(order, path)

        self.parent_app.save_db()
        # Refresh is handled by caller

    def _get_or_create_general_order(self, client):
        """Helper to find a suitable order for loose files."""
        if client.orders:
            return client.orders[0] # Use first available
        
        # Create default
        order = Order(
            id=str(uuid.uuid4()),
            service_type="Общий заказ",
            created_at=datetime.now().strftime("%d.%m.%Y %H:%M"),
            status="В работе",
            files=[]
        )
        client.orders.append(order)
        return order

    def _add_file_to_order(self, order, path):
        """Helper to attach file/folder to order."""
        # TODO: Implement storage logic (copy vs link) based on settings
        # For now, using Link mode as default for simplicity in this wizard
        is_dir = os.path.isdir(path)
        
        # Check duplicates
        if any(f.path == path for f in order.files):
            return

        order.files.append(ProjectFile(
            path=path,
            name=os.path.basename(path),
            is_finished=False,
            is_folder=is_dir
        ))

class IntroPage(QWizardPage):
    """First page of the wizard: shows the detected file structure."""
    def __init__(self, paths, parent=None):
        super().__init__(parent)
        self.setTitle("Шаг 1: Анализ структуры")
        self.setSubTitle("Программа проанализировала перетаскиваемые файлы и папки. Проверьте структуру и отметьте элементы для импорта.")

        layout = QVBoxLayout(self)
        header_layout = QHBoxLayout()
        header_layout.addStretch()
        header_layout.addWidget(self.help_btn)
        layout.addLayout(header_layout)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Элемент", "Тип", "Путь"])
        self.tree.setColumnWidth(0, 300)
        self.tree.setColumnWidth(1, 100)
        layout.addWidget(self.tree)

        self.populate_tree(paths)

    def populate_tree(self, paths):
        """Recursively populates the tree widget with files and folders."""
        for path in paths:
            if os.path.exists(path):
                self._add_path_to_tree(path, self.tree)

    def _add_path_to_tree(self, path, parent_item):
        name = os.path.basename(path)
        is_dir = os.path.isdir(path)

        item = QTreeWidgetItem(parent_item)
        item.setText(0, name)
        item.setText(1, "Папка" if is_dir else "Файл")
        item.setText(2, path)
        item.setCheckState(0, Qt.CheckState.Checked)
        item.setExpanded(True)

        if is_dir:
            try:
                # Add children recursively
                for entry in sorted(os.listdir(path)):
                    self._add_path_to_tree(os.path.join(path, entry), item)
            except OSError as e:
                # Add a disabled item to show there was an error
                error_item = QTreeWidgetItem(item)
                error_item.setText(0, f"Ошибка доступа: {e.strerror}")
                error_item.setDisabled(True)

class ClientCreationPage(QWizardPage):
    """Page for selecting/creating clients from root folders."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Шаг 2: Клиенты")
        self.setSubTitle("Как обработать папки верхнего уровня?")
        
        layout = QVBoxLayout(self)
        
        self.rb_create_new = QRadioButton("Создать новых клиентов из имен папок")
        self.rb_create_new.setChecked(True)
        self.rb_bind_existing = QRadioButton("Привязать всё к существующему клиенту")
        
        layout.addWidget(self.rb_create_new)
        layout.addWidget(self.rb_bind_existing)
        
        # Existing client selection
        self.existing_client_combo = QComboBox()
        self.existing_client_combo.setEnabled(False)
        layout.addWidget(QLabel("Существующий клиент:"))
        layout.addWidget(self.existing_client_combo)
        
        self.rb_bind_existing.toggled.connect(self.existing_client_combo.setEnabled)
        
        # Populate combo
        if parent and hasattr(parent, 'parent_app'):
            for client in parent.parent_app.clients:
                self.existing_client_combo.addItem(client.name, client)

    def initializePage(self):
        # Could update list if needed
        pass

class OrderCreationPage(QWizardPage):
    """Page for configuring order creation from subfolders."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Шаг 3: Заказы")
        self.setSubTitle("Как обработать вложенные папки?")
        
        layout = QVBoxLayout(self)
        
        self.cb_create_orders = QCheckBox("Создать отдельные заказы из подпапок")
        self.cb_create_orders.setChecked(True)
        layout.addWidget(self.cb_create_orders)
        
        self.cb_files_to_orders = QCheckBox("Файлы в корне папок привязывать к заказам")
        self.cb_files_to_orders.setChecked(True)
        layout.addWidget(self.cb_files_to_orders)

class SummaryPage(QWizardPage):
    """Final confirmation page."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Шаг 4: Подтверждение")
        self.setSubTitle("Проверьте настройки перед импортом.")
        
        layout = QVBoxLayout(self)
        self.summary_text = QTextBrowser()
        layout.addWidget(self.summary_text)
        
    def initializePage(self):
        # Generate summary based on previous pages
        wizard = self.wizard()
        summary = "<b>План импорта:</b><br><ul>"
        
        client_page = wizard.page(wizard.pageIds()[1]) # Assuming index 1
        order_page = wizard.page(wizard.pageIds()[2])  # Assuming index 2
        
        if client_page.rb_create_new.isChecked():
            summary += "<li>Создание <b>новых клиентов</b> из папок верхнего уровня.</li>"
        else:
            client_name = client_page.existing_client_combo.currentText()
            summary += f"<li>Привязка к клиенту: <b>{client_name}</b>.</li>"
            
        if order_page.cb_create_orders.isChecked():
            summary += "<li>Создание <b>заказов</b> из подпапок.</li>"
        else:
            summary += "<li>Подпапки будут добавлены как файлы/папки к клиенту (или одному заказу).</li>"
            
        summary += "</ul>"
        self.summary_text.setHtml(summary)

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
class StatsDetailDialog(QDialog, HelpButtonMixin):
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
        
        # Инциализация кнопки справки
        self.init_help_button(parent, "stats_detail")

        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Детальная история операций"))
        header_layout.addStretch()
        header_layout.addWidget(self.help_btn)
        layout.addLayout(header_layout)

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
class ClientSelectionDialog(QDialog, HelpButtonMixin):
    def __init__(self, parent_app, parent=None):
        super().__init__(parent)
        self.parent_app = parent_app
        self.selected_client = None
        self.setWindowTitle("Выбор клиента")
        self.init_help_button(parent_app, "selection_dialog")
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
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Выберите клиента для привязки файлов:"))
        header_layout.addStretch()
        header_layout.addWidget(self.help_btn)
        layout.addLayout(header_layout)
        
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
class OrderSelectionDialog(QDialog, HelpButtonMixin):
    def __init__(self, client, parent=None):
        super().__init__(parent)
        self.client = client
        self.selected_order = None
        self.setWindowTitle("Выбор заказа")
        self.init_help_button(parent, "selection_dialog")
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
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel(f"Клиент: {client.name}"))
        header_layout.addStretch()
        header_layout.addWidget(self.help_btn)
        layout.addLayout(header_layout)
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
        
        layout.addWidget(btn_box)
        
        animate_dialog_open(self)

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
            # или просто обновить список, а сохранение произойдет позже в GlobalFileManagerDialog
            
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
class GlobalFileManagerDialog(QDialog, HelpButtonMixin):
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
        
        # Инциализация кнопки справки
        self.init_help_button(parent_app, "file_manager")

        header_layout = QHBoxLayout()
        header_title = QLabel("Менеджер файлов всех проектов")
        header_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #00D1FF;")
        header_layout.addWidget(header_title)
        header_layout.addStretch()
        header_layout.addWidget(self.help_btn)
        layout.addLayout(header_layout)

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
        

        btn_layout.addWidget(refresh_btn)
        btn_layout.addWidget(del_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
        self.load_data()
        
        animate_dialog_open(self)

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

        paths = [url.toLocalFile() for url in urls]
        has_folders = any(os.path.isdir(p) for p in paths)

        if has_folders:
            dialog = AdvancedImportDialog(paths, self.parent_app, self)
            dialog.exec()
            # После закрытия диалога импорта обновляем данные
            self.load_data()
            self.parent_app.refresh_list()
            return
            
        # --- СТАРАЯ ЛОГИКА ДЛЯ ФАЙЛОВ ---
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
            dialog = OrderSelectionDialog(target_client, self)
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_order:
                target_order = dialog.selected_order
            else:
                return

        # Теперь добавляем файлы в target_order
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

            # Добавляем файл в заказ
            if not any(f.path == final_path for f in self.order.files):
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

    def eventFilter(self, obj, event):
        """Перенаправляет drag&drop событий от таблицы к диалогу"""
        if event.type() == event.Type.DragEnter:
            self.dragEnterEvent(event)
            return True
        elif event.type() == event.Type.Drop:
            self.dropEvent(event)
            return True
        return super().eventFilter(obj, event)

# --- ДИАЛОГ ИМПОРТА DRAG-AND-DROP ---
class DragDropImportDialog(QDialog, HelpButtonMixin):
    def __init__(self, dropped_paths, parent=None):
        super().__init__(parent)
        self.dropped_paths = dropped_paths
        self.import_data = []
        self.setWindowTitle("Импорт файлов и папок")
        self.init_help_button(parent, "import_wizard")
        self.resize(900, 650)
        self.setMinimumWidth(800)
        
        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; }
            QLabel { color: #FFFFFF; font-size: 12px; }
            QCheckBox { color: #DDDDDD; font-size: 11px; }
            QCheckBox::indicator { width: 16px; height: 16px; }
            QCheckBox::indicator:checked { background-color: #28A745; border: 1px solid #28A745; }
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #3D3D3D; }
            QPushButton:pressed { background-color: #4D4D4D; }
            QTreeWidget {
                background-color: #252525;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                font-size: 12px;
            }
            QTreeWidget::item { padding: 4px; }
            QTreeWidget::item:selected { background-color: #0078D7; }
            QTreeWidget::item:hover { background-color: #333333; }
            QGroupBox {
                color: #00D1FF;
                border: 1px solid #3D3D3D;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
                font-weight: bold;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        header_layout = QHBoxLayout()
        header = QLabel("Выберите элементы для импорта и действие:")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #00D1FF; padding: 5px;")
        header_layout.addWidget(header)
        header_layout.addStretch()
        header_layout.addWidget(self.help_btn)
        layout.addLayout(header_layout)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Имя", "Тип", "Путь"])
        self.tree.setColumnWidth(0, 250)
        self.tree.setColumnWidth(1, 80)
        self.tree.setAlternatingRowColors(True)
        
        left_layout.addWidget(QLabel("Структура файлов:"))
        left_layout.addWidget(self.tree)
        
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        actions_group = QGroupBox("Действие")
        actions_layout = QVBoxLayout(actions_group)
        
        self.rb_create_structure = QRadioButton("Создать структуру клиентов и заказов")
        self.rb_create_structure.setChecked(True)
        self.rb_create_structure.setStyleSheet("color: #FFFFFF;")
        
        self.rb_add_to_existing = QRadioButton("Добавить к существующему клиенту/заказу")
        self.rb_add_to_existing.setStyleSheet("color: #FFFFFF;")
        
        actions_layout.addWidget(self.rb_create_structure)
        actions_layout.addWidget(self.rb_add_to_existing)
        
        self.action_group = QButtonGroup(self)
        self.action_group.addButton(self.rb_create_structure)
        self.action_group.addButton(self.rb_add_to_existing)
        self.action_group.buttonClicked.connect(self.on_action_changed)
        
        right_layout.addWidget(actions_group)
        
        self.structure_group = QGroupBox("Настройки структуры")
        structure_layout = QVBoxLayout(self.structure_group)
        
        self.cb_create_clients = QCheckBox("Создать карточки клиентов из папок верхнего уровня")
        self.cb_create_clients.setChecked(True)
        
        self.cb_create_orders = QCheckBox("Создать карточки заказов из подпапок")
        self.cb_create_orders.setChecked(True)
        
        self.cb_include_files = QCheckBox("Включить файлы в заказы")
        self.cb_include_files.setChecked(True)
        
        structure_layout.addWidget(self.cb_create_clients)
        structure_layout.addWidget(self.cb_create_orders)
        structure_layout.addWidget(self.cb_include_files)
        
        right_layout.addWidget(self.structure_group)
        
        self.info_label = QLabel("Выберите элементы в дереве...")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #888888; font-style: italic; padding: 10px; background-color: #252525; border-radius: 4px;")
        right_layout.addWidget(self.info_label)
        
        right_layout.addStretch()
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        
        layout.addWidget(splitter, 1)
        
        btn_layout = QHBoxLayout()
        
        btn_expand = QPushButton("📂 Развернуть всё")
        btn_expand.clicked.connect(self.tree.expandAll)
        
        btn_collapse = QPushButton("📁 Свернуть всё")
        btn_collapse.clicked.connect(self.tree.collapseAll)
        
        btn_layout.addWidget(btn_expand)
        btn_layout.addWidget(btn_collapse)
        btn_layout.addStretch()
        
        self.btn_import = QPushButton("✅ Импортировать")
        self.btn_import.setStyleSheet("background-color: #28A745; font-weight: bold;")
        self.btn_import.clicked.connect(self.accept)
        self.btn_import.setEnabled(False)
        
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_import)
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)
        
        self.populate_tree()
        self.update_info()
        
        animate_dialog_open(self)
    
    def populate_tree(self):
        self.tree.clear()
        for path in self.dropped_paths:
            if os.path.exists(path):
                self.add_item_to_tree(path, self.tree)
        
        for i in range(self.tree.topLevelItemCount()):
            root_item = self.tree.topLevelItem(i)
            root_item.setExpanded(True)
            for j in range(root_item.childCount()):
                root_item.child(j).setExpanded(True)
    
    def add_item_to_tree(self, path, parent_item):
        name = os.path.basename(path)
        is_dir = os.path.isdir(path)
        
        item = QTreeWidgetItem(parent_item)
        item.setText(0, name)
        item.setText(1, "Папка" if is_dir else "Файл")
        item.setText(2, path)
        item.setData(0, Qt.ItemDataRole.UserRole, {
            'path': path,
            'is_dir': is_dir,
            'name': name
        })
        
        item.setCheckState(0, Qt.CheckState.Checked)
        
        if is_dir:
            try:
                for entry in sorted(os.listdir(path)):
                    entry_path = os.path.join(path, entry)
                    self.add_item_to_tree(entry_path, item)
            except PermissionError:
                pass
    
    def on_action_changed(self):
        if self.rb_create_structure.isChecked():
            self.structure_group.setEnabled(True)
            self.info_label.setText("Выберите папки для создания клиентов и заказов. Подпапки станут заказами.")
        else:
            self.structure_group.setEnabled(False)
            self.info_label.setText("Выберите файлы для добавления к существующему клиенту/заказу.")
        self.update_info()
    
    def update_info(self):
        selected_items = self.get_selected_items()
        
        if not selected_items:
            self.info_label.setText("Ничего не выбрано")
            self.btn_import.setEnabled(False)
            return
        
        folders = sum(1 for item in selected_items if item['is_dir'])
        
        if not selected_items:
            self.info_label.setText("Ничего не выбрано")
            self.btn_import.setEnabled(False)
            return
        
        folders = sum(1 for item in selected_items if item['is_dir'])
        files = len(selected_items) - folders
        
        if self.rb_create_structure.isChecked():
            clients_count = sum(1 for item in selected_items if item['is_dir'] and self.cb_create_clients.isChecked())
            self.info_label.setText(f"Выбрано: {folders} папок, {files} файлов\nБудет создано клиентов: {clients_count}")
        else:
            self.info_label.setText(f"Выбрано для добавления: {folders} папок, {files} файлов")
        
        self.btn_import.setEnabled(True)
    
    def get_selected_items(self):
        selected = []
        
        def collect_items(item):
            if item.checkState(0) == Qt.CheckState.Checked:
                data = item.data(0, Qt.ItemDataRole.UserRole)
                if data:
                    selected.append(data)
            
            for i in range(item.childCount()):
                collect_items(item.child(i))
        
        for i in range(self.tree.topLevelItemCount()):
            collect_items(self.tree.topLevelItem(i))
        
        return selected
    
    def get_import_data(self):
        selected_items = self.get_selected_items()
        
        if self.rb_create_structure.isChecked():
            return {
                'action': 'create_structure',
                'create_clients': self.cb_create_clients.isChecked(),
                'create_orders': self.cb_create_orders.isChecked(),
                'include_files': self.cb_include_files.isChecked(),
                'items': selected_items
            }
        else:
            return {
                'action': 'add_to_existing',
                'items': selected_items
            }
    
    def accept(self):
        data = self.get_import_data()
        if not data['items']:
            QMessageBox.warning(self, "Внимание", "Не выбраны элементы для импорта")
            return
        super().accept()

# --- ДИАЛОГ ПЛАТЕЖЕЙ ---
class PaymentsDialog(QDialog, HelpButtonMixin):
    def __init__(self, order: Order, parent=None):
        super().__init__(parent)
        self.order = order
        self.parent_app = parent
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
        
        # Инициализация кнопки справки
        self.init_help_button(parent, "payments_history")

        header_layout = QHBoxLayout()
        header_title = QLabel("История финансовых операций")
        header_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #28A745;")
        header_layout.addWidget(header_title)
        header_layout.addStretch()
        header_layout.addWidget(self.help_btn)
        layout.addLayout(header_layout)

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
class FolderImportDialog(QDialog, HelpButtonMixin):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Импорт из папки")
        self.init_help_button(parent, "import_wizard")
        self.setMinimumWidth(600)
        
        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; }
            QLabel { color: #DDDDDD; font-size: 13px; }
            QLabel#HelpLabel { color: #AAAAAA; font-size: 11px; font-style: italic; }
            QLineEdit { background-color: #333333; color: #FFFFFF; border: 1px solid #444444; padding: 6px; border-radius: 3px; }
            QPushButton { background-color: #2D2D2D; color: #FFFFFF; border: 1px solid #3D3D3D; padding: 8px 12px; border-radius: 4px; }
            QPushButton:hover { background-color: #3D3D3D; }
            QListWidget { background-color: #252525; color: #FFFFFF; border: 1px solid #3D3D3D; }
            QGroupBox { color: #00D1FF; border: 1px solid #3D3D3D; border-radius: 5px; margin-top: 10px; padding: 15px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)
        
        layout = QVBoxLayout(self)
        
        header_layout = QHBoxLayout()
        header_layout.addStretch()
        header_layout.addWidget(self.help_btn)
        layout.addLayout(header_layout)

        # Шаг 1: Выбор папки
        step1_group = QGroupBox("Шаг 1: Выберите корневую папку")
        step1_layout = QVBoxLayout(step1_group)
        
        step1_layout.addWidget(QLabel("Укажите папку, в которой находятся папки с клиентами."))
        
        folder_layout = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Пример: D:/Мои Проекты/Клиенты")
        self.folder_edit.setReadOnly(True)
        browse_btn = QPushButton("Обзор...")
        browse_btn.clicked.connect(self.browse_folder)
        
        folder_layout.addWidget(self.folder_edit, 1)
        folder_layout.addWidget(browse_btn)
        step1_layout.addLayout(folder_layout)
        layout.addWidget(step1_group)
        
        # Шаг 2: Сканирование и предпросмотр
        step2_group = QGroupBox("Шаг 2: Предварительный просмотр")
        step2_layout = QVBoxLayout(step2_group)
        
        scan_btn = QPushButton("🔍 Сканировать папку")
        scan_btn.setStyleSheet("background-color: #0078D7; font-weight: bold;")
        scan_btn.clicked.connect(self.scan_folder)
        step2_layout.addWidget(scan_btn)
        
        step2_layout.addWidget(QLabel("Будут созданы следующие клиенты и заказы:"))
        self.preview_list = QListWidget()
        step2_layout.addWidget(self.preview_list)
        layout.addWidget(step2_group)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        self.import_btn = QPushButton("✅ Импортировать")
        self.import_btn.clicked.connect(self.accept)
        self.import_btn.setEnabled(False)
        self.import_btn.setStyleSheet("background-color: #28A745; font-weight: bold;")
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.import_btn)
        buttons_layout.addWidget(cancel_btn)
        
        layout.addLayout(buttons_layout)
        
        self.scan_results = []
        animate_dialog_open(self)
    
    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку для импорта")
        if folder:
            self.folder_edit.setText(folder)
    
    def scan_folder(self):
        folder = self.folder_edit.text()
        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self, "Ошибка", "Выберите существующую папку.")
            return

        self.preview_list.clear()
        self.scan_results = []
        
        # Сканируем подпапки в выбранной директории (это "клиенты")
        for client_name in os.listdir(folder):
            client_path = os.path.join(folder, client_name)
            if not os.path.isdir(client_path):
                continue

            client_data = {'client_name': client_name, 'orders': []}
            
            # Ищем папки "заказов" внутри папки клиента
            for order_name in os.listdir(client_path):
                order_path = os.path.join(client_path, order_name)
                if not os.path.isdir(order_path):
                    continue
                
                # Собираем все файлы и папки внутри заказа
                order_files = []
                for item in os.listdir(order_path):
                    item_path = os.path.join(order_path, item)
                    order_files.append((item, item_path))
                
                if order_files:
                    client_data['orders'].append({'order_name': order_name, 'files': order_files})
            
            if client_data['orders']:
                self.scan_results.append(client_data)

        # Отображаем результаты
        if not self.scan_results:
            self.preview_list.addItem("Клиенты или заказы не найдены. Проверьте структуру папок:\nКорневаяПапка -> ПапкаКлиента -> ПапкаЗаказа -> Файлы")
            self.import_btn.setEnabled(False)
            return

        for client_res in self.scan_results:
            client_item = QListWidgetItem(f"👤 Клиент: {client_res['client_name']}")
            client_item.setFont(QFont("Arial", 10, QFont.Bold))
            self.preview_list.addItem(client_item)
            for order_res in client_res['orders']:
                order_item = QListWidgetItem(f"  📦 Заказ: {order_res['order_name']} ({len(order_res['files'])} файлов)")
                self.preview_list.addItem(order_item)
        
        self.import_btn.setEnabled(True)

# --- ДИАЛОГ ПЕРВОГО ЗАПУСКА ---
class FirstRunDialog(QDialog, HelpButtonMixin):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_app = parent
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
                padding: 6px 12px; /* Уменьшил padding */
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
                color: #FFFFFF;
                font-size: 13px;
                padding: 8px 0;
                spacing: 10px;
            }
            QRadioButton::indicator {
                width: 20px;
                height: 20px;
                border-radius: 10px;
                border: 2px solid #555;
                background-color: #333;
            }
            QRadioButton::indicator:hover {
                border: 2px solid #00D1FF;
            }
            QRadioButton::indicator:checked {
                background-color: qradialgradient(cx:0.5, cy:0.5, radius: 0.9, fx:0.5, fy:0.5, stop:0 #FFA500, stop:1 #FFD700);
                border: 2px solid #FFA500;
            }
            QCheckBox {
                color: #FFFFFF; /* Белый цвет текста для всех чекбоксов */
                font-size: 13px;
                padding: 4px 0;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 2px solid #555555;
                background-color: #333333;
            }
            QCheckBox::indicator:checked {
                background-color: #28A745; /* Зеленый цвет при выборе */
                border: 2px solid #28A745;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
        
        # Инициализация кнопки справки
        self.init_help_button(parent, "first_run")

        # Приветствие (H1 и Sub)
        title_row = QHBoxLayout()
        title_row.addStretch()
        title_label = QLabel("<span style='color: #9400D3;'>Finance</span><span style='color: #FFA500;'>Fugue</span>")
        title_label.setStyleSheet("""
            font-size: 30px; /* Уменьшил шрифт еще */
            letter-spacing: 2px; /* Увеличил расстояние между буквами */
            font-weight: bold;
            text-shadow: 2px 2px 5px rgba(0, 0, 0, 0.7); /* Сохранил объем */
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_row.addWidget(title_label)
        title_row.addStretch()
        title_row.addWidget(self.help_btn)
        layout.addLayout(title_row)

        subtitle_label = QLabel("Профессиональная система управления заказами") # Более полный текст
        subtitle_label.setStyleSheet("font-size: 15px; color: #AAAAAA; font-style: italic;") # Уменьшил шрифт
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle_label)
        
        layout.addSpacing(5)
        
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
        browse_btn.setFixedWidth(70) # Уменьшил ширину кнопки
        
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
        
        self.rb_file_link = QRadioButton("В исходной папке")
        self.rb_file_copy = QRadioButton("В папке программы")

        self.file_storage_group = QButtonGroup(self)
        self.file_storage_group.addButton(self.rb_file_link)
        self.file_storage_group.addButton(self.rb_file_copy)
        
        self.rb_file_link.setChecked(True)
        
        layout.addWidget(self.rb_file_link)
        layout.addWidget(self.rb_file_copy)
        
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
                padding: 8px 16px;
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
    
        enc_on = self.encryption_switch.isChecked()
        app_pass_on = self.app_password_cb.isChecked()
        
        self.encryption_hint_label.setVisible(True) # Всегда показываем подсказку по шифрованию
        self.password_widget.setVisible(app_pass_on)
        
        if enc_on:
            self.encryption_hint_label.setText("Рекомендуется для защиты конфиденциальной информации. База данных будет зашифрована.")
            self.app_password_cb.setChecked(True) # Пароль обязателен для шифрования
            self.app_password_cb.setEnabled(False) # Блокируем чекбокс
            self.password_widget.setVisible(True)
            self.password_hint_label.setText("Этот пароль будет использоваться для шифрования и входа в программу.")
            self.password_hint_label.setVisible(True)
        else:
            self.app_password_cb.setEnabled(True) # Разблокируем чекбокс
            self.encryption_hint_label.setText("База данных не будет зашифрована. Это снижает защиту конфиденциальной информации.")
            if app_pass_on:
                self.password_widget.setVisible(True)
                self.password_hint_label.setText("Пароль будет запрашиваться только для входа в программу. Данные не шифруются.")
                self.password_hint_label.setVisible(True)
            else:
                self.password_widget.setVisible(False)
                self.password_hint_label.setVisible(False)


    def update_file_storage_ui(self):
        pass # Больше нет дополнительных UI элементов для обновления

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
        file_storage_mode = 'copy' if self.rb_file_copy.isChecked() else 'link'
        
        # Определение пароля (только если установлен флажок "Запрашивать пароль")
        password = self.pass_edit.text() if self.app_password_cb.isChecked() else None
        
        # Определение состояния создания ярлыка
        create_shortcut = self.create_shortcut_cb.isChecked()

        return {
            'database_path': database_path,
            'file_storage_mode': file_storage_mode,
            'encryption_enabled': self.encryption_switch.isChecked(), # Добавляем флаг шифрования
            'app_password': password, # Это пароль на запуск программы (может быть None)
            'create_shortcut': create_shortcut
        }

    def update_security_ui(self):
        enc_on = self.encryption_switch.isChecked()
        app_pass_on = self.app_password_cb.isChecked()
        
        self.encryption_hint_label.setVisible(True) # Всегда показываем подсказку по шифрованию
        self.password_widget.setVisible(app_pass_on)
        
        if enc_on:
            self.encryption_hint_label.setText("Рекомендуется для защиты конфиденциальной информации. База данных будет зашифрована.")
            self.app_password_cb.setChecked(True) # Пароль обязателен для шифрования
            self.app_password_cb.setEnabled(False) # Блокируем чекбокс
            self.password_widget.setVisible(True)
            self.password_hint_label.setText("Этот пароль будет использоваться для шифрования и входа в программу.")
            self.password_hint_label.setVisible(True)
        else:
            self.app_password_cb.setEnabled(True) # Разблокируем чекбокс
            self.encryption_hint_label.setText("База данных не будет зашифрована. Это снижает защиту конфиденциальной информации.")
            if app_pass_on:
                self.password_widget.setVisible(True)
                self.password_hint_label.setText("Пароль будет запрашиваться только для входа в программу. Данные не шифруются.")
                self.password_hint_label.setVisible(True)
            else:
                self.password_widget.setVisible(False)
                self.password_hint_label.setVisible(False)


class ContextualHelpDialog(QDialog):
    def __init__(self, title, content_html, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(500, 300)
        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; }
            QTextBrowser {
                color: #DDDDDD;
                border: 1px solid #3D3D3D;
                padding: 15px;
                font-size: 14px;
                background-color: #252525;
            }
            QPushButton {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #3D3D3D;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #3D3D3D; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        self.content_view = QTextBrowser()
        self.content_view.setOpenExternalLinks(True)
        self.content_view.setHtml(content_html)
        layout.addWidget(self.content_view)
        
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        
        animate_dialog_open(self)
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
class ClientSettingsDialog(QDialog, HelpButtonMixin):
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
        
        # Инициализация кнопки справки
        self.init_help_button(parent, "client_settings")

        header_layout = QHBoxLayout()
        header_title = QLabel(f"Профиль: {client.name}")
        header_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #00D1FF;")
        header_layout.addWidget(header_title)
        header_layout.addStretch()
        header_layout.addWidget(self.help_btn)
        layout.addLayout(header_layout)

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
class SettingsDialog(QDialog, HelpButtonMixin):
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
        layout.setSpacing(15)
        
        # Инициализация кнопки справки
        self.init_help_button(parent, "settings")

        header_layout = QHBoxLayout()
        header_title = QLabel("Глобальные настройки системы")
        header_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFFFFF;")
        header_layout.addWidget(header_title)
        header_layout.addStretch()
        header_layout.addWidget(self.help_btn)
        layout.addLayout(header_layout)

        # --- Справка ---
        self.help_texts = {
            "db_location": "Позволяет изменить папку, в которой хранится файл базы данных (pro_database.db). Вы сможете выбрать, копировать ли связанные файлы в новое место.",
            "import_folder": "Эта функция сканирует выбранную вами папку и ищет в ней подпапки, рассматривая каждую как отдельного клиента. Затем она анализирует содержимое каждой папки-клиента для создания заказов. Вам будет предложен предварительный список найденных клиентов и заказов для подтверждения импорта.",
            "import_json": "Импортирует данные из ранее экспортированного JSON файла. Текущие данные будут заархивированы.",
            "export_json": "Экспортирует всю базу данных (клиентов, заказы, платежи) в один JSON файл. Файлы проектов при этом не затрагиваются.",
            "export_zip": "Создает полный бэкап, включающий файл базы данных и все связанные файлы проектов, в единый ZIP архив.",
            "security": "Открывает диалог для настройки шифрования базы данных и установки/изменения пароля для входа в приложение.",
            "backup_settings": "Создает резервную копию файла настроек приложения (crm_settings.json) в папку 'settings_backups'.",
            "restore_settings": "Позволяет восстановить настройки приложения из ранее созданной резервной копии.",
            "delete_files": "ОСТОРОЖНО! Удаляет все прикрепленные файлы из программы. Можно выбрать, удалять ли их физически с диска.",
            "delete_db": "ОСТОРОЖНО! Полностью очищает базу данных, удаляя всех клиентов и заказы. Это действие необратимо без бэкапа."
        }
        
        # --- Структура ---
        
        # Раздел "Данные"
        data_group = QGroupBox("Импорт и Экспорт Данных")
        data_layout = QVBoxLayout(data_group)
        
        btn_imp_folder = QPushButton("Импорт из папки")
        btn_imp_folder.clicked.connect(lambda: self.show_help_for_button("import_folder", self.main_window.import_from_folder))
        
        btn_imp = QPushButton("Импорт базы (JSON)")
        btn_imp.clicked.connect(lambda: self.show_help_for_button("import_json", self.main_window.import_json_file))
        
        btn_exp = QPushButton("Экспорт базы (JSON)")
        btn_exp.clicked.connect(lambda: self.show_help_for_button("export_json", self.main_window.export_json))
        
        btn_full = QPushButton("Полный бэкап (ZIP)")
        btn_full.clicked.connect(lambda: self.show_help_for_button("export_zip", self.main_window.export_full_backup))

        data_layout.addWidget(btn_imp_folder)
        data_layout.addWidget(btn_imp)
        data_layout.addWidget(btn_exp)
        data_layout.addWidget(btn_full)
        layout.addWidget(data_group)

        # Раздел "База данных"
        db_group = QGroupBox("Database")
        db_group.setObjectName("DatabaseGroup")
        db_layout = QVBoxLayout(db_group)
        
        btn_db_location = QPushButton("Select Database Storage Location")
        btn_db_location.clicked.connect(lambda: self.show_help_for_button("db_location", self.change_database_location))
        db_layout.addWidget(btn_db_location)
        layout.addWidget(db_group)

        # Раздел "Настройки приложения"
        app_settings_group = QGroupBox("Настройки приложения")
        app_settings_layout = QVBoxLayout(app_settings_group)
        
        btn_backup_settings = QPushButton("Создать копию настроек")
        btn_backup_settings.clicked.connect(lambda: self.show_help_for_button("backup_settings", self.manual_backup_settings))
        
        btn_restore_settings = QPushButton("Восстановить настройки")
        btn_restore_settings.clicked.connect(lambda: self.show_help_for_button("restore_settings", self.restore_settings_dialog))

        app_settings_layout.addWidget(btn_backup_settings)
        app_settings_layout.addWidget(btn_restore_settings)
        layout.addWidget(app_settings_group)
        
        # Кнопка безопасности отдельно
        btn_security = QPushButton("🔐 Настройки безопасности")
        btn_security.clicked.connect(lambda: self.show_help_for_button("security", self.open_security_settings))
        layout.addWidget(btn_security)
        
        # Раздел "Опасная зона"
        danger_group = QGroupBox() # Убираем заголовок
        danger_group.setStyleSheet("QGroupBox { border: 2px solid #D32F2F; margin-top: 15px; }")
        danger_layout = QVBoxLayout(danger_group)

        btn_del_files = QPushButton("🗑 Удалить ВСЕ файлы")
        btn_del_files.setStyleSheet("background-color: #A12A2A; color: white;")
        btn_del_files.clicked.connect(lambda: self.show_help_for_button("delete_files", self.main_window.delete_all_files))
        danger_layout.addWidget(btn_del_files)

        btn_del_db = QPushButton("☠ Удалить ВСЮ базу данных")
        btn_del_db.setStyleSheet("background-color: #D32F2F; color: white; font-weight: bold;")
        btn_del_db.clicked.connect(lambda: self.show_help_for_button("delete_db", self.main_window.delete_database_full))
        danger_layout.addWidget(btn_del_db)
        layout.addWidget(danger_group)

        layout.addSpacing(10)
        
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
        
        animate_dialog_open(self)

    def show_help_for_button(self, key, action_func):
        text = self.help_texts.get(key, "Справка не найдена.")
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Справка")
        msg_box.setText(text)
        msg_box.setIcon(QMessageBox.Icon.Information)
        
        btn_continue = msg_box.addButton("Продолжить", QMessageBox.ButtonRole.AcceptRole)
        btn_cancel = msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        msg_box.exec()
        
        if msg_box.clickedButton() == btn_continue:
            action_func()
    
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
        current_password = None
        # Запрашиваем пароль, если он установлен (для шифрования или просто для входа)
        if hasattr(self.main_window, 'backend') and self.main_window.backend.security.has_app_password():
            pwd, ok = QInputDialog.getText(self, "Проверка доступа", "Введите текущий пароль:", QLineEdit.EchoMode.Password)
            if not ok: return
            if not self.main_window.backend.check_password(pwd):
                QMessageBox.critical(self, "Ошибка", "Неверный пароль")
                return
            current_password = pwd
        
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
        want_pass = self.cb_app_pass.isChecked()
        
        self.gb_access.setEnabled(not enc_on)
        self.pass_widget.setVisible(want_pass or enc_on)

        if enc_on:
            self.cb_app_pass.setChecked(True)
            self.lbl_pass_info.setText("Пароль используется для шифрования и входа.")
        elif want_pass:
            self.lbl_pass_info.setText("Пароль будет запрашиваться только для входа.")
        else:
            self.lbl_pass_info.setText("")

    def apply_changes(self):
        # Получаем желаемые состояния из UI
        want_enc = self.rb_enc_on.isChecked()
        want_pass = self.cb_app_pass.isChecked()

        # Получаем текущие состояния из backend
        cur_enc = self.backend.security.is_encrypted()
        cur_has_pass = self.backend.security.has_app_password()

        password = self.new_pass.text()

        # Проверка на совпадение паролей, если они введены
        if password and password != self.confirm_pass.text():
            QMessageBox.warning(self, "Ошибка", "Пароли не совпадают")
            return

        # Сценарий: Изменение режима шифрования
        if want_enc != cur_enc:
            if want_enc: # Хотим зашифровать
                if not password: # Для шифрования пароль всегда нужен
                    QMessageBox.warning(self, "Ошибка", "Для шифрования необходимо задать пароль")
                    return
                reply = QMessageBox.warning(self, "Шифрование",
                    "Внимание! Если вы забудете пароль, данные восстановить будет НЕВОЗМОЖНО.\nПродолжить?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No: return

                if self.backend.change_encryption_mode(password, True):
                    self.backend.security.set_app_password(password) # Пароль для шифрования становится и паролем для входа
                    QMessageBox.information(self, "Успех", "База данных зашифрована.")
                    self.accept()
                else:
                    QMessageBox.critical(self, "Ошибка", "Не удалось зашифровать базу данных.")

            else: # Хотим расшифровать
                reply = QMessageBox.warning(self, "Расшифровка",
                    "База данных будет расшифрована и сохранена в открытом виде.\nПродолжить?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.No: return

                if self.backend.change_encryption_mode(self.current_password, False): # current_password - это пароль, которым разблокировали диалог
                    # После расшифровки, если хотят пароль для входа, устанавливаем его
                    if want_pass:
                        if password:
                            self.backend.security.set_app_password(password)
                        elif cur_has_pass: # Если пароль для входа был, но новый не введен, оставляем старый
                            # self.backend.security.set_app_password(self.current_password) # current_password может быть None если не было шифрования
                            pass # Пароль уже установлен, или не был изменен, если не введен новый
                        else: # Хотят пароль для входа, но не ввели
                             QMessageBox.warning(self, "Ошибка", "Введите пароль для входа в программу.")
                             return
                    else: # Не хотят пароль для входа
                        self.backend.security.remove_app_password()
                    QMessageBox.information(self, "Успех", "Шифрование отключено.")
                    self.accept()
                else:
                    QMessageBox.critical(self, "Ошибка", "Не удалось отключить шифрование.")

        else: # Сценарий: Изменение только пароля доступа, без изменения режима шифрования
            if want_pass:
                if not password and not cur_has_pass: # Хотят пароль для входа, но не ввели и его не было
                    QMessageBox.warning(self, "Ошибка", "Введите пароль для входа в программу.")
                    return
                elif password: # Ввели новый пароль
                    self.backend.security.set_app_password(password)
                # else: пароль был, новый не введен - оставляем старый
                QMessageBox.information(self, "Успех", "Пароль для входа установлен/изменен.")
                self.accept()
            else: # Не хотят пароль для входа
                if cur_has_pass:
                    # Если был установлен пароль, для его снятия нужно подтверждение
                    if self.current_password is None:
                         # Эта ситуация возникает, если шифрования не было, но пароль был.
                         # self.open_security_settings должен был запросить пароль.
                         # Если мы здесь, значит что-то пошло не так, но для безопасности прервемся.
                         QMessageBox.critical(self, "Ошибка", "Требуется подтверждение старого пароля для его удаления.")
                         return

                    self.backend.security.remove_app_password()
                    QMessageBox.information(self, "Успех", "Пароль для входа удален.")
                self.accept()

class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FinanceFugue - Справка")
        self.resize(950, 650)
        
        # Основной layout
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Left Panel for Navigation
        self.nav_panel = QWidget()
        self.nav_panel.setFixedWidth(220)
        self.nav_panel.setStyleSheet("background-color: #252525; border-right: 1px solid #333333;")
        nav_layout = QVBoxLayout(self.nav_panel)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(0)

        self.nav_list = QListWidget()
        self.nav_list.setStyleSheet("""
            QListWidget {
                color: #FFFFFF;
                font-size: 14px;
                outline: none;
                border: none;
            }
            QListWidget::item { 
                padding: 15px; 
                border-bottom: 1px solid #2D2D2D; 
            }
            QListWidget::item:selected { 
                background-color: #0078D7; 
                color: white; 
                border-left: 3px solid #00D1FF;
            }
        """)
        nav_layout.addWidget(self.nav_list)
        
        # Right Panel for Content
        self.content_panel = QWidget()
        self.content_panel.setStyleSheet("background-color: #1A1A1A;")
        content_layout = QVBoxLayout(self.content_panel)
        
        self.content_view = QTextBrowser()
        self.content_view.setOpenExternalLinks(True)
        self.content_view.setStyleSheet("""
            QTextBrowser {
                color: #DDDDDD;
                border: none;
                padding: 25px;
                font-size: 15px;
            }
        """)
        content_layout.addWidget(self.content_view)

        self.main_layout.addWidget(self.nav_panel)
        self.main_layout.addWidget(self.content_panel)
        
        # Populate navigation
        self.nav_list.addItem("🚀 Введение")
        self.nav_list.addItem("👤 Работа с клиентами")
        self.nav_list.addItem("📦 Управление заказами")
        self.nav_list.addItem("💰 Финансы и платежи")
        self.nav_list.addItem("📁 Менеджер файлов")
        self.nav_list.addItem("⚙️ Настройки и бэкапы")
        self.nav_list.addItem("⌨️ Горячие клавиши")
        self.nav_list.addItem("💡 Полезные советы")
        self.nav_list.addItem("📄 О программе")
        
        self.nav_list.currentRowChanged.connect(self.display_section)
        
        # Load sections data
        self.load_sections()
        
        # Set initial view
        self.nav_list.setCurrentRow(0)
        
        animate_dialog_open(self)

    def load_sections(self):
        self.sections = {
            0: ("🚀 Введение", """
                <h1 style='color: #00D1FF;'>FinanceFugue</h1>
                <p>Профессиональная система управления заказами, созданная для фрилансеров, студий и творческих профессионалов.</p>
                <p>Программа позволяет вести базу клиентов, отслеживать финансовые потоки по каждому заказу, управлять сроками выполнения работ и хранить все связанные файлы в единой структуре.</p>
                <h3>Основные возможности:</h3>
                <ul>
                    <li><b>Клиентская база:</b> Ведите учет всех ваших клиентов с контактной информацией и заметками.</li>
                    <li><b>Управление заказами:</b> Создавайте заказы для каждого клиента, отслеживайте их статусы, сроки и файлы.</li>
                    <li><b>Финансовый контроль:</b> Автоматический расчет стоимости, авансов, платежей и долгов по каждому заказу и по всем клиентам в целом.</li>
                    <li><b>Менеджер файлов:</b> Удобно добавляйте, просматривайте и экспортируйте файлы, связанные с заказами, с поддержкой Drag & Drop.</li>
                    <li><b>Безопасность:</b> Возможность шифрования базы данных и установки пароля на вход для защиты ваших данных.</li>
                    <li><b>Импорт и Экспорт:</b> Гибкие инструменты для переноса данных и создания резервных копий.</li>
                </ul>
            """),
            1: ("👤 Работа с клиентами", """
                <h2 style='color: #00D1FF;'>Управление клиентами</h2>
                <p>Клиенты — это основа вашей рабочей структуры в программе. Вся информация группируется вокруг карточек клиентов.</p>
                <h3>Создание клиента</h3>
                <p>Вы можете создать клиента несколькими способами:</p>
                <ul>
                    <li><b>Вручную:</b> Нажмите кнопку '➕ Новый клиент' на левой панели или используйте горячую клавишу <b>Ctrl+N</b>.</li>
                    <li><b>Автоматически из папки:</b> Перетащите папку с именем клиента в левую панель со списком клиентов. Программа предложит создать клиента с таким именем и импортировать содержимое папки.</li>
                </ul>
                <h3>Профиль клиента</h3>
                <p>Кликнув на имя клиента в списке, вы откроете его профиль. Здесь отображается вся ключевая информация:</p>
                <ul>
                    <li><b>Финансовая статистика:</b> Общая сумма заказов, сумма оплат, авансов и текущий долг.</li>
                    <li><b>Контактная информация:</b> Иконки соцсетей и почты становятся активными, если вы добавите соответствующие ссылки в настройках клиента.</li>
                    <li><b>Список заказов:</b> Все заказы данного клиента, сгруппированные в удобные карточки.</li>
                </ul>
            """),
            2: ("📦 Управление заказами", """
                <h2 style='color: #00D1FF;'>Управление заказами</h2>
                <p>Каждый заказ — это отдельная карточка в профиле клиента, содержащая всю необходимую информацию о работе.</p>
                <h3>Карточка заказа</h3>
                <ul>
                    <li><b>Статус:</b> Используйте переключатель "В РАБОТЕ" / "ГОТОВО", чтобы быстро менять статус заказа. Если у заказа есть долг, программа предложит автоматически его погасить при завершении.</li>
                    <li><b>Даты:</b> Вы можете легко изменить дату создания заказа и срок его выполнения, кликнув на соответствующие поля. Цвет поля срока выполнения меняется в зависимости от близости дедлайна.</li>
                    <li><b>Финансы:</b> Поля "СТОИМОСТЬ", "АВАНС" и "ДОЛГ" являются интерактивными. Изменение одного из них автоматически пересчитывает остальные, создавая соответствующие финансовые операции (платежи или корректировки).</li>
                    <li><b>Файлы:</b> Вы можете перетаскивать файлы и папки прямо на карточку заказа, чтобы прикрепить их.</li>
                </ul>
                <h3>Меню настроек заказа (⚙️)</h3>
                <p>Нажав на иконку шестеренки в карточке заказа, вы получите доступ к дополнительным функциям: переименование, смена валюты, дублирование, экспорт файлов и удаление заказа.</p>
            """),
            3: ("💰 Финансы и платежи", """
                <h2 style='color: #00D1FF;'>Финансы и платежи</h2>
                <p>Программа автоматически отслеживает все финансовые операции на основе ваших действий.</p>
                <h3>Как это работает:</h3>
                <ul>
                    <li><b>Добавление платежа:</b> Нажмите кнопку "✚ добавить" в блоке "ПЛАТЕЖИ" на карточке заказа, чтобы зарегистрировать поступление средств.</li>
                    <li><b>Автоматические операции:</b> Когда вы изменяете поля "СТОИМОСТЬ", "АВАНС" или "ДОЛГ", программа сама создает "платеж" или "корректировку", чтобы сбалансировать расчеты.</li>
                    <li><b>История платежей:</b> Кнопка "📋 история" открывает подробный список всех операций по данному заказу.</li>
                    <li><b>Статус оплаты:</b> Кнопка "ОПЛАЧЕНО" / "НЕ ОПЛАЧЕНО" позволяет быстро погасить весь долг или отменить последний платеж.</li>
                </ul>
            """),
            4: ("📁 Менеджер файлов", """
                <h2 style='color: #00D1FF;'>Менеджер файлов</h2>
                <p>Глобальный менеджер файлов (кнопка "📁 менеджер файлов" в главном окне) предоставляет обзор всех файлов по всем клиентам и заказам.</p>
                <h3>Возможности:</h3>
                <ul>
                    <li><b>Просмотр:</b> Вся структура клиентов, заказов и файлов представлена в виде дерева.</li>
                    <li><b>Drag & Drop:</b> Перетаскивайте файлы и папки в окно, чтобы добавить их к существующему клиенту/заказу или создать нового.</li>
                    <li><b>Контекстное меню:</b> Правый клик по любому элементу (клиенту, заказу, файлу) открывает меню с дополнительными действиями: переименование, удаление, переход к карточке и т.д.</li>
                </ul>
            """),
            5: ("⚙️ Настройки и бэкапы", """
                <h2 style='color: #00D1FF;'>Настройки и бэкапы</h2>
                <p>Диалог настроек (кнопка "⚙ Настройки" в главном окне) позволяет управлять глобальными параметрами программы.</p>
                <h3>Разделы:</h3>
                <ul>
                    <li><b>Импорт и Экспорт Данных:</b> Здесь вы можете импортировать данные из папок или JSON-файла, а также создать резервную копию вашей базы в форматах JSON или ZIP (полный бэкап с файлами).</li>
                    <li><b>Конфигурация:</b> Позволяет изменить место хранения файла базы данных и настроить параметры безопасности (шифрование, пароль на вход).</li>
                    <li><b>Настройки приложения:</b> Управление резервными копиями файла конфигурации.</li>
                </ul>
                <p><b>ВАЖНО:</b> Регулярно создавайте полные резервные копии (ZIP), чтобы не потерять данные и прикрепленные файлы.</p>
            """),
            6: ("⌨️ Горячие клавиши", """
                <h2 style='color: #00D1FF;'>Горячие клавиши</h2>
                <ul>
                    <li><b>Ctrl + N:</b> Создать нового клиента</li>
                    <li><b>Ctrl + S:</b> Сохранить изменения (хотя большинство изменений сохраняются автоматически)</li>
                    <li><b>Ctrl + Q:</b> Закрыть программу</li>
                    <li><b>Ctrl + F:</b> Установить фокус на поле поиска клиентов</li>
                    <li><b>Ctrl + O:</b> Открыть глобальный менеджер файлов</li>
                    <li><b>Ctrl + Shift + S:</b> Открыть настройки</li>
                    <li><b>F5:</b> Обновить список клиентов</li>
                    <li><b>Delete:</b> Удалить выбранного клиента(ов)</li>
                </ul>
            """),
            7: ("💡 Полезные советы", """
                <h2 style='color: #00D1FF;'>Полезные советы</h2>
                <ul>
                    <li><b>Drag & Drop повсюду:</b> Вы можете перетаскивать файлы и папки не только в менеджер файлов, но и напрямую на список клиентов (для создания нового клиента) или на карточку заказа.</li>
                    <li><b>Контекстные меню:</b> Не забывайте нажимать правую кнопку мыши на клиентах, заказах и файлах. Это открывает быстрый доступ ко многим полезным функциям.</li>
                    <li><b>Интерактивные финансы:</b> Не бойтесь редактировать поля стоимости, аванса и долга прямо в карточке заказа. Программа сама выполнит все необходимые расчеты.</li>
                </ul>
            """),
            8: ("📄 О программе", """
                <h2 style='color: #00D1FF;'>О программе</h2>
                <p><b>KVF SOFT.</b> Авторские права - Kirill Fandeev.</p>
                <p>Написать автору: <a href='mailto:KVF_SOFT@mail.ru' style='color: #00D1FF;'>KVF_SOFT@mail.ru</a></p>
            """)
        }

    def display_section(self, index):
        if index in self.sections:
            _, html_content = self.sections[index]
            self.content_view.setHtml(html_content)
            
    def select_section(self, section_name):
        for i in range(self.nav_list.count()):
            if section_name in self.nav_list.item(i).text():
                self.nav_list.setCurrentRow(i)
                break


class SelectionDialog(QDialog, HelpButtonMixin):
    def __init__(self, folder_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Items to Create Orders")
        self.init_help_button(parent, "selection_dialog")
        self.folder_path = folder_path
        self.selected_items = []

        layout = QVBoxLayout(self)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Select items to create orders for")
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.MultiSelection)
        layout.addWidget(self.tree)

        self.populate_tree()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def populate_tree(self):
        self.tree.clear()
        items = self._get_folder_items(self.folder_path)
        for item in items:
            self.tree.addTopLevelItem(item)

    def _get_folder_items(self, path):
        items = []
        for name in os.listdir(path):
            full_path = os.path.join(path, name)
            item = QTreeWidgetItem([name])
            item.setData(0, Qt.ItemDataRole.UserRole, full_path)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Unchecked)
            if os.path.isdir(full_path):
                child_items = self._get_folder_items(full_path)
                item.addChildren(child_items)
            items.append(item)
        return items

    def accept(self):
        self.selected_items = []
        iterator = QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            if item.checkState(0) == Qt.CheckState.Checked:
                self.selected_items.append(item.data(0, Qt.ItemDataRole.UserRole))
            iterator += 1
        super().accept()



