import uuid
from datetime import datetime

from PySide6.QtWidgets import QInputDialog, QLineEdit, QListWidgetItem, QMenu, QMessageBox
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QRunnable

from ....models import Client
from ....theme import MENU_STYLE
from ....logger import get_logger

logger = get_logger("MainWindow")


class ClientListMixin:
    def refresh_list(self):
        self.cl_list.clear()
        query = self.search_edit.text().strip().lower() if hasattr(self, "search_edit") else ""
        visible = 0

        for client in self.clients:
            if client.is_deleted:
                continue
            if query and query not in client.name.lower():
                continue
            item = QListWidgetItem(client.name)
            item.setData(Qt.ItemDataRole.UserRole, client.id)
            font = item.font()
            font.setPixelSize(13)
            font.setBold(True)
            item.setFont(font)
            self.cl_list.addItem(item)
            visible += 1

        if hasattr(self, "db_info_label"):
            total = sum(1 for c in self.clients if not c.is_deleted)
            if query:
                self.db_info_label.setText(f"Клиентов: {visible} из {total}")
            else:
                self.db_info_label.setText(f"Клиентов: {total}")

    def sort_clients(self):
        mode = self.sort_combo.currentText()

        def _last_order_date(client):
            if not client.orders:
                return datetime.min
            try:
                dates = []
                for o in client.orders:
                    d_str = o.created_at
                    if " " in d_str:
                        dt = datetime.strptime(d_str, "%d.%m.%Y %H:%M")
                    else:
                        dt = datetime.strptime(d_str, "%d.%m.%Y")
                    dates.append(dt)
                return max(dates)
            except ValueError:
                return datetime.min

        if mode == "Имя (А-Я)":
            self.clients.sort(key=lambda x: x.name.lower())
        elif mode == "Имя (Я-А)":
            self.clients.sort(key=lambda x: x.name.lower(), reverse=True)
        elif mode == "Новые заказы":
            self.clients.sort(key=_last_order_date, reverse=True)
        elif mode == "Старые заказы":
            self.clients.sort(key=_last_order_date)
        elif mode == "Срочные":
            def get_nearest_deadline(client):
                if not client.orders:
                    return datetime.max

                deadlines = []
                for o in client.orders:
                    if o.status != "Завершен" and o.deadline:
                        try:
                            dt = datetime.strptime(o.deadline, "%d.%m.%Y")
                            deadlines.append(dt)
                        except ValueError:
                            pass

                if not deadlines:
                    return datetime.max
                return min(deadlines)

            self.clients.sort(key=get_nearest_deadline)

        self.refresh_list()

    def show_client_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)

        item = self.cl_list.itemAt(pos)
        selected_items = self.cl_list.selectedItems()

        if not item:
            sort_menu = menu.addMenu("Сортировка")
            for label in ["Имя (А-Я)", "Имя (Я-А)", "Новые заказы", "Старые заказы", "Срочные"]:
                action = QAction(label, self)
                action.triggered.connect(lambda _checked=False, m=label: self._apply_sort(m))
                sort_menu.addAction(action)
            menu.exec(self.cl_list.mapToGlobal(pos))
            return

        if len(selected_items) > 1:
            delete_action = QAction(f"🗑 В корзину ({len(selected_items)})", self)
            delete_action.triggered.connect(self.delete_client)
            menu.addAction(delete_action)
        else:
            client_id = item.data(Qt.ItemDataRole.UserRole)
            client = next((c for c in self.clients if c.id == client_id), None)
            if not client:
                return

            add_order_action = QAction("➕ Добавить заказ", self)
            add_order_action.triggered.connect(lambda: self.quick_add_order(client))
            menu.addAction(add_order_action)

            settings_action = QAction("⚙ Настройки клиента", self)
            settings_action.triggered.connect(lambda: self.open_specific_client_settings(client))
            menu.addAction(settings_action)

            export_files_action = QAction("📦 Экспорт файлов (ZIP)", self)
            export_files_action.triggered.connect(
                lambda: self._export_client_files_for(client)
            )
            menu.addAction(export_files_action)

            delete_action = QAction("🗑 В корзину", self)
            delete_action.triggered.connect(lambda: self.delete_specific_client(client))
            menu.addAction(delete_action)

        menu.exec(self.cl_list.mapToGlobal(pos))

    def _apply_sort(self, mode: str):
        index = self.sort_combo.findText(mode)
        if index >= 0:
            self.sort_combo.setCurrentIndex(index)
        else:
            self.sort_clients()

    def open_specific_client_settings(self, client):
        self.current_client = client
        self.render_client_profile()
        self.open_client_settings()

    def delete_specific_client(self, client):
        self.delete_client([client])

    def delete_client(self, clients=None):
        target_clients = []
        if clients is not None:
            target_clients = list(clients)
        else:
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
            QMessageBox.warning(self, "Внимание", "Выберите клиентов для перемещения в корзину.")
            return

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Отправка в корзину")

        if len(target_clients) == 1:
            msg_box.setText(f"Отправить клиента '{target_clients[0].name}' в корзину?")
        else:
            msg_box.setText(f"Отправить {len(target_clients)} клиентов в корзину?")

        msg_box.setInformativeText("Вы сможете восстановить их позже через раздел 'Корзина'.")
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if msg_box.exec() != QMessageBox.StandardButton.Yes:
            return

        for c in target_clients:
            c.is_deleted = True

        if self.current_client in target_clients:
            self.current_client = None
            self.clear_profile_layout()

        try:
            self.save_db()
        except Exception as e:
            logger.error("Не удалось сохранить после удаления: %s", e, exc_info=True)
            QMessageBox.critical(
                self, "Ошибка",
                f"Не удалось сохранить базу данных:\n{e}",
            )
            return

        self.refresh_list()

    def add_client(self):
        name, ok = QInputDialog.getText(
            self,
            "Новый клиент",
            "Введите имя нового клиента:",
            QLineEdit.EchoMode.Normal,
            "",
        )
        if ok and name.strip():
            if any(client.name.lower() == name.strip().lower() for client in self.clients):
                QMessageBox.warning(self, "Внимание", "Клиент с таким именем уже существует.")
                return
            new_client = Client(
                id=str(uuid.uuid4()),
                name=name.strip(),
            )
            self.clients.append(new_client)
            logger.info("Добавлен новый клиент: %s (ID: %s)", new_client.name, new_client.id)
            self.save_db()
            self.refresh_list()
            for i in range(self.cl_list.count()):
                item = self.cl_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == new_client.id:
                    self.cl_list.setCurrentItem(item)
                    self.select_client(item)
                    break


class _CleanupTask(QRunnable):
    """Background walker для удаления пустых папок в attached_files.

    Внутри QThreadPool.globalInstance: не блокирует UI на больших деревьях.
    """

    def __init__(self, db_folder: str, *, logger_name: str | None = None):
        super().__init__()
        self.db_folder = db_folder
        self._logger_name = logger_name or "FinanceFugue"

    def run(self) -> None:
        import logging
        from ....services.client_deletion import cleanup_empty_attached_dirs
        log = logging.getLogger(self._logger_name)
        try:
            cleanup_empty_attached_dirs(self.db_folder, log=log)
        except Exception as e:  # noqa: BLE001
            log.error("Background cleanup failed: %s", e, exc_info=True)
