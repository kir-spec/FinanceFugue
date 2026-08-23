from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QHBoxLayout
)
from PySide6.QtCore import Qt

from ..storage import CRMStorage
from ..services.crypto import InvalidPasswordError

class LoginDialog(QDialog):
    def __init__(self, storage: CRMStorage, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.password_accepted = False

        self.setWindowTitle("FinanceFugue - Авторизация")
        self.setFixedSize(400, 250)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        self.setStyleSheet("""
            QDialog {
                background-color: #1E1E1E;
            }
            QLabel {
                color: #FFFFFF;
            }
            QLineEdit {
                background-color: #2D2D2D;
                color: #FFFFFF;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 14px;
                selection-background-color: #0078D7;
                selection-color: #FFFFFF;
            }
            QLineEdit:focus {
                border: 1px solid #00D1FF;
                background-color: #333333;
            }
            QPushButton {
                background-color: #0078D7;
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                padding: 10px 24px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1084E3;
            }
            QPushButton:pressed {
                background-color: #0063B1;
            }
        """)

        is_encrypted = self.storage.check_is_encrypted()
        db_exists = self.storage.path.exists()

        if db_exists and is_encrypted:
            self.mode = "login"
            title_text = "🔒 Введите Master-пароль"
            info_text = "Ваша база данных надежно зашифрована (AES-256)."
        elif db_exists and not is_encrypted:
            self.mode = "migrate"
            title_text = "🛡 Защита данных"
            info_text = "В новой версии требуется установить пароль для шифрования вашей базы данных."
        else:
            self.mode = "create"
            title_text = "✨ Добро пожаловать"
            info_text = "Придумайте надежный Master-пароль для шифрования ваших финансовых данных."

        title_lbl = QLabel(title_text)
        title_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFFFFF;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)

        info_lbl = QLabel(info_text)
        info_lbl.setWordWrap(True)
        info_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_lbl.setStyleSheet("color: #DDDDDD; font-size: 12px;")
        layout.addWidget(info_lbl)

        self.pwd_edit = QLineEdit()
        self.pwd_edit.setPlaceholderText("Введите пароль...")
        self.pwd_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.pwd_edit)

        if self.mode in ("migrate", "create"):
            self.pwd_confirm = QLineEdit()
            self.pwd_confirm.setPlaceholderText("Подтвердите пароль...")
            self.pwd_confirm.setEchoMode(QLineEdit.EchoMode.Password)
            layout.addWidget(self.pwd_confirm)

        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("Продолжить")
        self.btn_ok.clicked.connect(self.attempt_login)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)

    def attempt_login(self):
        pwd = self.pwd_edit.text()
        
        if self.mode in ("migrate", "create"):
            if not pwd:
                QMessageBox.warning(self, "Ошибка", "Пароль не может быть пустым.")
                return
            if pwd != self.pwd_confirm.text():
                QMessageBox.warning(self, "Ошибка", "Пароли не совпадают.")
                return
            
            # Для миграции: загружаем открытую базу (storage пароль пока пустой),
            # затем устанавливаем пароль и сохраняем зашифрованную.
            if self.mode == "migrate":
                try:
                    # Загрузит открытую базу
                    clients = self.storage.load()
                    # Ставим пароль
                    self.storage.password = pwd
                    # Сохраняем зашифрованную
                    self.storage.save(clients)
                    QMessageBox.information(self, "Успех", "База данных успешно зашифрована!")
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", f"Не удалось зашифровать базу:\n{e}")
                    return
            else:
                # Просто сохраняем пароль в storage, база будет создана при первом сохранении
                self.storage.password = pwd
                
            self.password_accepted = True
            self.accept()
            
        elif self.mode == "login":
            if not pwd:
                return
                
            self.storage.password = pwd
            try:
                # Пытаемся тестово загрузить базу
                self.storage.load()
                self.password_accepted = True
                self.accept()
            except InvalidPasswordError:
                self.storage.password = ""
                QMessageBox.critical(self, "Ошибка", "Неверный пароль. Доступ запрещен.")
                self.pwd_edit.clear()
                self.pwd_edit.setFocus()
            except Exception as e:
                self.storage.password = ""
                QMessageBox.critical(self, "Ошибка базы", f"Ошибка чтения файла:\n{e}")
