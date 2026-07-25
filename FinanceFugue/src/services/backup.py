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

logger = logging.getLogger("Backup")

_INVALID_PATH_CHARS = str.maketrans({c: "_" for c in '<>:"/\\|?*'})


def sanitize_path_component(name: str) -> str:
    """Безопасное имя сегмента пути для ZIP и файловой системы Windows."""
    cleaned = name.translate(_INVALID_PATH_CHARS).strip().strip(".")
    return cleaned or "unnamed"


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
        os.remove(backups.pop(0))

    return backup_path


def create_full_backup_zip(
    zip_path: Path,
    database_path: Path,
    clients: List[Client],
) -> int:
    file_count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        if database_path.exists():
            zip_file.write(database_path, "database.json")
        for client in clients:
            for order in client.orders:
                for file in order.files:
                    if os.path.exists(file.path) and os.path.isfile(file.path):
                        arcname = os.path.join(
                            "files",
                            sanitize_path_component(client.name),
                            sanitize_path_component(order.service_type),
                            sanitize_path_component(file.name),
                        )
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
