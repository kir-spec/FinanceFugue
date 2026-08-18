"""One-time extractor: order_widget methods -> mixins.

.. warning::
    Этот скрипт был **уже применён** во время рефакторинга.
    Результат (миксины) уже находятся в ``src/widgets/``.
    **Не запускайте повторно** — он перезапишет уже актуальные
    файлы миксинов старыми версиями из ``order_widget.py``.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "src/widgets/order_widget.py").read_text(encoding="utf-8")


def extract_methods(names: list[str]) -> str:
    parts = []
    for name in names:
        pat = rf"(    def {re.escape(name)}\(.*?)(?=\n    def |\Z)"
        m = re.search(pat, src, re.DOTALL)
        if not m:
            raise RuntimeError(f"missing method: {name}")
        parts.append(m.group(1).rstrip())
    return "\n\n".join(parts)


files_header = '''"""Файлы и DnD для карточки заказа."""
import os
import platform
import shutil
import subprocess
import zipfile
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QMessageBox, QFileDialog,
)
from PySide6.QtCore import Qt

from ..models import ProjectFile
from ..logger import get_logger
from ..theme import BUTTON_COMPACT_STYLE, FOLDER_ACCESS_LABEL_STYLE

logger = get_logger("Widgets")


class OrderFilesMixin:
'''

fin_header = '''"""Финансы и платежи для карточки заказа."""
from datetime import datetime

from PySide6.QtWidgets import (
    QMessageBox, QLineEdit, QDialog, QFormLayout, QComboBox, QDateEdit,
    QDialogButtonBox, QTextEdit,
)
from PySide6.QtGui import QDoubleValidator

from ..dialogs import PaymentsDialog
from ..logger import get_logger
from ..theme import (
    ADD_PAYMENT_DIALOG_STYLESHEET,
    DATE_EDIT_STYLE,
    deadline_date_edit_style,
    payment_status_style,
)

logger = get_logger("Widgets")


class OrderFinancialMixin:
'''

files_methods = [
    "dragEnterEvent", "dropEvent", "add_folder_access_button", "create_folder_access_widget",
    "open_folder", "add_file_with_storage_option", "export_files_to_zip", "add_file",
]
fin_methods = [
    "format_number", "sync_price", "sync_advance", "sync_debt", "sync_deadline", "sync_order_date",
    "update_deadline_color", "update_financial_display", "update_order_status", "update_payment_status",
    "add_payment_dialog", "show_payments_history", "delete_order",
]

(ROOT / "src/widgets/order_files_mixin.py").write_text(
    files_header + extract_methods(files_methods) + "\n", encoding="utf-8"
)
(ROOT / "src/widgets/order_financial_mixin.py").write_text(
    fin_header + extract_methods(fin_methods) + "\n", encoding="utf-8"
)
print("OK")
