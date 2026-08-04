"""Глобальный менеджер файлов."""
import os
import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QTreeWidgetItem, QPushButton, QMessageBox,
)

from .. import APP_NAME
from ..models import ProjectFile
from ..ui.file_tree_widget import FileTreeWidget
from ..theme import FILE_MANAGER_DIALOG_STYLESHEET


class FileManagerDialog(QDialog):
    ROLE_KIND = Qt.ItemDataRole.UserRole
    ROLE_CLIENT_ID = Qt.ItemDataRole.UserRole + 1
    ROLE_ORDER_ID = Qt.ItemDataRole.UserRole + 2
    ROLE_FILE_PATH = Qt.ItemDataRole.UserRole + 3

    def __init__(self, window, parent=None):
        super().__init__(parent or window)
        self._window = window
        self.setWindowTitle(f"{APP_NAME} — менеджер файлов")
        self.resize(720, 520)
        self.setMinimumSize(560, 400)
        self.setStyleSheet(FILE_MANAGER_DIALOG_STYLESHEET)

        layout = QVBoxLayout(self)
        hint = QLabel(
            "Дерево клиентов, заказов и файлов. Двойной клик — открыть файл или папку. "
            "Перетащите файлы на клиента или заказ для добавления."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.tree = FileTreeWidget()
        self.tree.setHeaderLabels(["Имя", "Путь"])
        self.tree.setColumnWidth(0, 280)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        self.tree.set_drop_handler(self._handle_drop)
        layout.addWidget(self.tree)

        buttons = QHBoxLayout()
        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self._populate)
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(refresh_btn)
        buttons.addStretch()
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        self._populate()

    def _populate(self):
        self.tree.clear()
        for client in self._window.clients:
            client_item = QTreeWidgetItem([f"👤 {client.name}", ""])
            client_item.setData(0, self.ROLE_KIND, "client")
            client_item.setData(0, self.ROLE_CLIENT_ID, client.id)
            self.tree.addTopLevelItem(client_item)

            for order in client.orders:
                order_item = QTreeWidgetItem([f"📋 {order.service_type}", order.deadline or ""])
                order_item.setData(0, self.ROLE_KIND, "order")
                order_item.setData(0, self.ROLE_CLIENT_ID, client.id)
                order_item.setData(0, self.ROLE_ORDER_ID, order.id)
                client_item.addChild(order_item)

                for file in order.files:
                    icon = "📁" if file.is_folder or os.path.isdir(file.path) else "📄"
                    file_item = QTreeWidgetItem([f"{icon} {file.name}", file.path])
                    file_item.setData(0, self.ROLE_KIND, "file")
                    file_item.setData(0, self.ROLE_FILE_PATH, file.path)
                    order_item.addChild(file_item)

            client_item.setExpanded(True)
        self.tree.expandAll()

    def _on_double_click(self, item: QTreeWidgetItem, _column: int):
        if item.data(0, self.ROLE_KIND) == "file":
            self._open_path(item.data(0, self.ROLE_FILE_PATH))

    def _open_path(self, path: str):
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, APP_NAME, "Файл или папка не найдены.")
            return
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.run(["open", path], check=False)
            else:
                subprocess.run(["xdg-open", path], check=False)
        except OSError as e:
            QMessageBox.warning(self, APP_NAME, f"Не удалось открыть:\n{e}")

    def _resolve_drop_target(self, item: QTreeWidgetItem):
        kind = item.data(0, self.ROLE_KIND)
        client_id = item.data(0, self.ROLE_CLIENT_ID)
        order_id = item.data(0, self.ROLE_ORDER_ID)

        if kind == "file":
            parent_order = item.parent()
            parent_client = parent_order.parent() if parent_order else None
            if not parent_order or not parent_client:
                QMessageBox.information(
                    self, APP_NAME, "Перетащите файл на клиента или заказ."
                )
                return None, None
            order_id = parent_order.data(0, self.ROLE_ORDER_ID)
            client_id = parent_client.data(0, self.ROLE_CLIENT_ID)
        elif kind == "client":
            order_id = None

        if not client_id:
            return None, None

        client = next((c for c in self._window.clients if c.id == client_id), None)
        if not client:
            return None, None

        if order_id:
            order = next((o for o in client.orders if o.id == order_id), None)
        elif client.orders:
            order = client.orders[0]
        else:
            QMessageBox.information(
                self, APP_NAME, "Сначала создайте заказ для клиента, затем добавьте файлы."
            )
            return None, None
        return client, order

    def _handle_drop(self, event, item: QTreeWidgetItem) -> bool:
        client, order = self._resolve_drop_target(item)
        if not order:
            return False

        from ..utils.path_safety import safe_resolve_within

        db_folder = os.path.dirname(self._window.storage.path) or os.getcwd()
        allowed_root = os.path.join(db_folder, "attached_files")
        existing_paths = {f.path for f in order.files}

        added = 0
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if not path or not os.path.exists(path):
                continue
            # Не позволяем drop произвольных путей, если они уходят
            # за пределы attached_files — отказ вместо молчаливого
            # сохранения ссылки на C:\Windows\System32.
            safe = safe_resolve_within(path, allowed_root)
            if safe is None:
                QMessageBox.warning(
                    self, APP_NAME,
                    f"Путь вне папки базы данных:\n{path}\n\n"
                    f"Допустимо: {allowed_root}",
                )
                continue
            if os.path.isfile(path):
                if path not in existing_paths:
                    order.files.append(ProjectFile(path=path, name=os.path.basename(path)))
                    existing_paths.add(path)
                    added += 1
            elif os.path.isdir(path):
                for root, _dirs, files in os.walk(path, followlinks=False):
                    for name in files:
                        file_path = os.path.join(root, name)
                        if safe_resolve_within(file_path, allowed_root) is None:
                            continue
                        if file_path not in existing_paths:
                            order.files.append(ProjectFile(path=file_path, name=name))
                            existing_paths.add(file_path)
                            added += 1

        if not added:
            return False

        self._window.save_db()
        self._populate()
        if self._window.current_client and self._window.current_client.id == client.id:
            self._window.render_client_profile()
        return True
