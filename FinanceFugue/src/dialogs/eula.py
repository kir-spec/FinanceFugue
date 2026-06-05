
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextEdit, QCheckBox,
    QPushButton, QHBoxLayout, QMessageBox,
)

from .. import APP_NAME
from ..theme import EULA_DIALOG_STYLESHEET, label_accent
from ..utils.paths import resource_path


class EulaDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} — лицензионное соглашение")
        self.setMinimumSize(560, 480)
        self.resize(640, 520)

        self.setStyleSheet(EULA_DIALOG_STYLESHEET)

        layout = QVBoxLayout(self)

        title = QLabel(f"Перед использованием {APP_NAME} примите условия:")
        title.setStyleSheet(label_accent())
        layout.addWidget(title)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(self._load_eula_text())
        layout.addWidget(text)

        self.accept_cb = QCheckBox("Я принимаю условия лицензионного соглашения")
        layout.addWidget(self.accept_cb)

        buttons = QHBoxLayout()
        reject_btn = QPushButton("Отклонить")
        reject_btn.clicked.connect(self.reject)
        accept_btn = QPushButton("Принять и продолжить")
        accept_btn.setObjectName("acceptBtn")
        accept_btn.clicked.connect(self._try_accept)
        buttons.addStretch()
        buttons.addWidget(reject_btn)
        buttons.addWidget(accept_btn)
        layout.addLayout(buttons)

    def _load_eula_text(self) -> str:
        path = resource_path("EULA.md")
        if path.exists():
            return path.read_text(encoding="utf-8")
        return (
            "Данные хранятся локально на вашем компьютере.\n"
            "Вы несёте ответственность за резервное копирование.\n"
            "Программа не передаёт данные на внешние серверы."
        )

    def _try_accept(self):
        if not self.accept_cb.isChecked():
            QMessageBox.warning(
                self,
                APP_NAME,
                "Для продолжения необходимо принять условия соглашения.",
            )
            return
        self.accept()
