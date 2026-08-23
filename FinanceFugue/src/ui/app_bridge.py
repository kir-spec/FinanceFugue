"""Мост между виджетами, диалогами и главным окном."""
import os

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget

from ..models import Client, ProjectFile


class AppBridge(QObject):
    save_requested = Signal()
    profile_refresh_requested = Signal()

    def __init__(self, window: QWidget):
        super().__init__(window)
        self._window = window

    @property
    def window(self) -> QWidget:
        return self._window

    @property
    def app_settings(self) -> dict:
        return self._window.app_settings

    @property
    def clients(self):
        return self._window.clients

    def storage_db_dir(self) -> str:
        return os.path.dirname(str(self._window.storage.path))

    def request_save(self) -> None:
        self.save_requested.emit()

    def request_profile_refresh(self) -> None:
        self.profile_refresh_requested.emit()

    def remove_file_from_order(self, file_obj: ProjectFile, order) -> bool:
        if file_obj in order.files:
            order.files.remove(file_obj)
            self.request_profile_refresh()
            self.request_save()
            return True
        return False

    def export_client_files(self) -> None:
        self._window.export_client_files()

    def export_client_orders(self) -> None:
        self._window.export_client_orders()

    def delete_client(self, client: Client) -> None:
        if hasattr(self._window, "delete_specific_client"):
            self._window.delete_specific_client(client)
        else:
            self.remove_client(client)

    def remove_client(self, client: Client) -> None:
        client.is_deleted = True
        self._window.current_client = None
        self._window.clear_profile_layout()
        self._window.refresh_list()
        self.request_save()

    def archive_order(self, client: Client, order) -> bool:
        success = self._window.archive_manager.archive_order(self.clients, client.id, order.id)
        if success:
            self.request_profile_refresh()
            self._window.refresh_list()
        return success

    def archive_completed_orders(self, client: Client) -> int:
        count = self._window.archive_manager.archive_completed_orders(self.clients, client.id)
        if count > 0:
            self.request_profile_refresh()
            self._window.refresh_list()
        return count

    @property
    def archive_manager(self):
        return getattr(self._window, "archive_manager", None)

    def get_archive_clients(self):
        if hasattr(self._window, "archive_manager"):
            return self._window.archive_manager.get_archive_clients()
        return []

    def archive_client(self, client: Client) -> bool:
        success = self._window.archive_manager.archive_client(self.clients, client.id)
        if success:
            self._window.current_client = None
            self._window.clear_profile_layout()
            self._window.refresh_list()
        return success
