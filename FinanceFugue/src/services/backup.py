"""Резервное копирование настроек и полных архивов."""
import glob
import json
import logging
import os
import traceback
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List

from PySide6.QtCore import QObject, QRunnable, Signal

from ..models import Client
from ..utils.paths import user_data_path
from ..utils.path_safety import sanitize_path_component, is_path_within

logger = logging.getLogger("Backup")


def backup_settings_file(    settings: dict,
    backup_dir: str = None,
    keep: int = 5,
) -> Path:
    if backup_dir is None:
        backup_dir = str(user_data_path() / "settings_backups")

    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_path = Path(backup_dir) / f"crm_settings_{timestamp}.json"
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)

    backups = sorted(glob.glob(os.path.join(backup_dir, "crm_settings_*.json")))
    while len(backups) > keep:
        try:
            os.remove(backups.pop(0))
        except OSError as e:
            logger.warning("Не удалось удалить старый бэкап: %s", e)

    return backup_path


def create_full_backup_zip(
    zip_path: Path,
    database_path: Path,
    clients: List[Client],
    *,
    on_progress: "callable | None" = None,
) -> int:
    """Создаёт полный ZIP-бэкап БД + файлов клиентов.

    Защита от path-traversal: каждый ``arcname`` собирается из
    санитизированных имён и проверяется на отсутствие ``..`` и
    абсолютного префикса.

    ``on_progress(done, total)`` — опциональный callback для UI-progress.
    """
    items = list(iter_files_for_backup(database_path, clients))
    total = len(items)

    file_count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for idx, (entry, arcname) in enumerate(items, 1):
            if entry == "__database__":
                if database_path.exists():
                    zip_file.write(database_path, "database.json")
            else:
                zip_file.write(entry.path, arcname)
                file_count += 1
            if on_progress is not None:
                try:
                    on_progress(idx, total)
                except Exception as e:  # noqa: BLE001
                    # Ошибка UI callback не должна ломать бэкап.
                    logger.debug("on_progress callback raised: %s", e)
    return file_count


def format_database_size(database_path: Path) -> str:
    if not database_path.exists():
        return "0 байт"
    size_bytes = os.path.getsize(database_path)
    if size_bytes < 1024:
        return f"{size_bytes} байт"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} КБ"
    return f"{size_bytes / (1024 * 1024):.1f} МБ"


def iter_files_for_backup(database_path: Path, clients: List[Client]):
    """Генератор файлов для бэкапа, отдаёт (file_obj, arcname_or_skip).

    Выделено из ``create_full_backup_zip``, чтобы ``BackupWorker``
    мог сообщать прогресс по каждому файлу.
    """
    db_folder = str(database_path.parent) if database_path.parent else os.getcwd()
    attached_root = os.path.join(db_folder, "attached_files")

    yield ("__database__", None)  # маркер для database.json

    for client in clients:
        safe_client = sanitize_path_component(client.name)
        for order in client.orders:
            safe_order = sanitize_path_component(order.service_type)
            for file in order.files:
                if not os.path.exists(file.path) or not os.path.isfile(file.path):
                    continue
                in_attached = is_path_within(file.path, attached_root)
                if not in_attached:
                    try:
                        resolved = Path(file.path).resolve(strict=False)
                    except (OSError, RuntimeError):
                        continue
                    if ".." in resolved.parts:
                        continue
                arcname = os.path.join(
                    "files", safe_client, safe_order,
                    sanitize_path_component(file.name),
                )
                if os.path.isabs(arcname) or ".." in Path(arcname).parts:
                    continue
                yield (file, arcname)

class BackupSignals(QObject):
    finished = Signal(int)  # file_count
    error = Signal(str)
    progress = Signal(int, int)  # done, total


class BackupWorker(QRunnable):
    """`QRunnable` для создания полного ZIP-бэкапа без блокировки UI.

    Используется в `ui/main_window/mixins/database_ops.py`.
    Связь через сигналы `BackupSignals` (потокобезопасно через Qt event-loop).
    """

    def __init__(
        self,
        zip_path: Path,
        database_path: Path,
        clients: List[Client],
    ):
        super().__init__()
        self.zip_path = zip_path
        self.database_path = database_path
        self.clients = clients
        self.signals = BackupSignals()

    def run(self) -> None:
        try:
            count = create_full_backup_zip(
                self.zip_path,
                self.database_path,
                self.clients,
                on_progress=lambda d, t: self.signals.progress.emit(d, t),
            )
            self.signals.finished.emit(count)
        except Exception as e:  # noqa: BLE001
            logger.error("Backup failed: %s", e, exc_info=True)
            self.signals.error.emit(
                f"{e}\n{traceback.format_exc(limit=2)}"
            )
