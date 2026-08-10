from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox, QLineEdit, 
    QPushButton, QLabel, QStackedWidget, QWidget, QFileDialog, QHBoxLayout, QMessageBox
)

from ..theme import CLIENT_SETTINGS_DIALOG_STYLESHEET
from ..logger import get_logger

logger = get_logger("CloudSettings")

class CloudSettingsDialog(QDialog):
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.window = parent_window
        self.app_settings = self.window.app_settings
        
        self.setWindowTitle("Настройка Облачной Синхронизации")
        self.resize(500, 400)
        self.setStyleSheet(CLIENT_SETTINGS_DIALOG_STYLESHEET)
        
        layout = QVBoxLayout(self)
        
        info_label = QLabel(
            "Настройте автоматическое резервное копирование базы данных.\n"
            "Бэкап выполняется в фоне при сохранении изменений."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        form = QFormLayout()
        self.provider_combo = QComboBox()
        self.provider_combo.addItems([
            "Не использовать", 
            "Telegram (Бот)", 
            "Яндекс.Диск", 
            "Dropbox", 
            "WebDAV (Nextcloud, Mail.ru...)", 
            "Локальная папка (GDrive, OneDrive...)"
        ])
        
        # Маппинг индексов на ключи
        self.provider_keys = ["none", "telegram", "yandex", "dropbox", "webdav", "local"]
        current_provider = self.app_settings.get("cloud_provider", "none")
        if current_provider in self.provider_keys:
            self.provider_combo.setCurrentIndex(self.provider_keys.index(current_provider))
            
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        form.addRow("Провайдер:", self.provider_combo)
        layout.addLayout(form)
        
        self.stack = QStackedWidget()
        
        # 0. None
        self.page_none = QWidget()
        self.stack.addWidget(self.page_none)
        
        # 1. Telegram
        self.page_telegram = QWidget()
        tg_layout = QFormLayout(self.page_telegram)
        
        tg_help = QLabel(
            "<a href='https://t.me/BotFather'>1. Создайте бота в @BotFather</a><br>"
            "<a href='https://t.me/userinfobot'>2. Узнайте свой Chat ID в @userinfobot</a>"
        )
        tg_help.setOpenExternalLinks(True)
        # Убираем использование внешнего LINK_STYLE
        tg_help.setStyleSheet("color: #0078D7; font-size: 13px;")
        
        self.tg_token_edit = QLineEdit(self.app_settings.get("telegram_token", ""))
        self.tg_token_edit.setPlaceholderText("123456789:ABCdefGHIjklMNOpqrSTUvwxYZ")
        self.tg_chat_id_edit = QLineEdit(self.app_settings.get("telegram_chat_id", ""))
        self.tg_chat_id_edit.setPlaceholderText("123456789")
        
        tg_layout.addRow(tg_help)
        tg_layout.addRow("Bot Token:", self.tg_token_edit)
        tg_layout.addRow("Chat ID:", self.tg_chat_id_edit)
        self.stack.addWidget(self.page_telegram)
        
        # 2. Yandex
        self.page_yandex = QWidget()
        ya_layout = QFormLayout(self.page_yandex)
        
        ya_help = QLabel(
            "<a href='https://oauth.yandex.ru/client/new'>Создайте OAuth приложение (Яндекс.Диск REST API)</a><br>"
            "И получите токен."
        )
        ya_help.setOpenExternalLinks(True)
        ya_help.setStyleSheet("color: #0078D7; font-size: 13px;")
        
        self.ya_token_edit = QLineEdit(self.app_settings.get("yandex_token", ""))
        self.ya_token_edit.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        
        ya_layout.addRow(ya_help)
        ya_layout.addRow("OAuth Токен:", self.ya_token_edit)
        self.stack.addWidget(self.page_yandex)
        
        # 3. Dropbox
        self.page_dropbox = QWidget()
        db_layout = QFormLayout(self.page_dropbox)
        db_help = QLabel(
            "<a href='https://www.dropbox.com/developers/apps'>Создайте App в App Console и сгенерируйте Access Token</a>"
        )
        db_help.setOpenExternalLinks(True)
        db_help.setStyleSheet("color: #0078D7; font-size: 13px;")
        
        self.db_token_edit = QLineEdit(self.app_settings.get("dropbox_token", ""))
        self.db_token_edit.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        
        db_layout.addRow(db_help)
        db_layout.addRow("Access Token:", self.db_token_edit)
        self.stack.addWidget(self.page_dropbox)
        
        # 4. WebDAV
        self.page_webdav = QWidget()
        wd_layout = QFormLayout(self.page_webdav)
        
        self.wd_url_edit = QLineEdit(self.app_settings.get("webdav_url", ""))
        self.wd_url_edit.setPlaceholderText("https://webdav.yandex.ru")
        self.wd_login_edit = QLineEdit(self.app_settings.get("webdav_login", ""))
        self.wd_password_edit = QLineEdit(self.app_settings.get("webdav_password", ""))
        self.wd_password_edit.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.wd_path_edit = QLineEdit(self.app_settings.get("webdav_path", "/FinanceFugue_Backup.json"))
        
        wd_layout.addRow("URL сервера:", self.wd_url_edit)
        wd_layout.addRow("Логин:", self.wd_login_edit)
        wd_layout.addRow("Пароль (app password):", self.wd_password_edit)
        wd_layout.addRow("Путь к файлу:", self.wd_path_edit)
        self.stack.addWidget(self.page_webdav)
        
        # 5. Local
        self.page_local = QWidget()
        loc_layout = QVBoxLayout(self.page_local)
        
        loc_help = QLabel("Выберите папку, которую синхронизирует клиент Google Drive, OneDrive или iCloud.")
        loc_help.setWordWrap(True)
        
        loc_row = QHBoxLayout()
        self.loc_path_edit = QLineEdit(self.app_settings.get("local_path", ""))
        self.loc_path_edit.setReadOnly(True)
        loc_btn = QPushButton("Выбрать папку...")
        loc_btn.clicked.connect(self._choose_local_folder)
        
        loc_row.addWidget(self.loc_path_edit)
        loc_row.addWidget(loc_btn)
        
        loc_layout.addWidget(loc_help)
        loc_layout.addLayout(loc_row)
        loc_layout.addStretch()
        self.stack.addWidget(self.page_local)
        
        layout.addWidget(self.stack)
        
        # Кнопки
        btn_layout = QHBoxLayout()
        
        btn_test = QPushButton("Тест подключения / Бэкап сейчас")
        btn_test.clicked.connect(self._test_sync)
        
        btn_save = QPushButton("Сохранить и закрыть")
        btn_save.clicked.connect(self.accept)
        
        btn_layout.addWidget(btn_test)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        
        layout.addLayout(btn_layout)
        
        self._on_provider_changed(self.provider_combo.currentIndex())
        
    def _on_provider_changed(self, index):
        self.stack.setCurrentIndex(index)
        
    def _choose_local_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку для бэкапа")
        if folder:
            self.loc_path_edit.setText(folder)
            
    def _save_settings(self):
        self.app_settings["cloud_provider"] = self.provider_keys[self.provider_combo.currentIndex()]
        self.app_settings["telegram_token"] = self.tg_token_edit.text()
        self.app_settings["telegram_chat_id"] = self.tg_chat_id_edit.text()
        self.app_settings["yandex_token"] = self.ya_token_edit.text()
        self.app_settings["dropbox_token"] = self.db_token_edit.text()
        self.app_settings["webdav_url"] = self.wd_url_edit.text()
        self.app_settings["webdav_login"] = self.wd_login_edit.text()
        self.app_settings["webdav_password"] = self.wd_password_edit.text()
        self.app_settings["webdav_path"] = self.wd_path_edit.text()
        self.app_settings["local_path"] = self.loc_path_edit.text()
        self.window.save_settings()

    def accept(self):
        self._save_settings()
        super().accept()
        
    def _test_sync(self):
        self._save_settings()
        
        provider = self.app_settings.get("cloud_provider", "none")
        if provider == "none":
            QMessageBox.information(self, "Тест", "Синхронизация отключена.")
            return
            
        # Запускаем синхронизацию через главное окно (там есть метод trigger_sync)
        if hasattr(self.window, 'trigger_sync'):
            self.window.trigger_sync(force=True)
            QMessageBox.information(self, "Тест", "Бэкап запущен. Смотрите статус в левом нижнем углу главного окна.")
        else:
            QMessageBox.warning(self, "Тест", "Метод trigger_sync не найден в главном окне.")
