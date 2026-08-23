import os
import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import (
    QFileDialog, QMessageBox, QDialog, QProgressDialog,
)

from .... import APP_NAME
from ....dialogs import FolderImportDialog
from ....services.backup import (
    BackupWorker, create_full_backup_zip, format_database_size,
)
from ....services.database_io import export_database, import_database_with_backup
from ....services.folder_import_service import apply_folder_scan_results, scan_client_folder
from ....storage import CRMStorage, DatabaseLoadError
from ....utils.instance_lock import InstanceLock, InstanceLockError
from ....logger import get_logger

logger = get_logger("MainWindow")


class DatabaseOpsMixin:
    def rebind_storage(self, database_folder: str, *, reload_clients: bool = True) -> None:
        """Переназначает путь к БД и блокировку экземпляра.

        Порядок: **сначала захватить новый lock, потом отпустить старый**.
        Это исключает окно гонки, в котором другой экземпляр мог бы
        захватить ещё не занятый lock нового пути.

        При ошибке `acquire` нового lock старый остаётся активным,
        состояние приложения не изменяется.
        """
        new_db_path = Path(database_folder) / "pro_database.json"
        new_lock = InstanceLock(new_db_path.with_suffix(".lock"))

        # Атомарная смена: захватываем новый ДО снятия старого.
        try:
            new_lock.acquire()
        except InstanceLockError as e:
            QMessageBox.critical(self, APP_NAME, str(e))
            raise

        # Старый lock отпускаем только после успешного acquire нового.
        if hasattr(self, "_instance_lock") and self._instance_lock is not None:
            self._instance_lock.release()

        self.storage = CRMStorage(str(new_db_path))
        self._instance_lock = new_lock

        if reload_clients:
            try:
                self.clients = self.storage.load()
            except DatabaseLoadError as e:
                QMessageBox.critical(
                    self,
                    APP_NAME,
                    f"Не удалось загрузить базу данных:\n{self.storage.path}\n\n{e}",
                )
                raise

    def save_db(self):
        try:
            self.storage.save(self.clients)
            self.update_dash()
            self._set_save_status("Сохранено")
            self.trigger_sync()
        except Exception as e:
            logger.error("Ошибка сохранения базы данных: %s", e, exc_info=True)
            self._set_save_status(f"Ошибка сохранения: {e}", error=True)
            raise

    def import_dropped_client_folder(self, folder_path: str):
        """Импорт одной папки клиента, перетащенной на список."""
        client_name = os.path.basename(folder_path.rstrip("\\/")).strip()
        existing = next(
            (c for c in self.clients if c.name.strip().lower() == client_name.lower()),
            None,
        )
        if existing:
            answer = QMessageBox.question(
                self,
                "Импорт папки",
                f"Клиент «{client_name}» уже существует.\nДобавить заказы из папки к нему?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        scan_results = scan_client_folder(folder_path, client_name)
        if not scan_results:
            QMessageBox.information(
                self,
                APP_NAME,
                "Не удалось распознать структуру папки.\n"
                "Ожидается: Папка клиента → папки заказов → файлы.",
            )
            return

        imported_count, order_count = apply_folder_scan_results(self.clients, scan_results)
        self.save_db()
        self.refresh_list()
        if self.clients and self.current_client is None:
            self.current_client = self.clients[0]
            self.render_client_profile()
        QMessageBox.information(
            self,
            "Импорт завершён",
            f"Клиент: {client_name}\n"
            f"Новых клиентов: {imported_count}\n"
            f"Создано заказов: {order_count}",
        )

    def get_selected_client(self):
        """Возвращает клиента, выбранного в списке."""
        return self.current_client

    def open_telegram_sync(self):
        """Открывает диалог 2-сторонней синхронизации с Telegram-ботом."""
        from ....dialogs.telegram_sync_dialog import TelegramSyncDialog
        dialog = TelegramSyncDialog(self)
        dialog.exec()

    def reload_database_after_pull(self):
        """Перезагружает базу данных после успешного скачивания (Pull) из Telegram."""
        try:
            self.clients = self.storage.load()
            self.refresh_list()
            self.update_dash()
            if hasattr(self, "db_info_label"):
                self.db_info_label.setText(f"Клиентов: {len(self.clients)}")
            if self.clients:
                self.current_client = self.clients[0]
                self.render_client_profile()
            else:
                self.current_client = None
                self.clear_profile_layout()
            self._set_save_status("Синхронизировано с Telegram")
            self.statusBar().showMessage(f"☁️ База обновлена из Telegram (Клиентов: {len(self.clients)})", 10000)
        except Exception as e:
            logger.error("Ошибка при перезагрузке базы после pull: %s", e, exc_info=True)
            QMessageBox.critical(self, "Ошибка обновления", f"Не удалось перезагрузить данные:\n{e}")

    def trigger_sync(self, force=False):
        """Запускает фоновую синхронизацию с облаком / ботом."""
        import time
        from ....services.cloud_sync import CloudSyncWorker

        provider = self.app_settings.get("cloud_provider", "none")
        auto_tg = self.app_settings.get("auto_telegram_sync", True)
        has_tg_chat = bool(self.app_settings.get("telegram_chat_id"))

        if provider == "none" and not (auto_tg and has_tg_chat):
            return

        # Если включена автосинхронизация с ботом — используем telegram как провайдер
        if auto_tg and has_tg_chat and provider == "none":
            self.app_settings["cloud_provider"] = "telegram"
            provider = "telegram"

        # Защита от слишком частых бэкапов (раз в 15 сек при сохранении, если не force)
        current_time = time.time()
        last_sync = getattr(self, "_last_cloud_sync", 0)
        cooldown = 15 if provider == "telegram" else 180
        
        if not force and (current_time - last_sync) < cooldown:
            return
            
        # Не запускаем, если уже крутится воркер
        if hasattr(self, "cloud_worker") and self.cloud_worker.isRunning():
            return
            
        self.statusBar().showMessage("☁️ Синхронизация с Telegram-ботом...")
        
        self.cloud_worker = CloudSyncWorker(str(self.storage.path), self.app_settings, action="push")
        self.cloud_worker.finished_sync.connect(self._on_sync_finished)
        self.cloud_worker.start()

    def _on_sync_finished(self, success, message):
        import time
        if success:
            self._last_cloud_sync = time.time()
            self.statusBar().showMessage(f"☁️ Синхронизация: {message}", 8000)
        else:
            self.statusBar().showMessage(f"❌ Ошибка синхронизации: {message}", 8000)

    def import_from_folder(self):
        """Импорт клиентов из структуры папок"""
        dialog = FolderImportDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            imported_count, order_count = apply_folder_scan_results(
                self.clients, dialog.scan_results
            )
            self.save_db()
            self.refresh_list()
            if self.clients and self.current_client is None:
                self.current_client = self.clients[0]
                self.render_client_profile()
            QMessageBox.information(
                self,
                "Импорт завершен",
                f"Импортировано клиентов: {imported_count}\n"
                f"Создано заказов: {order_count}\n"
                f"Всего файлов: {sum(len(r['files']) for r in dialog.scan_results)}",
            )

    def export_json(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Экспорт базы данных",
            f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON файлы (*.json)",
        )
        if path:
            try:
                storage_mode = (
                    (self.app_settings or {}).get("file_storage_mode", "copy")
                )
                # Для 'copy' режима — спрашиваем, копировать ли файлы.
                include_files = False
                if storage_mode == "copy":
                    answer = QMessageBox.question(
                        self,
                        "Экспорт с файлами",
                        "Включить файлы клиентов в экспорт?\n"
                        "Файлы будут скопированы в папку 'files/' рядом с JSON.\n"
                        "(Если нет — импортёр увидит только метаданные.)",
                        QMessageBox.StandardButton.Yes
                        | QMessageBox.StandardButton.No,
                    )
                    include_files = answer == QMessageBox.StandardButton.Yes

                export_database(
                    Path(path),
                    self.clients,
                    file_storage_mode=storage_mode,
                    include_files=include_files,
                )
                msg = f"База данных экспортирована в:\n{path}\n"
                if include_files:
                    msg += (
                        f"\nФайлы скопированы в: {Path(path).parent / 'files'}"
                    )
                QMessageBox.information(self, "Успех", msg)
            except Exception as e:
                QMessageBox.critical(
                    self, "Ошибка",
                    f"Не удалось экспортировать базу данных:\n{e}",
                )

    def import_json_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Импорт базы данных",
            "",
            "JSON файлы (*.json)",
        )
        if path:
            try:
                preview = CRMStorage(path).load()
                if not preview:
                    QMessageBox.warning(self, "Внимание", "Выбранный файл не содержит данных.")
                    return
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Подтверждение импорта")
                msg_box.setText(f"Найдено клиентов: {len(preview)}")
                msg_box.setInformativeText("Текущая база данных будет заменена. Продолжить?")
                msg_box.setIcon(QMessageBox.Icon.Warning)
                btn_yes = msg_box.addButton("Да", QMessageBox.ButtonRole.YesRole)
                msg_box.addButton("Нет", QMessageBox.ButtonRole.NoRole)
                msg_box.exec()
                if msg_box.clickedButton() != btn_yes:
                    return
                imported_clients, backup_path = import_database_with_backup(
                    target_storage=self.storage,
                    preloaded_clients=preview,
                )
                self.clients = imported_clients
                self.current_client = None
                self.save_db()
                self.refresh_list()
                self.clear_profile_layout()
                backup_msg = f"\nРезервная копия: {backup_path}" if backup_path else ""
                QMessageBox.information(
                    self,
                    "Успех",
                    f"База данных импортирована.\nКлиентов: {len(imported_clients)}{backup_msg}",
                )
            except DatabaseLoadError:
                QMessageBox.critical(self, "Ошибка", "Неверный или повреждённый файл базы данных.")
            except ValueError as e:
                QMessageBox.critical(self, "Ошибка", str(e))
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось импортировать базу данных:\n{e}")

    def export_full_backup(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Создание резервной копии",
            f"full_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            "ZIP архивы (*.zip)",
        )
        if not path:
            return

        zip_path = Path(path)
        # Маленькая база → бэкапим синхронно (прогресс-бар излишен).
        if len(self.clients) <= 5:
            try:
                file_count = create_full_backup_zip(
                    zip_path, self.storage.path, self.clients
                )
                QMessageBox.information(
                    self,
                    "Резервная копия создана",
                    f"Полная резервная копия успешно создана:\n\nФайл: {path}\n"
                    f"Клиентов: {len(self.clients)}\nФайлов в архиве: {file_count}",
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Ошибка",
                    f"Не удалось создать резервную копию:\n{e}",
                )
            return

        # Большая база → QThreadPool + прогресс-бар.
        progress = QProgressDialog(
            "Создание резервной копии...", "Отмена", 0, 100, self
        )
        progress.setWindowTitle("Бэкап")
        progress.setMinimumDuration(500)  # показать только если >0.5s
        progress.setValue(0)

        worker = BackupWorker(zip_path, self.storage.path, self.clients)

        def _on_progress(done: int, total: int) -> None:
            pct = int(done * 100 / total) if total else 100
            progress.setValue(pct)
            progress.setLabelText(
                f"Создание резервной копии... {done}/{total}"
            )

        def _on_cancel() -> None:
            progress.cancel()
            logger.info("Бэкап отменён пользователем")

        def _on_finished(count: int) -> None:
            progress.close()
            QMessageBox.information(
                self,
                "Резервная копия создана",
                f"Полная резервная копия успешно создана:\n\nФайл: {path}\n"
                f"Клиентов: {len(self.clients)}\nФайлов в архиве: {count}",
            )

        def _on_error(msg: str) -> None:
            progress.close()
            QMessageBox.critical(
                self, "Ошибка",
                f"Не удалось создать резервную копию:\n{msg}",
            )

        worker.signals.progress.connect(_on_progress)
        worker.signals.finished.connect(_on_finished)
        worker.signals.error.connect(_on_error)
        progress.canceled.connect(_on_cancel)

        QThreadPool.globalInstance().start(worker)

    def get_database_size(self):
        return format_database_size(self.storage.path)

    def delete_all_files(self):
        """Удаляет все файлы из базы данных (физически и ссылки)"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Удаление ВСЕХ файлов")
        msg_box.setText("Как вы хотите удалить файлы?")
        msg_box.setInformativeText(
            "Выберите вариант очистки:\n\n"
            "• Удалить только из программы: удалятся ссылки, файлы на диске останутся нетронутыми.\n"
            "• Удалить с компьютера: удалятся ссылки И сами файлы."
        )
        msg_box.setIcon(QMessageBox.Icon.Warning)

        btn_program_only = msg_box.addButton(
            "Удалить только из программы", QMessageBox.ButtonRole.YesRole
        )
        btn_disk_also = msg_box.addButton(
            "Удалить с компьютера", QMessageBox.ButtonRole.DestructiveRole
        )
        btn_cancel = msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        db_folder = os.path.dirname(self.storage.path)
        attached_files_dir = os.path.join(db_folder, "attached_files")

        msg_box.exec()

        clicked = msg_box.clickedButton()

        if clicked == btn_cancel:
            return

        delete_from_disk = clicked == btn_disk_also

        if delete_from_disk:
            warn_box = QMessageBox(self)
            warn_box.setWindowTitle("Удаление файлов")
            warn_box.setText(f"Файлы из папки:\n{attached_files_dir}\n\nбудут удалены.")
            warn_box.setInformativeText("Продолжить?")
            warn_box.setIcon(QMessageBox.Icon.Critical)

            btn_yes = warn_box.addButton("Да", QMessageBox.ButtonRole.YesRole)
            warn_box.addButton("Отмена", QMessageBox.ButtonRole.NoRole)

            warn_box.exec()

            if warn_box.clickedButton() != btn_yes:
                return

        deleted_count = 0

        for client in self.clients:
            for order in client.orders:
                deleted_count += len(order.files)
                order.files = []

        if delete_from_disk and os.path.exists(attached_files_dir):
            try:
                shutil.rmtree(attached_files_dir)
                os.makedirs(attached_files_dir, exist_ok=True)
            except Exception as e:
                logger.error("Ошибка удаления папки с файлами: %s", e)
                QMessageBox.warning(
                    self, "Ошибка", f"Не удалось полностью удалить файлы с диска: {e}"
                )

        self.save_db()
        self.render_client_profile()

        info_text = f"Удалено ссылок на файлы: {deleted_count}"
        if delete_from_disk:
            info_text += "\nФайлы также удалены с диска (из папки базы данных)."
        else:
            info_text += "\nФайлы на диске не были затронуты."

        QMessageBox.information(self, "Успех", info_text)

    def delete_database_full(self):
        """Полное удаление базы данных"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Удаление ВСЕЙ базы данных")
        msg_box.setText("ВНИМАНИЕ! Вы собираетесь удалить ВСЮ базу данных.")
        msg_box.setInformativeText(
            "Это удалит всех клиентов и все заказы из программы.\n"
            "Восстановить данные будет невозможно (если нет бэкапа).\n\n"
            "Что делать с файлами на диске?"
        )
        msg_box.setIcon(QMessageBox.Icon.Critical)

        btn_prog_only = msg_box.addButton(
            "Оставить файлы на диске", QMessageBox.ButtonRole.YesRole
        )
        btn_disk_also = msg_box.addButton(
            "Удалить с диска", QMessageBox.ButtonRole.DestructiveRole
        )
        btn_cancel = msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)

        db_folder = os.path.dirname(self.storage.path)
        attached_files_dir = os.path.join(db_folder, "attached_files")

        msg_box.exec()

        clicked = msg_box.clickedButton()
        if clicked == btn_cancel:
            return

        delete_files_disk = clicked == btn_disk_also

        if delete_files_disk:
            warn_box = QMessageBox(self)
            warn_box.setWindowTitle("Удаление файлов")
            warn_box.setText(f"Файлы из папки:\n{attached_files_dir}\n\nбудут удалены.")
            warn_box.setInformativeText("Продолжить?")
            warn_box.setIcon(QMessageBox.Icon.Critical)

            btn_yes = warn_box.addButton("Да", QMessageBox.ButtonRole.YesRole)
            warn_box.addButton("Отмена", QMessageBox.ButtonRole.NoRole)

            warn_box.exec()

            if warn_box.clickedButton() != btn_yes:
                return

        # --- Snapshot для rollback при ошибке записи ---
        clients_snapshot = self.clients
        prev_client = self.current_client

        self.clients = []
        self.current_client = None

        try:
            self.save_db()
        except Exception as e:
            # Откат: диск не изменён (save_db пишет в .tmp и только потом заменяет),
            # возвращаем in-memory состояние.
            self.clients = clients_snapshot
            self.current_client = prev_client
            logger.error("delete_database_full: сбой сохранения, откат: %s", e)
            QMessageBox.critical(
                self, "Ошибка",
                f"Не удалось очистить базу данных:\n{e}\n\nДанные восстановлены.",
            )
            return

        if delete_files_disk and os.path.exists(attached_files_dir):
            try:
                shutil.rmtree(attached_files_dir)
            except Exception as e:
                logger.error("Ошибка удаления папки файлов: %s", e)
                QMessageBox.warning(
                    self, "Предупреждение",
                    f"База очищена, но не удалось удалить файлы с диска:\n{e}",
                )

        self.refresh_list()
        self.clear_profile_layout()
        self.update_dash()

        msg = "База данных полностью очищена."
        if delete_files_disk:
            msg += "\nФайлы также были удалены с диска."
        else:
            msg += "\nФайлы на диске остались нетронутыми."

        QMessageBox.information(self, "Успех", msg)

