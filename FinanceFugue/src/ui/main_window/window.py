import os
import sys

from PySide6.QtWidgets import QMainWindow, QMessageBox
from PySide6.QtCore import QTimer

from ... import APP_NAME, VERSION, EULA_VERSION
from ...services.settings import SettingsLoadError
from ...storage import CRMStorage, DatabaseLoadError
from ...ui.app_bridge import AppBridge
from ...utils.instance_lock import InstanceLock, InstanceLockError
from ...logger import get_logger

from .mixins import (
    StartupMixin,
    ShellMixin,
    ClientListMixin,
    ClientProfileMixin,
    ClientExportMixin,
    OrdersMixin,
    DatabaseOpsMixin,
)

logger = get_logger("MainWindow")


class FinanceFugueWindow(
    StartupMixin,
    ShellMixin,
    ClientListMixin,
    ClientProfileMixin,
    ClientExportMixin,
    OrdersMixin,
    DatabaseOpsMixin,
    QMainWindow,
):
    def __init__(self):
        super().__init__()
        logger.info("Инициализация %s %s", APP_NAME, VERSION)
        try:
            self.app_settings = self.load_settings()
        except SettingsLoadError as e:
            QMessageBox.critical(
                None,
                APP_NAME,
                f"Не удалось загрузить настройки:\n{e}\n\n"
                "Проверьте crm_settings.json или восстановите из settings_backups/.",
            )
            sys.exit(1)

        db_filename = "pro_database.json"
        if "database_path" in self.app_settings:
            db_path = self.app_settings["database_path"]
            if os.path.exists(db_path):
                db_filename = os.path.join(db_path, "pro_database.json")

        self.storage = CRMStorage(db_filename)
        self._instance_lock = InstanceLock(self.storage.path.with_suffix(".lock"))
        try:
            self._instance_lock.acquire()
        except InstanceLockError as e:
            QMessageBox.critical(None, APP_NAME, str(e))
            sys.exit(1)
        try:
            self.clients = self.storage.load()
        except DatabaseLoadError as e:
            QMessageBox.critical(
                None,
                APP_NAME,
                f"Не удалось загрузить базу данных:\n{self.storage.path}\n\n{e}\n\n"
                "Приложение будет закрыто. Проверьте файл или восстановите из резервной копии.",
            )
            sys.exit(1)
        logger.info("Загружено клиентов: %d", len(self.clients))
        self.current_client = None

        self.bridge = AppBridge(self)
        self.bridge.save_requested.connect(self.save_db)
        self.bridge.profile_refresh_requested.connect(self.render_client_profile)

        if (
            not self.app_settings.get("eula_accepted")
            or self.app_settings.get("eula_version") != EULA_VERSION
        ):
            if not self.show_eula_dialog():
                sys.exit(0)

        self.init_ui()
        self.setup_shortcuts()

        if self.is_first_run():
            if not self.show_first_run_dialog():
                sys.exit(0)

        QTimer.singleShot(800, lambda: self.check_deadline_notifications(popup=True))
        self._deadline_timer = QTimer(self)
        self._deadline_timer.setInterval(30 * 60 * 1000)
        self._deadline_timer.timeout.connect(
            lambda: self.check_deadline_notifications(popup=False)
        )
        self._deadline_timer.start()
