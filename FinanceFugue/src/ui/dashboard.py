"""Виджеты панели статистики."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QWidget, QHBoxLayout

from ..theme import TRANSPARENT_FRAME_STYLE, label_stat_title, label_stat_value


def create_stat_widget(title: str, value: str, color: str, on_click=None) -> QFrame:
    widget = QFrame()
    if on_click:
        widget.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
            }
            QFrame:hover {
                background-color: #2D2D2D;
                border: 1px solid #4D4D4D;
            }
        """)
        widget.setCursor(Qt.CursorShape.PointingHandCursor)
        widget.mousePressEvent = lambda e: on_click() if e.button() == Qt.MouseButton.LeftButton else None
    else:
        widget.setStyleSheet(TRANSPARENT_FRAME_STYLE)
    
    # Подсказки для глобальной статистики
    tooltips = {
        "В РАБОТЕ": "Количество активных (не завершенных) заказов",
        "ВЫПОЛНЕНО": "Количество успешно завершенных заказов",
        "АВАНСЫ": "Общая сумма полученных авансов по активным заказам",
        "ДОЛГИ": "Общая сумма задолженностей от клиентов",
        "КАССА": "Общая сумма всех полученных платежей (нажмите для ручной корректировки кассы)"
    }
    for k, v in tooltips.items():
        if k in title:
            widget.setToolTip(v)
            break
        
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(10, 5, 10, 5)
    layout.setSpacing(2)

    display_title = f"{title} ✏️" if on_click else title
    title_label = QLabel(display_title)
    title_label.setStyleSheet(label_stat_title())
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    value_label = QLabel(value)
    value_label.setStyleSheet(label_stat_value(color, size=13))
    value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    layout.addWidget(title_label)
    layout.addWidget(value_label)
    return widget


def create_client_stats_widget(stats: dict) -> QFrame:
    widget = QFrame()
    widget.setStyleSheet(TRANSPARENT_FRAME_STYLE + " QFrame { padding: 0px; }")

    layout = QHBoxLayout(widget)
    layout.setSpacing(15)
    layout.setContentsMargins(0, 0, 0, 0)

    stat_items = [
        ("ВСЕГО", str(stats["total_orders"]), "#00D1FF", "Всего заказов у данного клиента"),
        ("ГОТОВО", str(stats["completed_orders"]), "#28A745", "Выполненные заказы клиента"),
        ("АВАНС", stats["advance_display"], "#FFD700", "Сумма авансов по заказам в работе"),
        ("ВНЕСЕНО", stats["received_display"], "#28A745", "Общая сумма оплат от клиента"),
        ("ДОЛГ", stats["debt_display"], "#FF4B2B" if stats["total_debt"] > 0 else "#28A745", "Текущий долг клиента"),
    ]

    for title, value, color, tooltip in stat_items:
        stat_widget = QWidget()
        stat_widget.setToolTip(tooltip)
        stat_layout = QVBoxLayout(stat_widget)
        stat_layout.setContentsMargins(0, 0, 0, 0)
        stat_layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setStyleSheet(label_stat_title())

        value_label = QLabel(value)
        value_label.setStyleSheet(label_stat_value(color))

        stat_layout.addWidget(title_label)
        stat_layout.addWidget(value_label)
        layout.addWidget(stat_widget)

    layout.addStretch()
    return widget

