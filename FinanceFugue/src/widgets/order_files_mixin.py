"""Файлы и DnD для карточки заказа."""
import os
import platform
import subprocess
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QMessageBox, QFileDialog, QProgressDialog
)
from ..models import ProjectFile
from ..logger import get_logger
from ..theme import BUTTON_COMPACT_STYLE, FOLDER_ACCESS_LABEL_STYLE
from ..utils.file_worker import CopyWorkerThread, ZipWorkerThread

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
        if files_to_add:
            self.add_multiple_files_with_storage_option(files_to_add)

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

    def add_multiple_files_with_storage_option(self, file_paths):
        """Пакетное добавление файлов с проверкой режима хранения и асинхронным копированием."""
        if not file_paths:
            return
            
        if not self._bridge.app_settings:
            # Если настройки не загружены, используем прямое добавление (как ссылку)
            for path in file_paths:
                self.order.files.append(ProjectFile(
                    path=path,
                    name=os.path.basename(path),
                    is_finished=False,
                    is_folder=os.path.isdir(path)
                ))
            self._bridge.request_profile_refresh()
            self._bridge.request_save()
            return
            
        storage_mode = self._bridge.app_settings.get('file_storage_mode', 'copy')
        
        if storage_mode == 'link':
            # Оставляем файлы на месте (храним абсолютные пути)
            for path in file_paths:
                self.order.files.append(ProjectFile(
                    path=path,
                    name=os.path.basename(path),
                    is_finished=False,
                    is_folder=os.path.isdir(path)
                ))
            self._bridge.request_profile_refresh()
            self._bridge.request_save()
        else:  # 'copy'
            # Запускаем асинхронное копирование с относительными путями
            db_folder = self._bridge.app_settings.get('database_path', self._bridge.storage_db_dir())
            tasks = []
            for path in file_paths:
                tasks.append({
                    'path': path,
                    'is_dir': os.path.isdir(path)
                })
                
            progress = QProgressDialog("Копирование файлов в базу...", "Отмена", 0, len(tasks), self._bridge.window)
            progress.setWindowTitle("Добавление файлов")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            
            self.copy_thread = CopyWorkerThread(tasks, db_folder, self.order.id)
            
            def on_progress(current, total):
                progress.setValue(current)
                
            def on_one_finished(orig_path, final_rel_path, is_dir):
                self.order.files.append(ProjectFile(
                    path=final_rel_path,
                    name=os.path.basename(final_rel_path),
                    is_finished=False,
                    is_folder=is_dir
                ))
                
            def on_all_finished():
                progress.setValue(len(tasks))
                self._bridge.request_profile_refresh()
                self._bridge.request_save()
                
            def on_error(err):
                QMessageBox.warning(self, "Ошибка копирования", f"Возникла ошибка:\n{err}")
                on_all_finished()
                
            progress.canceled.connect(self.copy_thread.cancel)
            self.copy_thread.progress.connect(on_progress)
            self.copy_thread.finished_one.connect(on_one_finished)
            self.copy_thread.finished_all.connect(on_all_finished)
            self.copy_thread.error.connect(on_error)
            
            # Start background thread
            progress.show()
            self.copy_thread.start()

    def export_files_to_zip(self):
        """Экспортирует все файлы из заказа в ZIP архив асинхронно"""
        # Сначала резолвим пути, чтобы знать абсолютные пути к файлам для экспорта
        db_folder = self._bridge.app_settings.get('database_path', self._bridge.storage_db_dir())
        
        files_info = []
        for f in self.order.files:
            if not f.path:
                continue
            # Резолвим путь
            if os.path.isabs(f.path):
                abs_path = f.path
            else:
                abs_path = os.path.normpath(os.path.join(db_folder, f.path))
                
            if os.path.exists(abs_path):
                files_info.append({
                    'abs_path': abs_path,
                    'arcname': f.name
                })
                
        if not files_info:
            QMessageBox.information(self, "Нет файлов", "Нет файлов для экспорта или они не найдены на диске.")
            return
        
        default_name = f"{self.order.service_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        path, _ = QFileDialog.getSaveFileName(
            self, 
            "Экспорт файлов заказа", 
            default_name,
            "ZIP архивы (*.zip)"
        )
        
        if path:
            progress = QProgressDialog("Создание ZIP архива...", "Отмена", 0, len(files_info), self._bridge.window)
            progress.setWindowTitle("Экспорт файлов")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            
            self.zip_thread = ZipWorkerThread(files_info, path)
            
            def on_progress(current, total):
                progress.setValue(current)
                
            def on_finished(zip_path):
                progress.setValue(len(files_info))
                QMessageBox.information(
                    self, 
                    "Экспорт завершен", 
                    f"Файлы успешно экспортированы в архив:\n{zip_path}\n"
                    f"Экспортировано элементов: {len(files_info)}"
                )
                
            def on_error(err):
                QMessageBox.critical(self, "Ошибка", f"Не удалось создать архив: {err}")
                
            progress.canceled.connect(self.zip_thread.cancel)
            self.zip_thread.progress.connect(on_progress)
            self.zip_thread.finished.connect(on_finished)
            self.zip_thread.error.connect(on_error)
            
            progress.show()
            self.zip_thread.start()

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
                self.add_multiple_files_with_storage_option(paths)
        
        elif clicked == btn_folder:
            folder = QFileDialog.getExistingDirectory(
                self._bridge.window,
                "Выберите папку для добавления"
            )
            if folder:
                logger.info("Добавление папки в заказ: %s", os.path.basename(folder))
                self.add_multiple_files_with_storage_option([folder])
