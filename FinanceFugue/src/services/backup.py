"""Резервное копирование настроек и полных архивов."""
import glob
import json
import logging
import os
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List

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
) -> int:
    """Создаёт полный ZIP-бэкап БД + файлов клиентов.

    Защита от path-traversal: каждый ``arcname`` собирается из
    санитизированных имён и проверяется на отсутствие ``..`` и
    абсолютного префикса.
    """
    file_count = 0
    db_folder = str(database_path.parent) if database_path.parent else os.getcwd()
    attached_root = os.path.join(db_folder, "attached_files")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        if database_path.exists():
            zip_file.write(database_path, "database.json")

        for client in clients:
            safe_client = sanitize_path_component(client.name)
            for order in client.orders:
                safe_order = sanitize_path_component(order.service_type)
                for file in order.files:
                    if not os.path.exists(file.path) or not os.path.isfile(file.path):
                        continue
                    # Бэкапим файлы из attached_files всегда.
                    # Файлы вне attached_files (link-storage) бэкапим
                    # только если они легитимные (нет «..» в resolved-пути
                    # и arcname не выходит за пределы files/).
                    in_attached = is_path_within(file.path, attached_root)
                    if not in_attached:
                        try:
                            resolved = Path(file.path).resolve(strict=False)
                        except (OSError, RuntimeError):
                            continue
                        if ".." in resolved.parts:
                            logger.warning(
                                "Пропуск файла с path-traversal при бэкапе: %s",
                                file.path,
                            )
                            continue

                    arcname = os.path.join(
                        "files", safe_client, safe_order,
                        sanitize_path_component(file.name),
                    )
                    if os.path.isabs(arcname) or ".." in Path(arcname).parts:
                        logger.warning("Подозрительный arcname, пропуск: %s", arcname)
                        continue
                    zip_file.write(file.path, arcname)
                    file_count += 1
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
