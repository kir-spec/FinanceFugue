import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QHBoxLayout, QMessageBox, QLabel
)
from PySide6.QtCore import Qt

from ..logger import get_logger
from ..ui.app_bridge import AppBridge
from ..services.client_deletion import delete_client_files_from_disk

logger = get_logger("Dialogs")

class RecycleBinDialog(QDialog):
    def __init__(self, bridge: AppBridge):
        super().__init__(bridge.window)
        self._bridge = bridge
        self.setWindowTitle("🗑 Корзина")
        self.resize(500, 400)
        
        layout = QVBoxLayout(self)
        
        info_label = QLabel("Удаленные клиенты находятся здесь. Вы можете восстановить их или удалить навсегда.")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.list_widget)
        
        btn_layout = QHBoxLayout()
        
        self.restore_btn = QPushButton("♻ Восстановить")
        self.restore_btn.clicked.connect(self.restore_clients)
        self.restore_btn.setStyleSheet("background-color: #2e7d32; color: white;")
        
        self.delete_btn = QPushButton("❌ Удалить навсегда")
        self.delete_btn.clicked.connect(self.delete_permanently)
        self.delete_btn.setStyleSheet("background-color: #c62828; color: white;")
        
        btn_layout.addWidget(self.restore_btn)
        btn_layout.addWidget(self.delete_btn)
        
        layout.addLayout(btn_layout)
        
        self.refresh_list()

    def refresh_list(self):
        self.list_widget.clear()
        for client in self._bridge.window.clients:
            if client.is_deleted:
                item = QListWidgetItem(client.name)
                item.setData(Qt.ItemDataRole.UserRole, client.id)
                self.list_widget.addItem(item)

    def get_selected_clients(self):
        clients = []
        for item in self.list_widget.selectedItems():
            c_id = item.data(Qt.ItemDataRole.UserRole)
            for c in self._bridge.window.clients:
                if c.id == c_id:
                    clients.append(c)
                    break
        return clients

    def restore_clients(self):
        clients = self.get_selected_clients()
        if not clients:
            return
            
        for c in clients:
            c.is_deleted = False
            
        try:
            self._bridge.window.save_db()
            self._bridge.window.refresh_list()
            self.refresh_list()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось восстановить: {e}")

    def delete_permanently(self):
        clients = self.get_selected_clients()
        if not clients:
            return
            
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Удаление навсегда")
        msg_box.setText(f"Вы собираетесь навсегда удалить {len(clients)} клиентов.")
        msg_box.setInformativeText("Это действие безвозвратно удалит все их заказы и прикрепленные файлы с диска. Продолжить?")
        msg_box.setIcon(QMessageBox.Icon.Critical)
        
        btn_yes = msg_box.addButton("Удалить безвозвратно", QMessageBox.ButtonRole.YesRole)
        msg_box.addButton("Отмена", QMessageBox.ButtonRole.NoRole)
        
        msg_box.exec()
        if msg_box.clickedButton() != btn_yes:
            return
            
        db_folder = os.path.dirname(self._bridge.window.storage.path)
        
        # УДАЛЯЕМ ФАЙЛЫ
        delete_client_files_from_disk(clients, db_folder, log=logger)
        
        # Удаляем аватарки
        for c in clients:
            if getattr(c, "avatar_path", ""):
                avatar_full_path = os.path.join(db_folder, c.avatar_path)
                if os.path.exists(avatar_full_path):
                    try:
                        os.remove(avatar_full_path)
                    except OSError:
                        pass
        
        # Удаляем из БД
        for c in clients:
            if c in self._bridge.window.clients:
                self._bridge.window.clients.remove(c)
                
        try:
            self._bridge.window.save_db()
            self.refresh_list()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить базу данных: {e}")
