import os
import platform
import logging
from .logger import get_logger

logger = get_logger("Widgets")
import subprocess
import zipfile
import shutil
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, 
    QMessageBox, QMenu, QInputDialog, QLineEdit, QFrame, 
    QCheckBox, QDialog, QFormLayout, QComboBox, QDateEdit,
    QDialogButtonBox, QFileDialog, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QDoubleValidator

from .models import ProjectFile, Order
from .dialogs import PaymentsDialog

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
        btn_open.setFixedWidth(60)
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
        
        # Кнопка удаления файла
        btn_delete = QPushButton("Удалить")
        btn_delete.setFixedWidth(60)
        btn_delete.clicked.connect(self.delete_file)
        btn_delete.setStyleSheet("""
            QPushButton {
                background-color: #DC3545;
                color: white;
                border: 1px solid #DC3545;
                padding: 4px;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #C82333;
            }
        """)
        
        layout.addWidget(self.name_label, 1)
        layout.addWidget(btn_open)
        layout.addWidget(btn_delete)
    
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
    
    def delete_file(self):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Удаление файла")
        msg_box.setText(f"Вы уверены, что хотите удалить файл '{self.file_obj.name}' из заказа?")
        msg_box.setIcon(QMessageBox.Icon.Question)
        
        btn_delete = msg_box.addButton("Удалить", QMessageBox.ButtonRole.YesRole)
        btn_cancel = msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        
        msg_box.exec()
        
        if msg_box.clickedButton() == btn_delete:
            # Находим заказ, которому принадлежит файл
            for client in self.parent_app.clients:
                for order in client.orders:
                    if self.file_obj in order.files:
                        order.files.remove(self.file_obj)
                        self.parent_app.render_client_profile()
                        self.parent_app.save_db()
                        return

