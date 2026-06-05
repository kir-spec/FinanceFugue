import os
import sys

from PySide6.QtWidgets import QDialog

from .... import EULA_VERSION
from ....dialogs import EulaDialog, FirstRunDialog
from ....services.settings import (
    load_settings as load_app_settings,
    save_settings as save_app_settings,
)
from ....storage import DatabaseLoadError
from ....utils.instance_lock import InstanceLockError


class StartupMixin:
    def load_settings(self):
        """Загружает настройки приложения"""
        return load_app_settings()

    def save_settings(self):
        """Сохраняет настройки приложения"""
        save_app_settings(self.app_settings)

    def is_first_run(self):
        """Проверяет, первый ли это запуск приложения"""
        return "first_run_completed" not in self.app_settings

    def show_first_run_dialog(self):
        """Показывает диалог первого запуска"""
        dialog = FirstRunDialog(self)
        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            settings = dialog.get_settings()
            self.app_settings.update(settings)
            self.app_settings["first_run_completed"] = True
            self.save_settings()

            if "database_path" in settings:
                try:
                    self.rebind_storage(settings["database_path"], reload_clients=True)
                except (DatabaseLoadError, InstanceLockError):
                    sys.exit(1)
                self.update_dash()
                self.refresh_list()

            if settings.get("file_storage_mode") == "copy":
                db_folder = settings.get("database_path", os.path.dirname(self.storage.path))
                files_folder = os.path.join(db_folder, "attached_files")
                os.makedirs(files_folder, exist_ok=True)
            return True
        return False

    def show_eula_dialog(self) -> bool:
        dialog = EulaDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        self.app_settings["eula_accepted"] = True
        self.app_settings["eula_version"] = EULA_VERSION
        self.save_settings()
        return True
