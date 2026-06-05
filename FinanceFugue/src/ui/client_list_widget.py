"""Список клиентов с поддержкой drag & drop папок."""
import os

from PySide6.QtCore import Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QListWidget


class ClientListWidget(QListWidget):
    folder_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.DropOnly)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        folders = [
            url.toLocalFile()
            for url in urls
            if url.isLocalFile() and os.path.isdir(url.toLocalFile())
        ]
        if len(folders) == 1:
            self.folder_dropped.emit(folders[0])
            event.acceptProposedAction()
        elif len(folders) > 1:
            event.ignore()
        else:
            event.ignore()
