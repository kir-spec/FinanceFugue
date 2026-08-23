# -*- coding: utf-8 -*-
from enum import Enum
from typing import Dict, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QMessageBox
)
from PySide6.QtCore import Qt
from ..theme import DIALOG_STYLESHEET, COLOR_SUCCESS, COLOR_DANGER, COLOR_BORDER, COLOR_ACCENT


class DeletionFinanceChoice(Enum):
    CANCEL = 0
    PURGE_FINANCES = 1   # Удалить и списать из кассы
    KEEP_FINANCES = 2    # Удалить, но сохранить сумму в кассе


class DeletionFinanceDialog(QDialog):
    """
    Интерактивный диалог удаления клиента или заказа
    с явным выбором: сохранить полученные деньги в кассе или списать их.
    """
    def __init__(
        self,
        parent,
        item_type: str,
        item_name: str,
        total_received_map: Dict[str, float],
        debt_map: Optional[Dict[str, float]] = None
    ):
        super().__init__(parent)
        self.choice = DeletionFinanceChoice.CANCEL
        self.setWindowTitle(f"Удаление {item_type}")
        self.setFixedWidth(480)
        self.setStyleSheet(DIALOG_STYLESHEET + f"""
            QLabel {{ color: #FFFFFF; font-size: 11pt; }}
            QFrame#infoBox {{
                background-color: #252525;
                border: 1px solid {COLOR_BORDER};
                border-radius: 6px;
                padding: 10px;
            }}
            QPushButton#keepBtn {{
                background-color: #1E7E34; color: #FFFFFF; font-weight: bold;
                padding: 10px 14px; border-radius: 5px; font-size: 11pt; text-align: center;
                border: 1px solid #28A745;
            }}
            QPushButton#keepBtn:hover {{ background-color: #28A745; }}
            QPushButton#purgeBtn {{
                background-color: #A71D2A; color: #FFFFFF; font-weight: bold;
                padding: 10px 14px; border-radius: 5px; font-size: 11pt; text-align: center;
                border: 1px solid #DC3545;
            }}
            QPushButton#purgeBtn:hover {{ background-color: #DC3545; }}
            QPushButton#cancelBtn {{
                background-color: #2D2D2D; color: #DDDDDD;
                padding: 8px 16px; border-radius: 4px; font-size: 10pt;
                border: 1px solid #3D3D3D;
            }}
            QPushButton#cancelBtn:hover {{ background-color: #3D3D3D; color: #FFFFFF; }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        title_lbl = QLabel(f"🗑 Отправить {item_type} «<b>{item_name}</b>» в корзину?")
        title_lbl.setWordWrap(True)
        layout.addWidget(title_lbl)

        # Блок финансовых данных
        info_box = QFrame()
        info_box.setObjectName("infoBox")
        info_l = QVBoxLayout(info_box)
        info_l.setSpacing(4)
        info_l.setContentsMargins(10, 8, 10, 8)

        received_strs = [f"<b>{val:,.2f} {curr}</b>" for curr, val in total_received_map.items() if val > 0]
        received_text = ", ".join(received_strs) if received_strs else "0.00 RUB"

        debts_strs = [f"<b>{val:,.2f} {curr}</b>" for curr, val in (debt_map or {}).items() if val > 0]
        debts_text = ", ".join(debts_strs) if debts_strs else "нет"

        info_l.addWidget(QLabel(f"💰 <b>Получено оплат (в кассе):</b> {received_text}"))
        if debts_strs:
            info_l.addWidget(QLabel(f"💳 <b>Неоплаченный долг:</b> {debts_text}"))

        layout.addWidget(info_box)

        prompt_lbl = QLabel("Как поступить с полученными деньгами в кассе?")
        prompt_lbl.setStyleSheet(f"color: {COLOR_ACCENT}; font-weight: bold;")
        layout.addWidget(prompt_lbl)

        # Вариант 1: Сохранить в кассе
        btn_keep = QPushButton(f"💵 Сохранить {received_text} в кассе\n(оставить в общем балансе как доход)")
        btn_keep.setObjectName("keepBtn")
        btn_keep.clicked.connect(self._choose_keep)
        layout.addWidget(btn_keep)

        # Вариант 2: Списать из кассы
        btn_purge = QPushButton(f"🗑 Списать и убрать из кассы\n(аннулировать все платежи вместе с {item_type})")
        btn_purge.setObjectName("purgeBtn")
        btn_purge.clicked.connect(self._choose_purge)
        layout.addWidget(btn_purge)

        layout.addSpacing(6)

        # Кнопка Отмена
        btn_cancel = QPushButton("Отмена")
        btn_cancel.setObjectName("cancelBtn")
        btn_cancel.clicked.connect(self.reject)
        layout.addWidget(btn_cancel)

    def _choose_keep(self):
        self.choice = DeletionFinanceChoice.KEEP_FINANCES
        self.accept()

    def _choose_purge(self):
        self.choice = DeletionFinanceChoice.PURGE_FINANCES
        self.accept()


def ask_deletion_with_finance_choice(
    parent,
    item_type: str,
    item_name: str,
    total_received_map: Dict[str, float],
    debt_map: Optional[Dict[str, float]] = None
) -> DeletionFinanceChoice:
    """
    Универсальная функция для запроса удаления.
    Если оплат нет (>0), показывает стандартный простой вопрос.
    Если оплаты есть, открывает диалог с выбором сохранения или списания финансов.
    """
    total_has_money = any(val > 0.001 for val in total_received_map.values())
    
    if not total_has_money:
        msg_box = QMessageBox(parent)
        msg_box.setWindowTitle(f"Удаление {item_type}")
        msg_box.setText(f"Отправить {item_type} «{item_name}» в корзину?")
        msg_box.setInformativeText("Вы сможете восстановить его позже через раздел 'Корзина'.")
        msg_box.setIcon(QMessageBox.Icon.Question)
        btn_del = msg_box.addButton("В корзину", QMessageBox.ButtonRole.YesRole)
        btn_cancel = msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        msg_box.exec()
        if msg_box.clickedButton() == btn_del:
            return DeletionFinanceChoice.PURGE_FINANCES
        return DeletionFinanceChoice.CANCEL

    dlg = DeletionFinanceDialog(parent, item_type, item_name, total_received_map, debt_map)
    dlg.exec()
    return dlg.choice
