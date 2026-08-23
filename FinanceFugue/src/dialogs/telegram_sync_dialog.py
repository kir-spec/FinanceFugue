import time
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QLabel, QCheckBox, QTextEdit, QMessageBox, QGroupBox, QProgressBar
)
from PySide6.QtCore import Qt

from ..theme import CLIENT_SETTINGS_DIALOG_STYLESHEET
from ..logger import get_logger
from ..services.cloud_sync import DEFAULT_TELEGRAM_BOT_TOKEN, CloudSyncWorker, TelegramBotSync

logger = get_logger("TelegramSyncDialog")

class TelegramSyncDialog(QDialog):
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.window = parent_window
        self.app_settings = self.window.app_settings
        self.worker = None

        self.setWindowTitle("📱 Синхронизация с Telegram-ботом")
        self.resize(560, 520)
        self.setStyleSheet(CLIENT_SETTINGS_DIALOG_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Информационная шапка
        header_box = QGroupBox("Бесшовная синхронизация ПК ⇄ Telegram")
        header_layout = QVBoxLayout(header_box)
        info_label = QLabel(
            "Программа FinanceFugue и Telegram-бот работают с единой базой данных.\n"
            "Вы можете вносить заказы и платежи на компьютере или с телефона через бота — "
            "все данные будут синхронизированы в реальном времени!"
        )
        info_label.setWordWrap(True)
        header_layout.addWidget(info_label)
        layout.addWidget(header_box)

        # Настройки подключения
        conn_group = QGroupBox("Параметры авторизации в Telegram")
        form = QFormLayout(conn_group)

        self.chat_id_edit = QLineEdit(str(self.app_settings.get("telegram_chat_id", "")))
        self.chat_id_edit.setPlaceholderText("Например: 123456789")
        self.chat_id_edit.setToolTip("Ваш уникальный цифровой ID в Telegram")

        tg_help = QLabel(
            "<i>💡 Как узнать свой Chat ID: откройте финансового бота и нажмите <b>/sync</b> или напишите боту @userinfobot</i>"
        )
        self.token_edit = QLineEdit(self.app_settings.get("telegram_token", DEFAULT_TELEGRAM_BOT_TOKEN))
        self.token_edit.setPlaceholderText("123456789:ABCdefGHIjklMNOpqrSTUvwxYZ")
        self.token_edit.setToolTip("Токен вашего Telegram-бота (из @BotFather)")

        form.addRow("Ваш Telegram Chat ID:", self.chat_id_edit)
        form.addRow("", tg_help)
        form.addRow("Токен бота (Bot Token):", self.token_edit)

        btn_test = QPushButton("⚡️ Проверить связь с ботом")
        btn_test.clicked.connect(self._test_connection)
        form.addRow("", btn_test)

        layout.addWidget(conn_group)

        # Опции
        opts_group = QGroupBox("Режим работы")
        opts_layout = QVBoxLayout(opts_group)

        self.auto_sync_cb = QCheckBox("Автоматически синхронизировать с ботом при сохранении на ПК")
        self.auto_sync_cb.setChecked(self.app_settings.get("auto_telegram_sync", True))
        opts_layout.addWidget(self.auto_sync_cb)
        layout.addWidget(opts_group)

        # Кнопки действий
        actions_group = QGroupBox("Действия синхронизации")
        actions_layout = QVBoxLayout(actions_group)

        btn_row1 = QHBoxLayout()
        self.btn_push = QPushButton("⬆️ Отправить базу в бота (Push)")
        self.btn_push.setToolTip("Выгрузить текущую базу с ПК в Telegram-бота")
        self.btn_push.clicked.connect(self._push_to_bot)

        self.btn_pull = QPushButton("⬇️ Загрузить базу из бота (Pull)")
        self.btn_pull.setToolTip("Загрузить в программу последнюю версию базы, отправленную в боте")
        self.btn_pull.clicked.connect(self._pull_from_bot)

        btn_row1.addWidget(self.btn_push)
        btn_row1.addWidget(self.btn_pull)
        actions_layout.addLayout(btn_row1)

        self.btn_full_sync = QPushButton("🔄 Синхронизировать сейчас (2-сторонний обмен)")
        self.btn_full_sync.setStyleSheet("background-color: #0078D7; color: #FFFFFF; font-weight: bold; padding: 8px;")
        self.btn_full_sync.clicked.connect(self._full_sync)
        actions_layout.addWidget(self.btn_full_sync)

        layout.addWidget(actions_group)

        # Лог и статус
        self.status_label = QLabel("Готово к работе")
        self.status_label.setStyleSheet("font-weight: bold; color: #00D1FF;")
        layout.addWidget(self.status_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(80)
        self.log_text.setStyleSheet("background-color: #1A1A1A; font-family: Consolas; font-size: 11px;")
        layout.addWidget(self.log_text)

        # Нижние кнопки
        bottom_layout = QHBoxLayout()
        btn_save_close = QPushButton("Сохранить настройки и закрыть")
        btn_save_close.clicked.connect(self.accept)
        bottom_layout.addStretch()
        bottom_layout.addWidget(btn_save_close)
        layout.addLayout(bottom_layout)

        self._log("Инициализация диалога синхронизации.")

    def _log(self, text: str):
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {text}")

    def _save_settings(self):
        self.app_settings["telegram_chat_id"] = self.chat_id_edit.text().strip()
        self.app_settings["telegram_token"] = self.token_edit.text().strip() or DEFAULT_TELEGRAM_BOT_TOKEN
        self.app_settings["auto_telegram_sync"] = self.auto_sync_cb.isChecked()
        self.app_settings["cloud_provider"] = "telegram"
        self.window.save_settings()

    def accept(self):
        self._save_settings()
        super().accept()

    def _set_busy(self, is_busy: bool, status_text: str = ""):
        self.btn_push.setEnabled(not is_busy)
        self.btn_pull.setEnabled(not is_busy)
        self.btn_full_sync.setEnabled(not is_busy)
        if status_text:
            self.status_label.setText(status_text)

    def _test_connection(self):
        self._save_settings()
        chat_id = self.chat_id_edit.text().strip()
        token = self.token_edit.text().strip() or DEFAULT_TELEGRAM_BOT_TOKEN
        if not chat_id:
            QMessageBox.warning(self, "Внимание", "Пожалуйста, введите ваш Telegram Chat ID.")
            return

        self._set_busy(True, "⏳ Проверка связи с ботом...")
        self._log("Отправка тестового запроса в Telegram...")

        self.worker = CloudSyncWorker(str(self.window.storage.path), self.app_settings, action="test_telegram")
        self.worker.finished_sync.connect(self._on_test_finished)
        self.worker.start()

    def _on_test_finished(self, success: bool, msg: str):
        self._set_busy(False, "✅ Связь установлена" if success else "❌ Ошибка связи")
        self._log(msg)
        if success:
            QMessageBox.information(self, "Успех", msg)
        else:
            QMessageBox.critical(self, "Ошибка подключения", msg)

    def _push_to_bot(self):
        self._save_settings()
        chat_id = self.chat_id_edit.text().strip()
        if not chat_id:
            QMessageBox.warning(self, "Внимание", "Укажите Telegram Chat ID перед синхронизацией.")
            return

        self._set_busy(True, "⏳ Отправка базы данных в Telegram...")
        self._log("Выгрузка базы данных в чат с ботом...")

        self.worker = CloudSyncWorker(str(self.window.storage.path), self.app_settings, action="push")
        self.worker.finished_sync.connect(self._on_push_finished)
        self.worker.start()

    def _on_push_finished(self, success: bool, msg: str):
        self._set_busy(False, "✅ База выгружена в бота" if success else "❌ Ошибка выгрузки")
        self._log(msg)
        if success:
            QMessageBox.information(self, "Синхронизация", f"База данных успешно отправлена в бота!\n\n{msg}")
        else:
            QMessageBox.critical(self, "Ошибка", f"Не удалось отправить базу: {msg}")

    def _pull_from_bot(self):
        self._save_settings()
        chat_id = self.chat_id_edit.text().strip()
        if not chat_id:
            QMessageBox.warning(self, "Внимание", "Укажите Telegram Chat ID перед синхронизацией.")
            return

        self._set_busy(True, "⏳ Загрузка последней базы из Telegram...")
        self._log("Запрос актуальной базы данных из Telegram...")

        self.worker = CloudSyncWorker(str(self.window.storage.path), self.app_settings, action="pull_telegram")
        self.worker.finished_sync.connect(self._on_pull_finished)
        self.worker.start()

    def _on_pull_finished(self, success: bool, msg: str):
        self._set_busy(False, "✅ База успешно загружена" if success else "❌ Ошибка загрузки")
        self._log(msg)
        if success:
            if hasattr(self.window, "reload_database_after_pull"):
                self.window.reload_database_after_pull()
            QMessageBox.information(
                self, "Синхронизация",
                f"База данных успешно получена из Telegram и загружена в программу!\n\n{msg}"
            )
        else:
            QMessageBox.warning(self, "Загрузка из бота", f"Не удалось загрузить базу: {msg}")

    def _full_sync(self):
        """2-сторонняя синхронизация: отправляет текущую базу в бота для немедленной актуализации"""
        self._push_to_bot()
