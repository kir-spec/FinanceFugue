"""Диалог «О программе FinanceFugue» с табами.

Табы:
  1. О программе — версия, реквизиты, LGPL notice.
  2. Лицензия (EULA) — HTML из ``resources/eula.html``.
  3. Конфиденциальность — ``PRIVACY.md``.
  4. Сторонние компоненты — ``THIRD_PARTY_LICENSES.txt``.
  5. Правообладатель — ``LICENSE``.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QTextBrowser, QPushButton, QWidget,
)

from .. import APP_NAME, VERSION, VERSION_DATE, COMPANY, COPYRIGHT_HOLDER, SUPPORT_EMAIL
from ..services.eula_renderer import load_eula_html
from ..theme import ABOUT_DIALOG_STYLESHEET, label_accent
from ..utils.paths import resource_path


def _read_text(name: str, fallback: str = "") -> str:
    path = resource_path(name)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return fallback or f"Файл {name} не найден в дистрибутиве."


def _build_simple_browser(text: str) -> QTextBrowser:
    """Plain-text браузер для не-HTML файлов."""
    browser = QTextBrowser()
    browser.setOpenExternalLinks(True)
    browser.setPlainText(text)
    return browser


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"О программе — {APP_NAME} {VERSION_DATE}")
        self.setMinimumSize(680, 520)
        self.resize(760, 600)
        self.setStyleSheet(ABOUT_DIALOG_STYLESHEET)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        tabs.addTab(self._about_tab(), "О программе")
        tabs.addTab(self._eula_tab(), "Лицензия (EULA)")
        tabs.addTab(
            _build_simple_browser(_read_text("PRIVACY.md")),
            "Конфиденциальность",
        )
        tabs.addTab(
            _build_simple_browser(_read_text("THIRD_PARTY_LICENSES.txt")),
            "Сторонние компоненты",
        )
        tabs.addTab(
            _build_simple_browser(_read_text("LICENSE")),
            "Правообладатель",
        )

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
        title = QLabel(f"{APP_NAME} {VERSION_DATE}")
        title.setStyleSheet(label_accent(size=20))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(title)

        info = QLabel(
            f"<p><b>{COMPANY}</b><br>"
            f"© {COPYRIGHT_HOLDER}, 2026. Все права защищены.</p>"
            f"<p><b>Версия:</b> {VERSION_DATE} (SemVer {VERSION})</p>"
            f"<p><b>Назначение:</b> локальная настольная CRM "
            f"(учёт клиентов, заказов, платежей и файлов).</p>"
            f"<p><b>Данные:</b> хранятся <i>исключительно</i> на устройстве "
            f"пользователя. Программа не отправляет данные на внешние серверы.</p>"
            f"<p><b>Контакт:</b> "
            f"<a href='mailto:{SUPPORT_EMAIL}' style='color:#00D1FF'>"
            f"{SUPPORT_EMAIL}</a></p>"
            f"<p><b>Документы:</b> EULA, политика конфиденциальности, "
            f"лицензии сторонних компонентов — соответствующие табы.</p>"
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
            "Source: "
            "<a href='https://code.qt.io/cgit/pyside/pyside-setup.git/' "
            "style='color:#00D1FF'>code.qt.io/pyside</a> · "
            "<a href='https://doc.qt.io/qtforpython-6/' "
            "style='color:#00D1FF'>doc.qt.io</a>"
            "</p>"
        )
        lgpl.setWordWrap(True)
        lgpl.setOpenExternalLinks(True)
        lgpl.setTextFormat(Qt.TextFormat.RichText)
        v.addWidget(lgpl)

        v.addStretch()
        return widget

    def _eula_tab(self) -> QWidget:
        """Таб с EULA HTML (тот же файл, что в диалоге принятия)."""
        widget = QWidget()
        v = QVBoxLayout(widget)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        from .. import EULA_VERSION
        browser.setHtml(
            load_eula_html(revision=EULA_VERSION, date=VERSION_DATE)
        )
        v.addWidget(browser)
        return widget
