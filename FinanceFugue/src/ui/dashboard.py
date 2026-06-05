"""Виджеты панели статистики."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QWidget, QHBoxLayout

from ..theme import TRANSPARENT_FRAME_STYLE, label_stat_title, label_stat_value


def create_stat_widget(title: str, value: str, color: str) -> QFrame:
    widget = QFrame()
    widget.setStyleSheet(TRANSPARENT_FRAME_STYLE)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(10, 5, 10, 5)
    layout.setSpacing(2)

    title_label = QLabel(title)
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
        ("ВСЕГО", str(stats["total_orders"]), "#00D1FF"),
        ("ГОТОВО", str(stats["completed_orders"]), "#28A745"),
        ("АВАНС", stats["advance_display"], "#FFD700"),
        ("ВНЕСЕНО", stats["received_display"], "#28A745"),
        ("ДОЛГ", stats["debt_display"], "#FF4B2B" if stats["total_debt"] > 0 else "#28A745"),
    ]

    for title, value, color in stat_items:
        stat_widget = QWidget()
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
