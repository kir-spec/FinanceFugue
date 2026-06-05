"""Дерево файлов с поддержкой drag & drop."""
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QTreeWidget


class FileTreeWidget(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QTreeWidget.DragDropMode.DropOnly)
        self._drop_handler = None

    def set_drop_handler(self, handler):
        """handler(event, item) -> bool — принять drop."""
        self._drop_handler = handler

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
        item = self.itemAt(event.position().toPoint())
        if not item or not self._drop_handler:
            event.ignore()
            return
        if self._drop_handler(event, item):
            event.acceptProposedAction()
        else:
            event.ignore()
