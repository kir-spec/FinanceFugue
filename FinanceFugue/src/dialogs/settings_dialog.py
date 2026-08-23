import os
import shutil
import glob
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox, QFileDialog, QCheckBox,
    QGroupBox, QInputDialog, QComboBox, QLabel, QLineEdit, QTextEdit, QTabWidget, QWidget
)

from ..logger import get_logger
from .. import APP_NAME
from ..theme import SETTINGS_DIALOG_STYLESHEET

logger = get_logger("Dialogs")

# --- ДИАЛОГ НАСТРОЕК (С ВКЛАДКАМИ) ---
class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self._window = parent
        self.setWindowTitle("Настройки")
        self.resize(540, 430)
        self.setStyleSheet(SETTINGS_DIALOG_STYLESHEET)
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(12, 12, 12, 12)
        
        # Создаем удобный TabWidget
        self.tabs = QTabWidget()
        
        # 1. Вкладка: Общие настройки
        tab_general = QWidget()
        gen_layout = QVBoxLayout(tab_general)
        gen_layout.setSpacing(8)
        gen_layout.setContentsMargins(12, 12, 12, 12)

        # Язык интерфейса
        gen_layout.addWidget(QLabel("🌐 Язык интерфейса / Language / Мова:"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("🌐 Авто (Язык системы / Auto)", "auto")
        self.lang_combo.addItem("🇬🇧 English", "en")
        self.lang_combo.addItem("🇷🇺 Русский", "ru")
        self.lang_combo.addItem("🇺🇦 Українська", "uk")
        current_saved_lang = self._window.app_settings.get("ui_language", "auto")
        idx = {"auto": 0, "en": 1, "ru": 2, "uk": 3}.get(current_saved_lang, 0)
        self.lang_combo.setCurrentIndex(idx)
        self.lang_combo.currentIndexChanged.connect(self._save_lang_pref)
        gen_layout.addWidget(self.lang_combo)

        # Режим работы
        from ..services.i18n import t
        gen_layout.addWidget(QLabel("🎯 Режим работы программы / Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem(t("mode_full"), "full")
        self.mode_combo.addItem(t("mode_personal"), "personal")
        self.mode_combo.addItem(t("mode_crm"), "crm")
        current_saved_mode = self._window.app_settings.get("app_mode", "full")
        m_idx = {"full": 0, "personal": 1, "crm": 2}.get(current_saved_mode, 0)
        self.mode_combo.setCurrentIndex(m_idx)
        self.mode_combo.currentIndexChanged.connect(self._save_mode_pref)
        gen_layout.addWidget(self.mode_combo)

        # Тема оформления
        gen_layout.addWidget(QLabel("🎨 Тема оформления (требует перезапуска):"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["🌙 Темная (по умолчанию)", "☀️ Светлая"])
        if self._window.app_settings.get("theme", "dark") == "light":
            self.theme_combo.setCurrentIndex(1)
        self.theme_combo.currentIndexChanged.connect(self._save_theme_pref)
        gen_layout.addWidget(self.theme_combo)

        # Дедлайны чекбокс
        self.deadline_notify_cb = QCheckBox("🔔 Уведомления о приближающихся дедлайнах")
        self.deadline_notify_cb.setChecked(
            self._window.app_settings.get("deadline_notifications", True)
        )
        self.deadline_notify_cb.stateChanged.connect(self._save_deadline_pref)
        gen_layout.addWidget(self.deadline_notify_cb)

        # Резервная копия конфигурации
        cfg_row = QHBoxLayout()
        btn_backup_settings = QPushButton("💾 Резервная копия настроек")
        btn_backup_settings.clicked.connect(self.manual_backup_settings)
        btn_restore_settings = QPushButton("🔄 Восстановить настройки")
        btn_restore_settings.clicked.connect(self.restore_settings_dialog)
        cfg_row.addWidget(btn_backup_settings)
        cfg_row.addWidget(btn_restore_settings)
        gen_layout.addLayout(cfg_row)
        gen_layout.addStretch()

        self.tabs.addTab(tab_general, "⚙️ Общие")

        # 2. Вкладка: База данных
        tab_db = QWidget()
        db_layout = QVBoxLayout(tab_db)
        db_layout.setSpacing(8)
        db_layout.setContentsMargins(12, 12, 12, 12)

        btn_db_location = QPushButton("📁 Выбрать место хранения базы данных")
        btn_db_location.clicked.connect(self.change_database_location)
        db_layout.addWidget(btn_db_location)

        btn_imp_folder = QPushButton("📂 Импорт из папки клиентов")
        btn_imp_folder.clicked.connect(self._window.import_from_folder)
        db_layout.addWidget(btn_imp_folder)

        json_row = QHBoxLayout()
        btn_exp = QPushButton("📤 Экспорт (JSON)")
        btn_exp.clicked.connect(self._window.export_json)
        btn_imp = QPushButton("📥 Импорт (JSON)")
        btn_imp.clicked.connect(self._window.import_json_file)
        json_row.addWidget(btn_exp)
        json_row.addWidget(btn_imp)
        db_layout.addLayout(json_row)

        btn_full = QPushButton("📦 Полный бэкап (ZIP архив со всеми файлами)")
        btn_full.clicked.connect(self._window.export_full_backup)
        db_layout.addWidget(btn_full)

        # Опасная зона
        danger_box = QGroupBox("⚠️ Опасная зона")
        danger_layout = QHBoxLayout(danger_box)
        btn_del_files = QPushButton("🗑 Удалить ВСЕ файлы")
        btn_del_files.setStyleSheet("background-color: #8B0000; color: #FFFFFF;")
        btn_del_files.clicked.connect(self._window.delete_all_files)
        btn_del_db = QPushButton("☠ Удалить ВСЮ базу")
        btn_del_db.setStyleSheet("background-color: #A00000; color: #FFFFFF;")
        btn_del_db.clicked.connect(self._window.delete_database_full)
        danger_layout.addWidget(btn_del_files)
        danger_layout.addWidget(btn_del_db)
        db_layout.addWidget(danger_box)
        db_layout.addStretch()

        self.tabs.addTab(tab_db, "💾 База данных")

        # 3. Вкладка: Синхронизация (Telegram & Облако)
        tab_sync = QWidget()
        sync_layout = QVBoxLayout(tab_sync)
        sync_layout.setSpacing(10)
        sync_layout.setContentsMargins(12, 12, 12, 12)

        tg_group = QGroupBox("📱 Двусторонняя синхронизация с Telegram-ботом")
        tg_l = QVBoxLayout(tg_group)
        tg_desc = QLabel("Мгновенный обмен базой данных с вашим персональным ботом.")
        tg_desc.setWordWrap(True)
        btn_tg_sync = QPushButton("⚡️ Открыть окно синхронизации с Telegram")
        btn_tg_sync.setStyleSheet("background-color: #0078D7; color: #FFFFFF; font-weight: bold; padding: 8px;")
        btn_tg_sync.clicked.connect(self._open_telegram_sync)
        tg_l.addWidget(tg_desc)
        tg_l.addWidget(btn_tg_sync)
        sync_layout.addWidget(tg_group)

        cloud_group = QGroupBox("☁️ Облачные бэкапы (WebDAV / Яндекс.Диск / Dropbox)")
        cloud_l = QVBoxLayout(cloud_group)
        cloud_desc = QLabel("Настройка автоматического резервного копирования в сторонние облачные сервисы.")
        cloud_desc.setWordWrap(True)
        btn_cloud_sync = QPushButton("☁️ Настроить облачные сервисы")
        btn_cloud_sync.clicked.connect(self._open_cloud_settings)
        cloud_l.addWidget(cloud_desc)
        cloud_l.addWidget(btn_cloud_sync)
        sync_layout.addWidget(cloud_group)
        sync_layout.addStretch()

        self.tabs.addTab(tab_sync, "☁️ Синхронизация")

        # 4. Вкладка: Реквизиты исполнителя (для PDF-счетов)
        tab_invoice = QWidget()
        inv_layout = QVBoxLayout(tab_invoice)
        inv_layout.setSpacing(8)
        inv_layout.setContentsMargins(12, 12, 12, 12)

        inv_layout.addWidget(QLabel("Название компании / ФИО исполнителя:"))
        self.seller_name_edit = QLineEdit(
            self._window.app_settings.get("seller_name", "")
        )
        self.seller_name_edit.setPlaceholderText("ИП Иванов И.И. / ООО «Моя Компания»")
        self.seller_name_edit.setMaxLength(200)
        self.seller_name_edit.editingFinished.connect(self._save_invoice_prefs)
        inv_layout.addWidget(self.seller_name_edit)

        inv_layout.addWidget(QLabel("Банковские реквизиты (для счетов на оплату):"))
        self.seller_requisites_edit = QTextEdit(
            self._window.app_settings.get("seller_requisites", "")
        )
        self.seller_requisites_edit.setMaximumHeight(110)
        self.seller_requisites_edit.setPlaceholderText(
            "ИНН 1234567890\nР/с 40802810...\nБанк: АО «Тинькофф Банк»\nБИК 044525974\nК/с 30101810145250000974"
        )
        inv_layout.addWidget(self.seller_requisites_edit)
        inv_layout.addStretch()

        self.tabs.addTab(tab_invoice, "📄 Реквизиты (PDF)")

        # 5. Вкладка: О программе и Лицензия
        tab_about = QWidget()
        about_layout = QVBoxLayout(tab_about)
        about_layout.setSpacing(10)
        about_layout.setContentsMargins(12, 12, 12, 12)

        btn_about = QPushButton("ℹ️ О программе, разработчиках и лицензии")
        btn_about.clicked.connect(self._window.open_about)
        btn_eula = QPushButton("📜 Лицензионное соглашение (EULA)")
        btn_eula.clicked.connect(self._show_eula)
        about_layout.addWidget(btn_about)
        about_layout.addWidget(btn_eula)
        about_layout.addStretch()

        self.tabs.addTab(tab_about, "⚖️ О программе")

        main_layout.addWidget(self.tabs)

        # Нижняя кнопка закрытия
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.accept)
        main_layout.addWidget(btn_close)

    def accept(self):
        # Сохраняем реквизиты из QTextEdit перед закрытием
        self._save_invoice_prefs()
        super().accept()

    def _save_theme_pref(self, index: int):
        theme_val = "light" if index == 1 else "dark"
        self._window.app_settings["theme"] = theme_val
        self._window.save_settings()

    def _save_lang_pref(self, index: int):
        from ..services.i18n import set_current_language
        lang_val = self.lang_combo.currentData()
        self._window.app_settings["ui_language"] = lang_val
        set_current_language(lang_val)
        self._window.save_settings()

    def _save_mode_pref(self, index: int):
        mode_val = self.mode_combo.currentData()
        self._window.app_settings["app_mode"] = mode_val
        self._window.save_settings()

    def _save_invoice_prefs(self):
        self._window.app_settings["seller_name"] = self.seller_name_edit.text()
        self._window.app_settings["seller_requisites"] = self.seller_requisites_edit.toPlainText()
        self._window.save_settings()

    def _save_deadline_pref(self):
        self._window.app_settings["deadline_notifications"] = self.deadline_notify_cb.isChecked()
        self._window.save_settings()

    def _open_cloud_settings(self):
        from .cloud_settings import CloudSettingsDialog
        CloudSettingsDialog(self._window).exec()

    def _open_telegram_sync(self):
        from .telegram_sync_dialog import TelegramSyncDialog
        TelegramSyncDialog(self._window).exec()

    def _show_eula(self):
        if self._window.show_eula_dialog():
            QMessageBox.information(self, APP_NAME, "Условия лицензионного соглашения приняты.")

    def manual_backup_settings(self):
        """Ручное создание бэкапа с подтверждением"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Резервное копирование")
        msg_box.setText("Вы собираетесь создать резервную копию настроек приложения.")
        msg_box.setInformativeText(
            "Будет создан JSON файл с текущими путями к базе данных и режимом хранения файлов.\n"
            "Это позволит восстановить конфигурацию в случае сбоя или переноса.\n\n"
            "Продолжить?"
        )
        msg_box.setIcon(QMessageBox.Icon.Question)
        
        btn_yes = msg_box.addButton("Создать копию", QMessageBox.ButtonRole.YesRole)
        btn_no = msg_box.addButton("Отмена", QMessageBox.ButtonRole.NoRole)
        
        msg_box.exec()
        
        if msg_box.clickedButton() == btn_yes:
            self._window.backup_settings()
            logger.info("Пользователь вручную создал резервную копию настроек")
            QMessageBox.information(self, "Успех", "Резервная копия настроек успешно создана в папке 'settings_backups'.")

    def change_database_location(self):
        """Изменяет место хранения базы данных"""
        folder = QFileDialog.getExistingDirectory(self, "Выберите новое место для базы данных")
        if not folder:
            return
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Перенос базы данных")
        msg_box.setText("Как вы хотите хранить файлы при переносе базы?")
        msg_box.setInformativeText(
            "Вы можете оставить файлы там, где они сейчас, "
            "или скопировать их в новую папку вместе с базой данных."
        )
        msg_box.setIcon(QMessageBox.Icon.Question)
        
        # Добавляем кнопки с понятным текстом на русском
        btn_leave = msg_box.addButton("Оставить как есть", QMessageBox.ButtonRole.NoRole)
        btn_move = msg_box.addButton("Скопировать в новую базу", QMessageBox.ButtonRole.YesRole)
        btn_cancel = msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        
        msg_box.exec()
        
        clicked_button = msg_box.clickedButton()
        
        if clicked_button == btn_cancel:
            return
            
        move_files = (clicked_button == btn_move)

        try:
            new_db_path = Path(folder) / "pro_database.json"

            if (
                self._window.storage.path.exists()
                and new_db_path.resolve() == self._window.storage.path.resolve()
            ):
                QMessageBox.information(
                    self, "Информация", "База данных уже находится в выбранной папке."
                )
                return

            self._window.save_db()

            if move_files:
                files_folder = Path(folder) / "attached_files"
                files_folder.mkdir(exist_ok=True)

                # Сначала копируем ВСЕ файлы во временный план,
                # и только при полном успехе обновляем пути.
                # Иначе при падении на середине мы получим смесь
                # старых и новых путей и inconsistent БД.
                new_paths = []
                for client in self._window.clients:
                    for order in client.orders:
                        order_folder = files_folder / order.id
                        order_folder.mkdir(exist_ok=True)
                        for file in order.files:
                            if not os.path.exists(file.path):
                                new_paths.append(None)
                                continue

                            new_file_path = order_folder / file.name
                            try:
                                if os.path.isdir(file.path):
                                    new_file_path = order_folder / file.name
                                    shutil.copytree(
                                        file.path,
                                        new_file_path,
                                        dirs_exist_ok=True,
                                    )
                                else:
                                    shutil.copy2(file.path, new_file_path)
                                new_paths.append(str(new_file_path))
                            except Exception as copy_err:
                                logger.error(
                                    "Ошибка копирования %s → %s: %s",
                                    file.path, new_file_path, copy_err,
                                )
                                raise

                # Только после успешного копирования — мутируем.
                idx = 0
                for client in self._window.clients:
                    for order in client.orders:
                        for file in order.files:
                            new_path = new_paths[idx]
                            idx += 1
                            if new_path is not None:
                                file.path = new_path

            if self._window.storage.path.exists():
                shutil.copy2(self._window.storage.path, new_db_path)

            self._window.app_settings['database_path'] = folder
            self._window.rebind_storage(folder, reload_clients=False)

            self._window.save_db()
            self._window.save_settings()

            QMessageBox.information(
                self,
                "Успех",
                f"База данных успешно перенесена в:\n{folder}\n\n"
                f"{'Файлы были скопированы в новую базу данных и привязаны к новому месту' if move_files else 'Файлы остались на старых местах'}"
            )

        except Exception as e:
            logger.error(f"Ошибка переноса базы данных: {e}", exc_info=True)
            QMessageBox.critical(self, "Ошибка", f"Не удалось перенести базу данных: {e}")

    def restore_settings_dialog(self):
        """Диалог восстановления настроек из бэкапа"""
        from ..utils.paths import user_data_path

        backup_dir = str(user_data_path() / "settings_backups")
        if not os.path.exists(backup_dir):
            QMessageBox.information(self, "Инфо", "Папка с резервными копиями пуста.")
            return

        backups = sorted(glob.glob(os.path.join(backup_dir, "crm_settings_*.json")), reverse=True)
        if not backups:
            QMessageBox.information(self, "Инфо", "Нет доступных резервных копий.")
            return

        items = [os.path.basename(b) for b in backups]
        item, ok = QInputDialog.getItem(self, "Восстановление настроек",
                                      "Выберите файл резервной копии:", items, 0, False)

        if ok and item:
            selected_backup = os.path.join(backup_dir, item)
            try:
                with open(selected_backup, "r", encoding="utf-8") as f:
                    new_settings = json.load(f)

                # РебindInstanceLock до перезаписи, чтобы два
                # приложения не делили одну базу.
                self._window.app_settings = new_settings
                self._window.save_settings()

                QMessageBox.information(self, "Успех",
                                      "Настройки восстановлены. Перезапустите приложение для применения изменений.")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось восстановить настройки: {e}")