class OrderWidget(QFrame):
    def __init__(self, order: Order, parent_app):
        super().__init__()
        self.order = order
        self.parent_app = parent_app
        self.setAcceptDrops(True)  # Разрешаем drag and drop
        self.init_ui()
        self.update_deadline_color()

    def init_ui(self):
        self.setStyleSheet("""
            QFrame#OrderCard {
                background-color: #2A2A2A;
                border-radius: 8px;
                border: 1px solid #3D3D3D;
                margin-bottom: 5px;
            }
        """)
        self.setObjectName("OrderCard")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 8, 10, 8)
        self.main_layout.setSpacing(4)

        # Заголовок
        header = QHBoxLayout()
        
        # Явная стрелка для сворачивания
        self.toggle_btn = QPushButton("▼")
        self.toggle_btn.setFixedSize(16, 16)
        self.toggle_btn.clicked.connect(self.toggle_contents)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #888888;
                border: none;
                font-size: 12px;
            }
            QPushButton:hover {
                color: #FFFFFF;
            }
        """)

        title = QLabel(f"{self.order.service_type}")
        title.setStyleSheet("font-weight: bold; color: #00D1FF; font-size: 18px;")
        
        # Кнопка удаления заказа - СЕРАЯ
        self.delete_btn = QPushButton("Удалить")
        self.delete_btn.setFixedWidth(70)
        self.delete_btn.clicked.connect(self.delete_order)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #6C757D;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #5A6268;
            }
        """)

        # Чекбокс "Выполнен"
        self.status_cb = QCheckBox("Выполнен")
        self.status_cb.setChecked(self.order.status == "Завершен")
        self.status_cb.stateChanged.connect(self.update_order_status)
        self.status_cb.setStyleSheet("""
            QCheckBox {
                color: #DDDDDD;
                font-size: 12px;
                padding-left: 5px;
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
        header.addWidget(self.delete_btn)
        self.main_layout.addLayout(header)

        # Содержимое
        self.content = QWidget()
        self.c_layout = QVBoxLayout(self.content)
        self.c_layout.setSpacing(4)
        
        # Информация (ID и дата заказа)
        info_widget = QWidget()
        info_layout = QHBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        
        id_label = QLabel(f"ID: {self.order.id[:8]}...")
        id_label.setStyleSheet("color: #888888; font-size: 10px;")
        info_layout.addWidget(id_label)
        
        info_layout.addStretch()
        
        # Редактируемая дата заказа
        date_box = QWidget()
        date_box_layout = QHBoxLayout(date_box)
        date_box_layout.setContentsMargins(0,0,0,0)
        date_box_layout.setSpacing(5)
        
        start_date_label = QLabel("дата заказа:")
        start_date_label.setStyleSheet("color: #888888; font-size: 10px;")
        
        self.order_date_edit = QDateEdit()
        self.order_date_edit.setCalendarPopup(True)
        self.order_date_edit.setDisplayFormat("dd.MM.yyyy")
        try:
            if self.order.created_at:
                d_str = self.order.created_at.split()[0]
                self.order_date_edit.setDate(datetime.strptime(d_str, "%d.%m.%Y").date())
            else:
                self.order_date_edit.setDate(datetime.now().date())
        except:
            self.order_date_edit.setDate(datetime.now().date())
            
        self.order_date_edit.setFixedWidth(90)
        self.order_date_edit.dateChanged.connect(self.sync_order_date)
        self.order_date_edit.setStyleSheet("""
            QDateEdit {
                background-color: transparent;
                color: #888888;
                border: 1px solid #333333;
                font-size: 10px;
                padding: 1px;
            }
            QDateEdit::drop-down { border: none; background: #333333; width: 12px; }
            QDateEdit::down-arrow { image: none; border-left: 3px solid transparent; border-right: 3px solid transparent; border-top: 3px solid #888888; }
        """)
        
        date_box_layout.addWidget(start_date_label)
        date_box_layout.addWidget(self.order_date_edit)
        info_layout.addWidget(date_box)
        
        self.c_layout.addWidget(info_widget)
        
        # Финансовый блок
        financial_container = QWidget()
        financial_layout = QVBoxLayout(financial_container)
        financial_layout.setContentsMargins(0, 2, 0, 2)
        financial_layout.setSpacing(8)

        # Верхняя строка: Стоимость, Аванс, Долг
        money_row = QHBoxLayout()
        money_row.setSpacing(15)

        # Функция для создания стилизованного блока ввода с меткой
        def create_money_box(label_text, value, color, callback):
            box = QWidget()
            layout = QVBoxLayout(box)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(2)
            
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #AAAAAA; font-size: 11px; font-weight: bold;")
            
            edit = QLineEdit(self.format_number(value))
            edit.setFixedWidth(120)
            edit.editingFinished.connect(callback)
            edit.setStyleSheet(f"""
                QLineEdit {{
                    background-color: #252525;
                    color: {color};
                    border: 1px solid #444444;
                    padding: 8px;
                    border-radius: 4px;
                    font-size: 16px;
                    font-weight: bold;
                }}
                QLineEdit:focus {{
                    border: 1px solid {color};
                }}
            """)
            layout.addWidget(lbl)
            layout.addWidget(edit)
            return box, edit

        cost_box, self.cost_edit = create_money_box("СТОИМОСТЬ", self.order.price, "#00D1FF", self.sync_price)
        advance_box, self.advance_edit = create_money_box("АВАНС", self.order.advance, "#FFD700", self.sync_advance)
        debt_box, self.debt_edit = create_money_box("ДОЛГ", self.order.debt, "#FF4B2B", self.sync_debt)

        money_row.addWidget(cost_box)
        money_row.addWidget(advance_box)
        money_row.addWidget(debt_box)
        money_row.addStretch()
        
        financial_layout.addLayout(money_row)

        # Нижняя строка: Платежи
        payments_row = QHBoxLayout()
        payments_row.setSpacing(10)
        
        payments_label = QLabel("платежи:")
        payments_label.setStyleSheet("color: #AAAAAA; font-size: 12px; font-weight: bold; margin-right: 5px;")
        
        add_payment_btn = QPushButton("✚ добавить")
        add_payment_btn.setFixedWidth(100)
        add_payment_btn.clicked.connect(self.add_payment_dialog)
        add_payment_btn.setStyleSheet("""
            QPushButton {
                background-color: #28A745;
                color: white;
                font-weight: bold;
                padding: 6px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        
        history_payment_btn = QPushButton("📋 история")
        history_payment_btn.setFixedWidth(100)
        history_payment_btn.clicked.connect(self.show_payments_history)
        history_payment_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078D7;
                color: white;
                font-weight: bold;
                padding: 6px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0056A3;
            }
        """)
        
        payments_row.addWidget(payments_label)
        payments_row.addWidget(add_payment_btn)
        payments_row.addWidget(history_payment_btn)
        payments_row.addStretch()
        
        financial_layout.addLayout(payments_row)
        
        self.c_layout.addWidget(financial_container)

        # Статус оплаты
        self.payment_status = QLabel()
        # self.update_payment_status() - перенесено ниже, после обновления UI
        self.c_layout.addWidget(self.payment_status)

        # Дедлайн с цветовой индикацией и календарем
        deadline_widget = QWidget()
        deadline_layout = QHBoxLayout(deadline_widget)
        deadline_layout.setContentsMargins(0, 5, 0, 5)
        deadline_layout.setSpacing(10)

        deadline_label = QLabel("СРОК:")
        deadline_label.setStyleSheet("color: #CCCCCC; font-size: 13px; font-weight: bold;")
        
        self.deadline_edit = QDateEdit()
        self.deadline_edit.setCalendarPopup(True)
        self.deadline_edit.setDisplayFormat("dd.MM.yyyy")
        try:
            if self.order.deadline:
                self.deadline_edit.setDate(datetime.strptime(self.order.deadline, "%d.%m.%Y").date())
            else:
                self.deadline_edit.setDate(datetime.now().date())
        except:
            self.deadline_edit.setDate(datetime.now().date())
            
        self.deadline_edit.dateChanged.connect(self.sync_deadline)
        self.deadline_edit.setFixedWidth(110)
        self.deadline_edit.setStyleSheet("""
            QDateEdit {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #444444;
                padding: 4px 6px;
                border-radius: 3px;
                font-size: 14px;
                font-weight: bold;
            }
            QDateEdit::drop-down {
                border: none;
                background: #444444;
                width: 20px;
            }
        """)
        
        deadline_layout.addWidget(deadline_label)
        deadline_layout.addWidget(self.deadline_edit)
        deadline_layout.addStretch()
        
        self.c_layout.addWidget(deadline_widget)
        
        # Файлы
        files_label = QLabel("Файлы:")
        files_label.setStyleSheet("font-weight: bold; margin-top: 5px; color: #CCCCCC; font-size: 13px;")
        self.c_layout.addWidget(files_label)
        
        # Добавляем подсказку о drag and drop
        drag_label = QLabel("(перетащите файлы или папки сюда)")
        drag_label.setStyleSheet("color: #888888; font-size: 10px; font-style: italic; margin-bottom: 2px;")
        self.c_layout.addWidget(drag_label)
        
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
        
        b_z = QPushButton("📦 Экспорт файлов")  # Изменили текст
        b_z.clicked.connect(self.export_files_to_zip)  # Изменили метод
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

    # Drag and drop методы
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return
            
        files_to_add = []
        folders_to_handle = []
        
        for url in urls:
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):
                files_to_add.append(file_path)
            elif os.path.isdir(file_path):
                folders_to_handle.append(file_path)
        
        # Обрабатываем папки
        for folder_path in folders_to_handle:
            # Считаем файлы в папке
            all_files = []
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    all_files.append(os.path.join(root, file))
            
            if len(all_files) > 5:
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Много файлов в папке")
                msg_box.setText(f"В папке '{os.path.basename(folder_path)}' найдено {len(all_files)} файлов.")
                msg_box.setInformativeText("Как вы хотите добавить эту папку?")
                msg_box.setIcon(QMessageBox.Icon.Question)
                
                btn_add_all = msg_box.addButton("Добавить все файлы", QMessageBox.ButtonRole.YesRole)
                btn_link = msg_box.addButton("Создать ссылку на папку", QMessageBox.ButtonRole.NoRole)
                btn_cancel = msg_box.addButton("Пропустить", QMessageBox.ButtonRole.RejectRole)
                
                msg_box.exec()
                
                clicked_button = msg_box.clickedButton()
                
                if clicked_button == btn_add_all:
                    files_to_add.extend(all_files)
                elif clicked_button == btn_link:
                    # Создаем кнопку для доступа к папке
                    self.add_folder_access_button(folder_path)
                # Если Cancel - пропускаем эту папку
            else:
                files_to_add.extend(all_files)
        
        # Обрабатываем файлы
        for file_path in files_to_add:
            self.add_file_with_storage_option(file_path)
        
        self.parent_app.render_client_profile()
        self.parent_app.save_db()

    def add_folder_access_button(self, folder_path):
        """Добавляет кнопку для быстрого доступа к папке"""
        folder_name = os.path.basename(folder_path)
        
        # Создаем специальный файл-ссылку (в реальной системе это может быть текстовый файл с путем)
        link_file_path = os.path.join(os.path.dirname(folder_path), f"LINK_{folder_name}.txt")
        with open(link_file_path, 'w', encoding='utf-8') as f:
            f.write(f"Ссылка на папку: {folder_path}\n")
            f.write(f"Добавлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        
        # Добавляем как обычный файл
        project_file = ProjectFile(
            path=link_file_path,
            name=f"📁 Доступ к папке: {folder_name}",
            is_finished=False
        )
        self.order.files.append(project_file)
        
        # Также добавляем кнопку открытия папки
        self.create_folder_access_widget(folder_path)

    def create_folder_access_widget(self, folder_path):
        """Создает виджет с кнопкой доступа к папке"""
        folder_widget = QWidget()
        folder_layout = QHBoxLayout(folder_widget)
        folder_layout.setContentsMargins(5, 2, 5, 2)
        
        folder_label = QLabel(f"📁 {os.path.basename(folder_path)}")
        folder_label.setStyleSheet("color: #DDDDDD; font-size: 12px;")
        
        open_btn = QPushButton("Открыть папку")
        open_btn.setFixedWidth(80)
        open_btn.clicked.connect(lambda: self.open_folder(folder_path))
        open_btn.setStyleSheet("""
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
        
        folder_layout.addWidget(folder_label, 1)
        folder_layout.addWidget(open_btn)
        
        # Вставляем виджет перед кнопками управления файлами
        self.c_layout.insertWidget(self.c_layout.count() - 2, folder_widget)

    def open_folder(self, folder_path):
        """Открывает папку в проводнике"""
        if os.path.exists(folder_path):
            if platform.system() == "Windows":
                os.startfile(folder_path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", folder_path])
            else:
                subprocess.Popen(["xdg-open", folder_path])
        else:
            QMessageBox.warning(self, "Папка не найдена", f"Папка {folder_path} не существует.")

    def add_file_with_storage_option(self, file_path):
        """Добавляет файл с предложением о месте хранения"""
        if not self.parent_app.app_settings:
            # Если настройки не загружены, используем прямое добавление
            self.order.files.append(ProjectFile(
                path=file_path,
                name=os.path.basename(file_path),
                is_finished=False
            ))
            return
        
        storage_mode = self.parent_app.app_settings.get('file_storage_mode', 'copy')
        
        if storage_mode == 'link':
            # Оставляем файл на месте
            final_path = file_path
        else:  # 'copy'
            # Копируем файл в папку базы данных
            db_folder = self.parent_app.app_settings.get('database_path', os.path.dirname(self.parent_app.storage.path))
            files_folder = os.path.join(db_folder, "attached_files", self.order.id)
            os.makedirs(files_folder, exist_ok=True)
            
            new_path = os.path.join(files_folder, os.path.basename(file_path))
            
            # Проверяем, не существует ли уже файл с таким именем
            counter = 1
            name, ext = os.path.splitext(os.path.basename(file_path))
            while os.path.exists(new_path):
                new_path = os.path.join(files_folder, f"{name}_{counter}{ext}")
                counter += 1
            
            try:
                shutil.copy2(file_path, new_path)
                final_path = new_path
            except Exception as e:
                QMessageBox.warning(self, "Ошибка копирования", f"Не удалось скопировать файл: {e}")
                final_path = file_path
        
        self.order.files.append(ProjectFile(
            path=final_path,
            name=os.path.basename(final_path),
            is_finished=False
        ))

    def format_number(self, num):
        """Форматирует число без точек"""
        if num == int(num):
            return str(int(num))
        return str(num).rstrip('0').rstrip('.') if '.' in str(num) else str(num)

    def toggle_contents(self):
        visible = self.content.isVisible()
        self.content.setVisible(not visible)
        # Меняем стрелочку в зависимости от состояния
        self.toggle_btn.setText("▲" if visible else "▼")

    def export_files_to_zip(self):
        """Экспортирует все файлы из заказа в ZIP архив"""
        ready_files = [f for f in self.order.files if os.path.exists(f.path)]
        if not ready_files:
            QMessageBox.information(
                self, 
                "Нет файлов", 
                "Нет файлов для экспорта."
            )
            return
        
        default_name = f"{self.order.service_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        path, _ = QFileDialog.getSaveFileName(
            self, 
            "Экспорт файлов заказа", 
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
                    "Экспорт завершен", 
                    f"Файлы успешно экспортированы в архив:\n{path}\n"
                    f"Экспортировано файлов: {len(ready_files)}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось создать архив: {e}")

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
                QMessageBox.warning(self.parent_app, "Ошибка", "Стоимость не может быть отрицательной")
                self.cost_edit.setText(self.format_number(self.order.price))
                return
            
            if new_price < self.order.total_received:
                msg_box = QMessageBox(self.parent_app)
                msg_box.setWindowTitle("Изменение стоимости")
                msg_box.setText(f"Новая стоимость ({new_price:.2f} руб.) меньше уже полученной суммы ({self.order.total_received:.2f} руб.).")
                msg_box.setInformativeText(f"Это приведет к необходимости вернуть {self.order.total_received - new_price:.2f} руб.\nПродолжить?")
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
                msg_box = QMessageBox(self.parent_app)
                msg_box.setWindowTitle("Изменение стоимости")
                msg_box.setText(f"Новая стоимость ({new_price:.2f} руб.) меньше аванса ({self.order.advance:.2f} руб.).")
                msg_box.setInformativeText(f"Это приведет к возврату части аванса в размере {diff:.2f} руб.\nПродолжить?")
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
                QMessageBox.warning(self.parent_app, "Ошибка", "Аванс не может быть отрицательным")
                self.advance_edit.setText(self.format_number(self.order.advance))
                return
            
            if new_advance > self.order.price:
                QMessageBox.warning(self.parent_app, "Ошибка", "Аванс не может превышать стоимость заказа")
                self.advance_edit.setText(self.format_number(self.order.advance))
                return
            
            diff = new_advance - self.order.advance
            
            if diff != 0:
                if diff > 0:
                    # Увеличение аванса
                    self.order.add_payment(diff, "аванс", "Дополнительный аванс")
                else:
                    # Уменьшение аванса (возврат)
                    msg_box = QMessageBox(self.parent_app)
                    msg_box.setWindowTitle("Возврат аванса")
                    msg_box.setText(f"Вы уменьшаете аванс на {abs(diff):.2f} руб. Это создаст возврат средств.")
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
                QMessageBox.warning(self.parent_app, "Ошибка", "Долг не может быть отрицательным")
                self.debt_edit.setText(self.format_number(self.order.debt))
                return
            
            if new_debt > self.order.price:
                QMessageBox.warning(self.parent_app, "Ошибка", "Долг не может превышать стоимость")
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
                    msg_box = QMessageBox(self.parent_app)
                    msg_box.setWindowTitle("Возврат средств")
                    msg_box.setText(f"Вы создаете возврат средств на сумму {abs(diff):.2f} руб.")
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
            self.parent_app.save_db()
            
        except ValueError as e:
            QMessageBox.warning(self.parent_app, "Ошибка", "Введите числовое значение")
            self.debt_edit.setText(self.format_number(self.order.debt))

    def sync_deadline(self, qdate):
        self.order.deadline = qdate.toString("dd.MM.yyyy")
        logger.info(f"Изменен срок заказа {self.order.id}: {self.order.deadline}")
        self.update_deadline_color()
        self.parent_app.save_db()
        
    def sync_order_date(self, qdate):
        new_date = qdate.toString("dd.MM.yyyy")
        # Сохраняем время если оно было
        if " " in self.order.created_at:
            time_part = self.order.created_at.split()[1]
            self.order.created_at = f"{new_date} {time_part}"
        else:
            self.order.created_at = f"{new_date} 00:00"
        logger.info(f"Изменена дата заказа {self.order.id}: {self.order.created_at}")
        self.parent_app.save_db()
    
    def update_deadline_color(self):
        """Обновление цвета поля дедлайна в зависимости от оставшегося времени"""
        if not self.order.deadline:
            self.deadline_edit.setStyleSheet("""
                QDateEdit {
                    background-color: #333333;
                    color: #FFFFFF;
                    border: 1px solid #444444;
                    padding: 4px 6px;
                    border-radius: 3px;
                    font-size: 14px;
                    font-weight: bold;
                }
                QDateEdit::drop-down { border: none; background: #444444; width: 20px; }
            """)
            return
            
        try:
            deadline_date = datetime.strptime(self.order.deadline, "%d.%m.%Y")
            today = datetime.now()
            days_left = (deadline_date - today).days
            
            common_style = """
                QDateEdit {
                    color: white;
                    padding: 4px 6px;
                    border-radius: 3px;
                    font-size: 14px;
                    font-weight: bold;
                }
                QDateEdit::drop-down { border: none; background: rgba(0,0,0,0.1); width: 20px; }
            """
            
            if days_left < 0:
                # Просрочено - красный
                self.deadline_edit.setStyleSheet(common_style + "QDateEdit { background-color: #FF4B2B; border: 1px solid #FF4B2B; }")
            elif days_left == 0:
                # Остался 1 день - красный
                self.deadline_edit.setStyleSheet(common_style + "QDateEdit { background-color: #FF4B2B; border: 1px solid #FF4B2B; }")
            elif days_left <= 2:
                # Осталось 2 дня - желтый
                self.deadline_edit.setStyleSheet(common_style + "QDateEdit { background-color: #FFA500; border: 1px solid #FFA500; }")
            else:
                # Все в порядке - стандартный
                self.deadline_edit.setStyleSheet("""
                    QDateEdit {
                        background-color: #333333;
                        color: #FFFFFF;
                        border: 1px solid #444444;
                        padding: 4px 6px;
                        border-radius: 3px;
                        font-size: 14px;
                        font-weight: bold;
                    }
                    QDateEdit::drop-down { border: none; background: #444444; width: 20px; }
                """)
        except ValueError:
            # Неверный формат даты
            self.deadline_edit.setStyleSheet("""
                QDateEdit {
                    background-color: #333333;
                    color: #FFFFFF;
                    border: 1px solid #444444;
                    padding: 4px 6px;
                    border-radius: 3px;
                    font-size: 14px;
                    font-weight: bold;
                }
                QDateEdit::drop-down { border: none; background: #444444; width: 20px; }
            """)

    def update_financial_display(self):
        # Обновляем поля ввода
        self.cost_edit.setText(self.format_number(self.order.price))
        self.advance_edit.setText(self.format_number(self.order.advance))
        self.debt_edit.setText(self.format_number(self.order.debt))
        
        # Обновляем статусы
        self.update_payment_status()

    def update_order_status(self, state):
        self.order.status = "Завершен" if state else "В работе"
        self.parent_app.save_db()

    def update_payment_status(self):
        # Если стоимость 0, статус не показываем (или пишем "Бесплатно/Не задано")
        if self.order.price == 0:
             self.payment_status.setText("")
             return

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

    def add_payment_dialog(self):
        dialog = QDialog(self.parent_app)
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
                    QMessageBox.warning(self.parent_app, "Ошибка", "Введите сумму платежа")
                    return
                    
                amount = float(amount_text)
                note = note_edit.toPlainText()
                date = date_edit.date().toString("dd.MM.yyyy")
                payment_type = type_combo.currentText()
                
                self.order.add_payment(amount, payment_type, note, date + " 00:00")
                logger.info(f"Добавлен платеж: {amount} ({payment_type}) для заказа {self.order.service_type}")
                self.update_financial_display()
                self.parent_app.save_db()
                
                if amount > 0:
                    QMessageBox.information(
                        self.parent_app,
                        "Платеж добавлен",
                        f"Платеж на сумму {amount:.2f} руб. успешно добавлен.\n"
                        f"Получено: {self.order.total_received:.2f} руб.\n"
                        f"Остаток долга: {self.order.debt:.2f} руб."
                    )
                else:
                    QMessageBox.information(
                        self.parent_app,
                        "Возврат добавлен",
                        f"Возврат на сумму {abs(amount):.2f} руб. успешно добавлен.\n"
                        f"Получено: {self.order.total_received:.2f} руб.\n"
                        f"Остаток долга: {self.order.debt:.2f} руб."
                    )
                
            except ValueError as e:
                QMessageBox.warning(self.parent_app, "Ошибка", str(e))

    def show_payments_history(self):
        dialog = PaymentsDialog(self.order, self.parent_app)
        dialog.exec()
        self.update_financial_display()

    def add_file(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self.parent_app, 
            "Выберите файлы для заказа", 
            "", 
            "Все файлы (*.*)"
        )
        if paths:
            for p in paths:
                logger.info(f"Добавление файла в заказ: {os.path.basename(p)}")
                self.add_file_with_storage_option(p)  # Используем новый метод
            self.parent_app.render_client_profile()
            self.parent_app.save_db()

    def delete_order(self):
        if not self.order:
            return
        
        msg_box = QMessageBox(self.parent_app)
        msg_box.setWindowTitle("Удаление заказа")
        msg_box.setText(f"Вы уверены, что хотите удалить заказ '{self.order.service_type}'?")
        msg_box.setIcon(QMessageBox.Icon.Question)
        
        btn_delete = msg_box.addButton("Удалить", QMessageBox.ButtonRole.YesRole)
        btn_cancel = msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        
        msg_box.exec()
        
        if msg_box.clickedButton() == btn_delete:
            logger.info(f"Удаление заказа: {self.order.service_type} (ID: {self.order.id})")
            # Находим клиента, которому принадлежит заказ
            for client in self.parent_app.clients:
                if self.order in client.orders:
                    client.orders.remove(self.order)
                    break
            
            # Перерисовываем профиль
            self.parent_app.render_client_profile()
            self.parent_app.save_db()
