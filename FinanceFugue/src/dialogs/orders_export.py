
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QWidget,
    QCheckBox,
)
from PySide6.QtCore import Qt

from ..logger import get_logger
from ..theme import ORDERS_EXPORT_DIALOG_STYLESHEET

logger = get_logger("Dialogs")

# --- ДИАЛОГ ЭКСПОРТА ЗАКАЗОВ КЛИЕНТА ---
class ClientOrdersExportDialog(QDialog):
    def __init__(self, client, parent=None):
        super().__init__(parent)
        self.client = client
        self.setWindowTitle("Экспорт заказов клиента")
        self.setFixedSize(500, 400)
        
        self.setStyleSheet(ORDERS_EXPORT_DIALOG_STYLESHEET)
        
        layout = QVBoxLayout(self)
        
        # Описание
        layout.addWidget(QLabel("Выберите заказы для экспорта:"))
        
        # Список заказов с чекбоксами
        self.orders_list = QListWidget()
        for order in self.client.orders:
            item = QListWidgetItem(f"{order.service_type} (ID: {order.id[:8]}, создан: {order.created_at})")
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, order)
            self.orders_list.addItem(item)
        
        layout.addWidget(self.orders_list)
        
        # Опции экспорта
        options_widget = QWidget()
        options_layout = QVBoxLayout(options_widget)
        
        self.include_files_cb = QCheckBox("Включить файлы заказов в экспорт")
        self.include_files_cb.setChecked(True)
        options_layout.addWidget(self.include_files_cb)
        
        layout.addWidget(options_widget)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        
        select_all_btn = QPushButton("Выбрать все")
        select_all_btn.clicked.connect(self.select_all)
        
        deselect_all_btn = QPushButton("Снять выделение")
        deselect_all_btn.clicked.connect(self.deselect_all)
        
        export_btn = QPushButton("Экспорт")
        export_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        
        buttons_layout.addWidget(select_all_btn)
        buttons_layout.addWidget(deselect_all_btn)
        buttons_layout.addStretch()
        buttons_layout.addWidget(export_btn)
        buttons_layout.addWidget(cancel_btn)
        
        layout.addLayout(buttons_layout)
    
    def select_all(self):
        for i in range(self.orders_list.count()):
            item = self.orders_list.item(i)
            item.setCheckState(Qt.CheckState.Checked)
    
    def deselect_all(self):
        for i in range(self.orders_list.count()):
            item = self.orders_list.item(i)
            item.setCheckState(Qt.CheckState.Unchecked)
    
    def get_export_data(self):
        selected_orders = []
        for i in range(self.orders_list.count()):
            item = self.orders_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected_orders.append(item.data(Qt.ItemDataRole.UserRole))
        
        return {
            'selected_orders': selected_orders,
            'include_files': self.include_files_cb.isChecked()
        }

