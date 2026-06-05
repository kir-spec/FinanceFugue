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

    def remove_client(self, client: Client) -> None:
        if client in self._window.clients:
            self._window.clients.remove(client)
        self._window.current_client = None
        self._window.clear_profile_layout()
        self._window.refresh_list()
        self.request_save()
