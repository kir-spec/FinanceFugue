"""Диалог принятия Пользовательского соглашения (EULA).

Адаптировано под стиль KoshaDrive:
- HTML-шаблон из ``resources/eula.html`` с плейсхолдерами
- Кнопка «Принять» активна только после прокрутки текста до конца
  (гарантирует, что пользователь действительно прочитал)
- Диалог модальный, без возможности обхода

Юридический канон: см. ``EULA.md`` (редакция FF-EULA-04.08.2026-1).
"""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QTextBrowser, QVBoxLayout,
)

from .. import APP_NAME, EULA_VERSION, VERSION_DATE
from ..services.eula_renderer import load_eula_html
from ..theme import EULA_DIALOG_STYLESHEET, label_accent

logger = logging.getLogger("EULADialog")


class EulaDialog(QDialog):
    """Модальный диалог принятия EULA.

    Поведение:
        * Показывает HTML из ``resources/eula.html`` с подставленными
          ``{{REVISION}}`` и ``{{DATE}}``.
        * Кнопка «Принять и продолжить» неактивна до прокрутки текста
          до конца (вертикальный scrollbar) **И** установки флажка
          «Я принимаю условия».
        * При отказе вызывается ``reject()`` — приложение завершает
          работу (см. ``show_eula_dialog`` в ``src/ui/main_window/window.py``).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} {VERSION_DATE} — лицензионное соглашение")
        self.setMinimumSize(720, 560)
        self.resize(820, 640)
        self.setModal(True)
        self.setStyleSheet(EULA_DIALOG_STYLESHEET)

        self._scrolled_to_end = False

        layout = QVBoxLayout(self)

        # Title
        title = QLabel(
            f"Перед использованием {APP_NAME} {VERSION_DATE} "
            f"примите условия Пользовательского соглашения"
        )
        title.setStyleSheet(label_accent(size=12))
        title.setWordWrap(True)
        layout.addWidget(title)

        # EULA text
        self.text = QTextBrowser()
        self.text.setOpenExternalLinks(True)
        self.text.setHtml(self._load_eula_html())
        self.text.verticalScrollBar().valueChanged.connect(self._on_scroll)
        layout.addWidget(self.text, 1)

        # Hint
        hint = QLabel(
            "Прокрутите текст до конца и поставьте флажок, чтобы продолжить."
        )
        hint.setStyleSheet("color:#888; font-size:9pt;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        # Acceptance
        self.accept_cb = QCheckBox(
            "Я прочитал(а) и принимаю условия Пользовательского соглашения"
        )
        self.accept_cb.toggled.connect(self._refresh_accept_state)
        layout.addWidget(self.accept_cb)

        # Buttons
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.reject_btn = QPushButton("Отклонить")
        self.reject_btn.clicked.connect(self._on_reject)
        self.accept_btn = QPushButton("Принять и продолжить")
        self.accept_btn.setObjectName("acceptBtn")
        self.accept_btn.setEnabled(False)
        self.accept_btn.setDefault(False)
        self.accept_btn.clicked.connect(self._try_accept)
        buttons.addWidget(self.reject_btn)
        buttons.addWidget(self.accept_btn)
        layout.addLayout(buttons)

    def _load_eula_html(self) -> str:
        return load_eula_html(revision=EULA_VERSION, date=VERSION_DATE)

    def _on_scroll(self, value: int) -> None:
        sb = self.text.verticalScrollBar()
        # «До конца» = прокручены вниз до самого низа.
        # Используем высоту viewport родительского QTextBrowser.
        viewport = self.text.viewport().height()
        if value + viewport >= sb.maximum() - 4:
            if not self._scrolled_to_end:
                self._scrolled_to_end = True
                self._refresh_accept_state()

    def _refresh_accept_state(self) -> None:
        self.accept_btn.setEnabled(self._scrolled_to_end and self.accept_cb.isChecked())

    def _try_accept(self) -> None:
        if not self.accept_cb.isChecked():
            QMessageBox.warning(
                self, APP_NAME,
                "Для продолжения необходимо подтвердить принятие условий.",
            )
            return
        if not self._scrolled_to_end:
            QMessageBox.warning(
                self, APP_NAME,
                "Прокрутите текст соглашения до конца перед принятием.",
            )
            return
        logger.info("Пользователь принял EULA %s", EULA_VERSION)
        self.accept()

    def _on_reject(self) -> None:
        answer = QMessageBox.question(
            self,
            APP_NAME,
            "Вы отклоняете Пользовательское соглашение.\n"
            f"Это означает, что {APP_NAME} не может быть запущен.\n\n"
            "Закрыть приложение?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.reject()
