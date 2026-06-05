"""Импорт и экспорт базы данных JSON."""
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from ..models import Client
from ..storage import CRMStorage, _extract_clients_payload, _parse_clients_list


def export_database(path: Path, clients: List[Client]) -> None:
    CRMStorage(path).save(clients)


def load_database_file(path: Path) -> List[Client]:
    return CRMStorage(path).load()


def import_database_with_backup(
    source_path: Path,
    target_storage: CRMStorage,
) -> Tuple[List[Client], Path | None]:
    """
    Загружает клиентов из файла. Возвращает (clients, backup_path).
    backup_path создаётся только если целевая база уже существовала.
    """
    imported = load_database_file(source_path)
    if not imported:
        raise ValueError("Файл не содержит данных")

    backup_path = None
    if target_storage.path.exists():
        backup_path = target_storage.path.with_suffix(
            f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        shutil.copy2(target_storage.path, backup_path)
    return imported, backup_path


def parse_database_json_text(text: str) -> List[Client]:
    """Парсинг JSON для тестов и валидации без записи на диск."""
    data = json.loads(text)
    return _parse_clients_list(_extract_clients_payload(data))
