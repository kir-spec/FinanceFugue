import pyqtgraph as pg
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton
)

from ..ui.app_bridge import AppBridge
from ..services.analytics import calculate_monthly_revenue, get_top_clients, get_funnel_stats
from ..theme import DIALOG_STYLESHEET

class AnalyticsDialog(QDialog):
    def __init__(self, bridge: AppBridge):
        super().__init__(bridge.window)
        self.bridge = bridge
        self.setWindowTitle("Интерактивная Аналитика")
        self.resize(1000, 700)
        self.setStyleSheet(DIALOG_STYLESHEET)
        
        # Настройка цветов pyqtgraph
        # Пытаемся получить тему из настроек, чтобы адаптировать графики
        is_light = self.bridge.window.app_settings.get("theme", "dark") == "light"
        
        if is_light:
            pg.setConfigOption('background', '#F5F5F5')
            pg.setConfigOption('foreground', '#333333')
            self.color_rev = (0, 168, 204) # #00A8CC
            self.color_debt = (220, 53, 69) # #DC3545
            self.color_funnel = [(0, 120, 215), (40, 167, 69), (102, 102, 102)]
        else:
            pg.setConfigOption('background', '#1E1E1E')
            pg.setConfigOption('foreground', '#DDDDDD')
            self.color_rev = (0, 209, 255) # #00D1FF
            self.color_debt = (220, 53, 69) # #DC3545
            self.color_funnel = [(0, 120, 215), (40, 167, 69), (102, 102, 102)]

        main_layout = QVBoxLayout(self)
        
        # Верхний ряд графиков
        top_row = QHBoxLayout()
        self.plot_revenue = pg.PlotWidget(title="Доходы и Долги по месяцам")
        self.plot_revenue.showGrid(x=False, y=True, alpha=0.3)
        top_row.addWidget(self.plot_revenue, stretch=2)
        
        self.plot_funnel = pg.PlotWidget(title="Воронка заказов")
        self.plot_funnel.showGrid(x=False, y=True, alpha=0.3)
        top_row.addWidget(self.plot_funnel, stretch=1)
        
        main_layout.addLayout(top_row, stretch=1)
        
        # Нижний ряд графиков
        bottom_row = QHBoxLayout()
        self.plot_top = pg.PlotWidget(title="Топ-5 Клиентов (Выручка)")
        self.plot_top.showGrid(x=False, y=True, alpha=0.3)
        bottom_row.addWidget(self.plot_top)
        
        main_layout.addLayout(bottom_row, stretch=1)
        
        # Кнопка закрытия
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.accept)
        main_layout.addWidget(btn_close)
        
        self.render_charts()
        
    def render_charts(self):
        clients = self.bridge.clients
        
        # 1. Доходы по месяцам
        months, revenues, debts = calculate_monthly_revenue(clients)
        if months:
            x = list(range(len(months)))
            
            # Настройка оси X для месяцев
            axis = self.plot_revenue.getAxis('bottom')
            axis.setTicks([[(i, m) for i, m in enumerate(months)]])
            
            # Рисуем выручку
            bar_rev = pg.BarGraphItem(x=[i - 0.2 for i in x], height=revenues, width=0.3, brush=pg.mkBrush(*self.color_rev))
            self.plot_revenue.addItem(bar_rev)
            
            # Рисуем долги
            bar_debt = pg.BarGraphItem(x=[i + 0.2 for i in x], height=debts, width=0.3, brush=pg.mkBrush(*self.color_debt))
            self.plot_revenue.addItem(bar_debt)
            
        # 2. Топ клиентов
        top_clients = get_top_clients(clients)
        if top_clients:
            names = [c[0] for c in top_clients]
            totals = [c[1] for c in top_clients]
            x_top = list(range(len(names)))
            
            axis_top = self.plot_top.getAxis('bottom')
            axis_top.setTicks([[(i, n) for i, n in enumerate(names)]])
            
            bar_top = pg.BarGraphItem(x=x_top, height=totals, width=0.5, brush=pg.mkBrush(*self.color_rev))
            self.plot_top.addItem(bar_top)
            
        # 3. Воронка заказов
        funnel_stats = get_funnel_stats(clients)
        labels = ["В работе", "Завершен", "Удален"]
        counts = [funnel_stats[labels[0]], funnel_stats[labels[1]], funnel_stats[labels[2]]]
        
        x_funnel = list(range(3))
        axis_funnel = self.plot_funnel.getAxis('bottom')
        axis_funnel.setTicks([[(i, labels[i]) for i in x_funnel]])
        
        for i, count in enumerate(counts):
            bar_f = pg.BarGraphItem(x=[i], height=[count], width=0.6, brush=pg.mkBrush(*self.color_funnel[i]))
            self.plot_funnel.addItem(bar_f)
