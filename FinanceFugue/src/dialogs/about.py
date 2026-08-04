
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QTextEdit, QPushButton, QWidget,
)

from .. import APP_NAME, VERSION, COMPANY, COPYRIGHT_HOLDER, SUPPORT_EMAIL
from ..theme import ABOUT_DIALOG_STYLESHEET, label_accent
from ..utils.paths import resource_path


def _read_resource(name: str, fallback: str = "") -> str:
    path = resource_path(name)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return fallback


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"О программе — {APP_NAME}")
        self.setMinimumSize(620, 480)
        self.resize(700, 540)
        self.setStyleSheet(ABOUT_DIALOG_STYLESHEET)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        tabs.addTab(self._about_tab(), "О программе")
        tabs.addTab(self._text_tab("EULA.md"), "Лицензия (EULA)")
        tabs.addTab(self._text_tab("PRIVACY.md"), "Конфиденциальность")
        tabs.addTab(self._text_tab("THIRD_PARTY_LICENSES.txt"), "Сторонние компоненты")
        tabs.addTab(self._text_tab("LICENSE"), "Правообладатель")

        layout.addWidget(tabs)

        buttons = QHBoxLayout()
        buttons.addStretch()
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

    def _about_tab(self) -> QWidget:
        widget = QWidget()
        v = QVBoxLayout(widget)
        title = QLabel(f"{APP_NAME} {VERSION}")
        title.setStyleSheet(label_accent(size=18))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(title)

        info = QLabel(
            f"<p><b>{COMPANY}</b><br>"
            f"© {COPYRIGHT_HOLDER}, 2026. Все права защищены.</p>"
            f"<p>CRM для учёта клиентов, заказов, платежей и файлов.<br>"
            f"Данные хранятся локально на вашем компьютере.</p>"
            f"<p>Контакт: <a href='mailto:{SUPPORT_EMAIL}' style='color:#00D1FF'>{SUPPORT_EMAIL}</a></p>"
            f"<p>Документы: EULA, политика конфиденциальности, "
            f"<a href='#license-tab' style='color:#00D1FF'>лицензии сторонних компонентов</a>.</p>"
        )
        info.setWordWrap(True)
        info.setOpenExternalLinks(True)
        info.setTextFormat(Qt.TextFormat.RichText)
        v.addWidget(info)

        # LGPL notice per Qt licensing requirements.
        lgpl = QLabel(
            "<p style='color:#888;font-size:11px;margin-top:10px'>"
            "<b>LGPL v3 notice:</b> This software uses PySide6 (Qt for Python), "
            "licensed under <i>GNU Lesser General Public License v3</i>.<br>"
            "Per LGPL §6, you may <b>relink</b> this application against a "
            "modified version of PySide6 / Qt libraries.<br>"
            "Source code for this application and PySide6 is available at "
            "<a href='https://github.com/your-repo/financefugue' "
            "style='color:#00D1FF'>github.com</a> and "
            "<a href='https://doc.qt.io/qtforpython-6/' "
            "style='color:#00D1FF'>doc.qt.io</a>."
            "</p>"
        )
        lgpl.setWordWrap(True)
        lgpl.setOpenExternalLinks(True)
        lgpl.setTextFormat(Qt.TextFormat.RichText)
        v.addWidget(lgpl)

        v.addStretch()
        return widget

    def _text_tab(self, filename: str) -> QWidget:
        widget = QWidget()
        v = QVBoxLayout(widget)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(_read_resource(filename, f"Файл {filename} не найден."))
        v.addWidget(text)
        return widget
