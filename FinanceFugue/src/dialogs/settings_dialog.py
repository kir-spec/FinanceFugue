import os
import shutil
import glob
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QMessageBox, QFileDialog, QCheckBox, QGroupBox, QInputDialog,
)

from ..logger import get_logger
from .. import APP_NAME
from ..theme import SETTINGS_DIALOG_STYLESHEET

logger = get_logger("Dialogs")

# --- ДИАЛОГ НАСТРОЕК ---
class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self._window = parent
        self.setWindowTitle("Настройки")
        
        self.setStyleSheet(SETTINGS_DIALOG_STYLESHEET)
        
        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
        layout.setSpacing(5)
        
        # Группа управления базой данных
        db_group = QGroupBox("База данных")
        db_group.setObjectName("DatabaseGroup")
        db_layout = QVBoxLayout(db_group)
        db_layout.setSpacing(5)
        db_layout.setContentsMargins(10, 10, 10, 10)
        
        btn_db_location = QPushButton("Выбрать место хранения")
        btn_db_location.clicked.connect(self.change_database_location)
        
        btn_imp_folder = QPushButton("Импорт из папки")
        btn_imp_folder.clicked.connect(self._window.import_from_folder)
        
        btn_exp = QPushButton("Экспорт (JSON)")
        btn_exp.clicked.connect(self._window.export_json)
        
        btn_imp = QPushButton("Импорт (JSON)")
        btn_imp.clicked.connect(self._window.import_json_file)
        
        btn_full = QPushButton("Полный бэкап (ZIP)")
        btn_full.clicked.connect(self._window.export_full_backup)
        
        db_layout.addWidget(btn_db_location)
        db_layout.addWidget(btn_imp_folder)
        db_layout.addWidget(btn_exp)
        db_layout.addWidget(btn_imp)
        db_layout.addWidget(btn_full)
        
        # Кнопка удаления всех файлов
        btn_del_files = QPushButton("🗑 Удалить ВСЕ файлы")
        btn_del_files.clicked.connect(self._window.delete_all_files)
        db_layout.addWidget(btn_del_files)

        # Кнопка удаления всей базы
        btn_del_db = QPushButton("☠ Удалить ВСЮ базу данных")
        btn_del_db.clicked.connect(self._window.delete_database_full)
        db_layout.addWidget(btn_del_db)

        layout.addWidget(db_group)

        # Группа настроек приложения
        settings_group = QGroupBox("Настройки")
        settings_group.setObjectName("SettingsGroup")
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setSpacing(5)
        settings_layout.setContentsMargins(10, 10, 10, 10)
        
        btn_backup_settings = QPushButton("Создать копию настроек")
        btn_backup_settings.clicked.connect(self.manual_backup_settings)
        
        btn_restore_settings = QPushButton("Восстановить настройки")
        btn_restore_settings.clicked.connect(self.restore_settings_dialog)
        
        settings_layout.addWidget(btn_backup_settings)
        settings_layout.addWidget(btn_restore_settings)

        self.deadline_notify_cb = QCheckBox("Уведомления о приближающихся дедлайнах")
        self.deadline_notify_cb.setChecked(
            self._window.app_settings.get("deadline_notifications", True)
        )
        self.deadline_notify_cb.stateChanged.connect(self._save_deadline_pref)
        settings_layout.addWidget(self.deadline_notify_cb)

        layout.addWidget(settings_group)

        legal_group = QGroupBox("Правовая информация")
        legal_group.setObjectName("LegalGroup")
        legal_layout = QVBoxLayout(legal_group)
        legal_layout.setContentsMargins(10, 10, 10, 10)

        btn_about = QPushButton("О программе и лицензии")
        btn_about.clicked.connect(self._window.open_about)
        btn_eula = QPushButton("Перечитать EULA")
        btn_eula.clicked.connect(self._show_eula)
        legal_layout.addWidget(btn_about)
        legal_layout.addWidget(btn_eula)
        layout.addWidget(legal_group)

        layout.addSpacing(10)
        
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
    
    def _save_deadline_pref(self):
        self._window.app_settings["deadline_notifications"] = self.deadline_notify_cb.isChecked()
        self._window.save_settings()

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
