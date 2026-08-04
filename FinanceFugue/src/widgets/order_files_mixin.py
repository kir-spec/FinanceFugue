"""Файлы и DnD для карточки заказа."""
import os
import platform
import shutil
import subprocess
import zipfile
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QMessageBox, QFileDialog,
)
from ..models import ProjectFile
from ..logger import get_logger
from ..theme import BUTTON_COMPACT_STYLE, FOLDER_ACCESS_LABEL_STYLE

logger = get_logger("Widgets")


class OrderFilesMixin:
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
            # followlinks=False защищает от symlink-циклов и
            # ссылок, указывающих вне предполагаемой зоны.
            all_files = []
            for root, _dirs, files in os.walk(folder_path, followlinks=False):
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
        
        self._bridge.request_profile_refresh()
        self._bridge.request_save()

    def add_folder_access_button(self, folder_path):
        """Добавляет ссылку на папку в заказ (без создания файлов на диске пользователя)."""
        folder_name = os.path.basename(folder_path)
        if any(f.path == folder_path for f in self.order.files):
            return
        self.order.files.append(
            ProjectFile(
                path=folder_path,
                name=f"📁 Доступ к папке: {folder_name}",
                is_finished=False,
                is_folder=True,
            )
        )
        self.create_folder_access_widget(folder_path)

    def create_folder_access_widget(self, folder_path):
        """Создает виджет с кнопкой доступа к папке"""
        folder_widget = QWidget()
        folder_layout = QHBoxLayout(folder_widget)
        folder_layout.setContentsMargins(5, 2, 5, 2)
        
        folder_label = QLabel(f"📁 {os.path.basename(folder_path)}")
        folder_label.setStyleSheet(FOLDER_ACCESS_LABEL_STYLE)
        
        open_btn = QPushButton("Открыть папку")
        open_btn.setFixedWidth(80)
        open_btn.clicked.connect(lambda: self.open_folder(folder_path))
        open_btn.setStyleSheet(BUTTON_COMPACT_STYLE)
        
        folder_layout.addWidget(folder_label, 1)
        folder_layout.addWidget(open_btn)
        
        # Вставляем виджет перед кнопками управления файлами
        # Кнопки (btns) - это последний Layout в self.files_layout
        # insertWidget работает с виджетами. Поскольку кнопки - это Layout, они учитываются в count(), но вставка перед ними может быть сложнее
        # Проще добавить в конец, если кнопок нет, или пересобрать.
        # Но у нас кнопки всегда есть.
        
        # Попробуем вставить перед кнопками (предпоследняя позиция, т.к. stretch последний)
        count = self.files_layout.count()
        if count >= 2:
            self.files_layout.insertWidget(count - 2, folder_widget)
        else:
            self.files_layout.addWidget(folder_widget)

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
        """Добавляет файл или папку с предложением о месте хранения"""
        is_dir = os.path.isdir(file_path)
        
        if not self._bridge.app_settings:
            # Если настройки не загружены, используем прямое добавление (как ссылку)
            self.order.files.append(ProjectFile(
                path=file_path,
                name=os.path.basename(file_path),
                is_finished=False,
                is_folder=is_dir
            ))
            return
        
        storage_mode = self._bridge.app_settings.get('file_storage_mode', 'copy')
        
        if storage_mode == 'link':
            # Оставляем файл на месте
            final_path = file_path
        else:  # 'copy'
            # Копируем файл в папку базы данных
            db_folder = self._bridge.app_settings.get('database_path', self._bridge.storage_db_dir())
            files_folder = os.path.join(db_folder, "attached_files", self.order.id)
            os.makedirs(files_folder, exist_ok=True)
            
            base_name = os.path.basename(file_path)
            new_path = os.path.join(files_folder, base_name)
            
            # Проверяем, не существует ли уже файл/папка с таким именем
            counter = 1
            name, ext = os.path.splitext(base_name)
            while os.path.exists(new_path):
                new_path = os.path.join(files_folder, f"{name}_{counter}{ext}")
                counter += 1
            
            try:
                if is_dir:
                    # Копирование папки
                    shutil.copytree(file_path, new_path)
                else:
                    # Копирование файла
                    shutil.copy2(file_path, new_path)
                final_path = new_path
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Ошибка копирования",
                    f"Не удалось скопировать объект в базу данных:\n{e}\n\n"
                    "Файл не добавлен. Проверьте режим хранения или повторите позже.",
                )
                return

        self.order.files.append(ProjectFile(
            path=final_path,
            name=os.path.basename(final_path),
            is_finished=False,
            is_folder=is_dir
        ))

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

    def add_file(self):
        msg_box = QMessageBox(self._bridge.window)
        msg_box.setWindowTitle("Добавление элементов")
        msg_box.setText("Что вы хотите добавить?")
        msg_box.setIcon(QMessageBox.Icon.Question)
        
        btn_files = msg_box.addButton("Файлы", QMessageBox.ButtonRole.ActionRole)
        btn_folder = msg_box.addButton("Папку", QMessageBox.ButtonRole.ActionRole)
        btn_cancel = msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        
        msg_box.exec()
        clicked = msg_box.clickedButton()
        
        if clicked == btn_cancel:
            return

        if clicked == btn_files:
            paths, _ = QFileDialog.getOpenFileNames(
                self._bridge.window,
                "Выберите файлы для заказа",
                "",
                "Все файлы (*.*)"
            )
            if paths:
                for p in paths:
                    logger.info(f"Добавление файла в заказ: {os.path.basename(p)}")
                    self.add_file_with_storage_option(p)
                self._bridge.request_profile_refresh()
                self._bridge.request_save()
        
        elif clicked == btn_folder:
            folder = QFileDialog.getExistingDirectory(
                self._bridge.window,
                "Выберите папку для добавления"
            )
            if folder:
                logger.info(f"Добавление папки в заказ: {os.path.basename(folder)}")
                self.add_file_with_storage_option(folder)
                self._bridge.request_profile_refresh()
                self._bridge.request_save()
