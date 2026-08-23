from datetime import datetime
from collections import defaultdict
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QPushButton, QHBoxLayout, QLabel
)

from ..services.archive import ArchiveManager
from ..theme import DB_INFO_LABEL_STYLE, MAIN_WINDOW_STYLESHEET

class ArchiveViewerDialog(QDialog):
    def __init__(self, archive_source=None, parent=None):
        super().__init__(parent)
        if archive_source is None:
            from ..storage import CRMStorage
            self.archive_manager = ArchiveManager(CRMStorage())
        elif isinstance(archive_source, ArchiveManager):
            self.archive_manager = archive_source
        elif hasattr(archive_source, "get_archive_clients"):
            self.archive_manager = archive_source
        elif hasattr(archive_source, "archive_manager"):
            self.archive_manager = archive_source.archive_manager
        elif hasattr(archive_source, "storage"):
            self.archive_manager = ArchiveManager(archive_source.storage)
        elif hasattr(archive_source, "window") and hasattr(archive_source.window, "storage"):
            self.archive_manager = ArchiveManager(archive_source.window.storage)
        else:
            self.archive_manager = ArchiveManager(archive_source)

        self.setWindowTitle("🗄 Архив (Холодное хранилище)")
        self.resize(800, 600)
        self.setStyleSheet(MAIN_WINDOW_STYLESHEET)
        
        layout = QVBoxLayout(self)
        
        info_label = QLabel("Архив хранит все завершенные заказы и закрытых клиентов для вечной отчетности.\nДанные доступны только для чтения.")
        info_label.setStyleSheet(DB_INFO_LABEL_STYLE)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Год / Месяц / Заказ", "Клиент", "Сумма", "Валюта"])
        self.tree.setColumnWidth(0, 350)
        self.tree.setColumnWidth(1, 150)
        self.tree.setColumnWidth(2, 120)
        layout.addWidget(self.tree)
        
        self.load_archive()
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.reject)
        close_btn.setMinimumWidth(100)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)

    def load_archive(self):
        clients = self.archive_manager.get_archive_clients()
        
        # Группируем заказы: Год -> Месяц -> Список заказов
        # orders_tree[year][month] = [(order, client), ...]
        orders_tree = defaultdict(lambda: defaultdict(list))
        
        for client in clients:
            for order in client.orders:
                year = "Неизвестно"
                month_name = "Неизвестно"
                
                if order.created_at:
                    try:
                        d = datetime.strptime(order.created_at.split()[0], "%d.%m.%Y")
                        year = str(d.year)
                        months = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
                        month_name = f"{d.month:02d}. {months[d.month-1]}"
                    except ValueError:
                        pass
                
                orders_tree[year][month_name].append((order, client))
                
        # Заполняем QTreeWidget
        for year in sorted(orders_tree.keys(), reverse=True):
            year_item = QTreeWidgetItem(self.tree, [f"📁 {year} год", "", "", ""])
            year_item.setExpanded(True)
            
            for month in sorted(orders_tree[year].keys(), reverse=True):
                month_orders = orders_tree[year][month]
                month_total = sum(o.price for o, c in month_orders)
                
                month_item = QTreeWidgetItem(year_item, [f"📁 {month} ({len(month_orders)} заказов)", "", f"{month_total:,.2f}", ""])
                month_item.setExpanded(False)
                
                for order, client in month_orders:
                    order_item = QTreeWidgetItem(month_item, [
                        f"📄 {order.service_type}",
                        client.name,
                        f"{order.price:,.2f}",
                        order.currency
                    ])
                    # order_item.setData(0, Qt.ItemDataRole.UserRole, order.id)
                    
