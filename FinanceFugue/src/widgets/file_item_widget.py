import os
import platform
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, Signal as pyqtSignal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QMenu, QInputDialog, QLineEdit,
)

from ..logger import get_logger
from ..models import ProjectFile, Order
from ..ui.app_bridge import AppBridge
from ..utils.path_safety import is_path_within, safe_filename_candidate
from ..theme import (
    BUTTON_COMPACT_STYLE,
    BUTTON_DANGER_COMPACT_STYLE,
    FILE_NAME_FILE_STYLE,
    FILE_NAME_FOLDER_STYLE,
)


logger = get_logger("Widgets")


class FileItemWidget(QWidget):
    statusChanged = pyqtSignal()
    renameRequested = pyqtSignal(str, str)

    def __init__(self, file_obj: ProjectFile, bridge: AppBridge, order: Order):
        super().__init__()
        self.file_obj = file_obj
        self._bridge = bridge
        self._order = order
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)

        is_folder = getattr(file_obj, "is_folder", os.path.isdir(file_obj.path))
        prefix = "📁 " if is_folder else "📄 "
        self.name_label = QLabel(f"{prefix}{file_obj.name}")
        self.name_label.setStyleSheet(
            FILE_NAME_FOLDER_STYLE if is_folder else FILE_NAME_FILE_STYLE
        )
        self.name_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.name_label.customContextMenuRequested.connect(self.show_context_menu)

        btn_open = QPushButton("Открыть")
        btn_open.clicked.connect(self.open_file)
        btn_open.setStyleSheet(BUTTON_COMPACT_STYLE)

        btn_delete = QPushButton("Удалить")
        btn_delete.clicked.connect(self.delete_file)
        btn_delete.setStyleSheet(BUTTON_DANGER_COMPACT_STYLE)

        layout.addWidget(self.name_label, 1)
        layout.addWidget(btn_open)
        layout.addWidget(btn_delete)
        self.name_label.setCursor(Qt.CursorShape.PointingHandCursor)

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
            self.file_obj.name,
        )
        if not ok or not new_name.strip() or new_name == self.file_obj.name:
            return

        sanitized = safe_filename_candidate(new_name)
        if sanitized != new_name.strip() or sanitized in {"", "_"}:
            QMessageBox.warning(
                self,
                "Недопустимое имя",
                "Имя содержит запрещённые символы (``..``,\n"
                "/\\ и т. п.). Исправлено автоматически.",
            )
            return

        old_path = Path(self.file_obj.path)
        new_path = old_path.parent / sanitized
        if new_path.exists() and new_path != old_path:
            QMessageBox.warning(
                self, "Файл уже существует", f"Файл уже существует:\n{new_path}"
            )
            return

        try:
            old_path.rename(new_path)
        except OSError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось переименовать файл: {e}")
            return

        self.file_obj.path = str(new_path)
        self.file_obj.name = sanitized
        self.name_label.setText(sanitized)
        self._bridge.request_save()
        QMessageBox.information(self, "Успех", "Файл переименован")

    def mouseReleaseEvent(self, event):
        """Игнорируем клики по дочерним кнопкам, чтобы не дублировать открытие."""
        if self.childAt(event.position().toPoint()) is None:
            self.open_file()
        super().mouseReleaseEvent(event)

    def open_file(self):
        try:
            path = self.file_obj.path
            
            # Resolve relative paths
            if not os.path.isabs(path):
                db_folder = self._bridge.app_settings.get('database_path', self._bridge.storage_db_dir())
                path = os.path.normpath(os.path.join(db_folder, path))
            
            # Auto-healing: if absolute path is broken, check if it exists in the relative attached_files
            if not os.path.exists(path):
                db_folder = self._bridge.app_settings.get('database_path', self._bridge.storage_db_dir())
                fallback_path = os.path.join(db_folder, "attached_files", self._order.id, os.path.basename(path))
                if os.path.exists(fallback_path):
                    path = fallback_path
                    # Automatically heal the link (convert to relative)
                    self.file_obj.path = os.path.join("attached_files", self._order.id, os.path.basename(path)).replace('\\', '/')
                    self._bridge.request_save()

            if not os.path.exists(path):
                QMessageBox.warning(
                    self,
                    "Объект не найден",
                    f"Объект '{self.file_obj.name}' не найден по пути:\n{path}",
                )
                return

            # Защита от symlink-атак: если путь — symlink,
            # резолвим и проверяем, что цель не ушла за пределы
            # ожидаемой зоны (директория файла из БД).
            try:
                if os.path.islink(path):
                    expected_dir = os.path.dirname(path) or "."
                    if not is_path_within(path, expected_dir):
                        QMessageBox.warning(
                            self, "Небезопасный путь",
                            f"Файл '{self.file_obj.name}' является символической ссылкой\n"
                            f"за пределы ожидаемой директории. Открытие заблокировано.",
                        )
                        logger.warning(
                            "Отклонён symlink при открытии: %s", path
                        )
                        return
            except OSError as e:
                logger.warning("Symlink-проверка не удалась для %s: %s", path, e)

            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except OSError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть объект: {e}")

    def delete_file(self):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Удаление файла")
        msg_box.setText(
            f"Вы уверены, что хотите удалить файл '{self.file_obj.name}' из заказа?"
        )
        msg_box.setIcon(QMessageBox.Icon.Question)
        btn_delete = msg_box.addButton("Удалить", QMessageBox.ButtonRole.YesRole)
        msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        msg_box.exec()
        if msg_box.clickedButton() == btn_delete:
            self._bridge.remove_file_from_order(self.file_obj, self._order)
