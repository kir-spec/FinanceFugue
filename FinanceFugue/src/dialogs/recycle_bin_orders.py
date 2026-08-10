import os
import shutil
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QHBoxLayout, QMessageBox, QLabel
)
from PySide6.QtCore import Qt

from ..models import Client
from ..logger import get_logger
from ..ui.app_bridge import AppBridge
from ..services.client_deletion import is_safe_to_delete

logger = get_logger("Dialogs")

class RecycleBinOrdersDialog(QDialog):
    def __init__(self, client: Client, bridge: AppBridge):
        super().__init__(bridge.window)
        self.client = client
        self._bridge = bridge
        self.setWindowTitle(f"🗑 Корзина заказов: {client.name}")
        self.resize(500, 400)
        
        layout = QVBoxLayout(self)
        
        info_label = QLabel("Удаленные заказы находятся здесь. Вы можете восстановить их или удалить навсегда, освободив место на диске.")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.list_widget)
        
        btn_layout = QHBoxLayout()
        
        self.restore_btn = QPushButton("♻ Восстановить")
        self.restore_btn.clicked.connect(self.restore_orders)
        self.restore_btn.setStyleSheet("background-color: #2e7d32; color: white; padding: 5px;")
        
        self.delete_btn = QPushButton("❌ Удалить навсегда")
        self.delete_btn.clicked.connect(self.delete_permanently)
        self.delete_btn.setStyleSheet("background-color: #c62828; color: white; padding: 5px;")
        
        btn_layout.addWidget(self.restore_btn)
        btn_layout.addWidget(self.delete_btn)
        
        layout.addLayout(btn_layout)
        
        self.refresh_list()

    def refresh_list(self):
        self.list_widget.clear()
        for order in self.client.orders:
            if order.is_deleted:
                item = QListWidgetItem(f"{order.service_type} ({order.price} {order.currency})")
                item.setData(Qt.ItemDataRole.UserRole, order.id)
                self.list_widget.addItem(item)

    def get_selected_orders(self):
        orders = []
        for item in self.list_widget.selectedItems():
            o_id = item.data(Qt.ItemDataRole.UserRole)
            for o in self.client.orders:
                if o.id == o_id:
                    orders.append(o)
                    break
        return orders

    def restore_orders(self):
        orders = self.get_selected_orders()
        if not orders:
            return
            
        for o in orders:
            o.is_deleted = False
            
        try:
            self._bridge.request_save()
            self._bridge.request_profile_refresh()
            self.refresh_list()
            # Если корзина пуста, закрываем диалог
            if not any(o.is_deleted for o in self.client.orders):
                self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось восстановить: {e}")

    def delete_permanently(self):
        orders = self.get_selected_orders()
        if not orders:
            return
            
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Удаление навсегда")
        msg_box.setText(f"Вы собираетесь навсегда удалить {len(orders)} заказов.")
        msg_box.setInformativeText("Это действие безвозвратно удалит все прикрепленные файлы заказов с диска. Продолжить?")
        msg_box.setIcon(QMessageBox.Icon.Critical)
        
        btn_yes = msg_box.addButton("Удалить безвозвратно", QMessageBox.ButtonRole.YesRole)
        msg_box.addButton("Отмена", QMessageBox.ButtonRole.NoRole)
        
        msg_box.exec()
        if msg_box.clickedButton() != btn_yes:
            return
            
        db_folder = os.path.dirname(self._bridge.window.storage.path)
        
        # УДАЛЯЕМ ФАЙЛЫ
        for o in orders:
            for file in o.files:
                if not os.path.exists(file.path):
                    continue
                if not is_safe_to_delete(file.path, db_folder):
                    continue
                try:
                    if getattr(file, "is_folder", False) or os.path.isdir(file.path):
                        shutil.rmtree(file.path)
                    else:
                        os.remove(file.path)
                except OSError as e:
                    logger.error("Не удалось удалить %s: %s", file.path, e)
                    
            order_dir = os.path.join(db_folder, "attached_files", o.id)
            if os.path.exists(order_dir):
                try:
                    shutil.rmtree(order_dir)
                    logger.info("Удалена папка заказа: %s", order_dir)
                except Exception as e:
                    logger.error("Ошибка удаления папки %s: %s", order_dir, e)
        
        # Удаляем из БД
        for o in orders:
            if o in self.client.orders:
                self.client.orders.remove(o)
                
        try:
            self._bridge.request_save()
            self._bridge.request_profile_refresh()
            self.refresh_list()
            # Если корзина пуста, закрываем диалог
            if not any(o.is_deleted for o in self.client.orders):
                self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить базу данных: {e}")
