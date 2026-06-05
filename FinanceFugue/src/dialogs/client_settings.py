
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QMessageBox, QLineEdit, QGroupBox, QFormLayout, QTextEdit, QDialogButtonBox, QSizePolicy,
)
from PySide6.QtCore import Qt

from ..logger import get_logger
from ..models import Client
from ..ui.app_bridge import AppBridge
from ..theme import CLIENT_SETTINGS_DIALOG_STYLESHEET

logger = get_logger("Dialogs")

# --- ДИАЛОГ НАСТРОЕК КЛИЕНТА ---
class ClientSettingsDialog(QDialog):
    def __init__(self, client: Client, bridge: AppBridge):
        super().__init__(bridge.window)
        self.client = client
        self._bridge = bridge
        self.setWindowTitle("Настройки клиента")

        self.setStyleSheet(CLIENT_SETTINGS_DIALOG_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
        form = QFormLayout()

        self.name_edit = QLineEdit(client.name)
        form.addRow("Имя:", self.name_edit)

        self.email_edit = QLineEdit(client.email)
        form.addRow("Email:", self.email_edit)

        self.link_edit = QLineEdit(client.social_link)
        form.addRow("Соц. сеть:", self.link_edit)

        self.notes_edit = QTextEdit(client.notes)
        self.notes_edit.setMaximumHeight(80)
        form.addRow("Заметка:", self.notes_edit)

        layout.addLayout(form)

        export_group = QGroupBox("Инструменты экспорта")
        export_group.setObjectName("exportGroup")
        export_layout = QVBoxLayout(export_group)
        export_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        export_files_btn = QPushButton("📁 Экспорт файлов")
        export_files_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        export_files_btn.clicked.connect(self._bridge.export_client_files)

        export_orders_btn = QPushButton("📊 Экспорт заказов")
        export_orders_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        export_orders_btn.clicked.connect(self._bridge.export_client_orders)

        export_layout.addWidget(export_files_btn)
        export_layout.addWidget(export_orders_btn)
        layout.addWidget(export_group)

        del_btn = QPushButton("🗑️ Удалить клиента")
        del_btn.setObjectName("dangerButton")
        del_btn.clicked.connect(self.delete_client)
        layout.addWidget(del_btn)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def delete_client(self):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Подтверждение удаления")
        msg_box.setText(f"Вы уверены, что хотите удалить клиента '{self.client.name}'?")
        msg_box.setInformativeText("Все заказы и файлы клиента будут также удалены.")
        msg_box.setIcon(QMessageBox.Icon.Warning)

        btn_delete = msg_box.addButton("Удалить клиента", QMessageBox.ButtonRole.YesRole)
        btn_cancel = msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)

        msg_box.exec()

        if msg_box.clickedButton() == btn_delete:
            logger.info("Удаление клиента: %s (ID: %s)", self.client.name, self.client.id)
            self._bridge.remove_client(self.client)
            self.reject()
