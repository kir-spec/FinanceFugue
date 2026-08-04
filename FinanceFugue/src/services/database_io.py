"""Импорт и экспорт базы данных JSON."""
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from ..models import Client
from ..storage import CRMStorage, _extract_clients_payload, _parse_clients_list


def export_database(path: Path, clients: List[Client]) -> None:
    CRMStorage(path).save(clients)


def load_database_file(path: Path) -> List[Client]:
    return CRMStorage(path).load()


def import_database_with_backup(
    source_path: Optional[Path] = None,
    target_storage: Optional[CRMStorage] = None,
    *,
    preloaded_clients: Optional[List[Client]] = None,
) -> Tuple[List[Client], Optional[Path]]:
    """
    Загружает клиентов из файла. Возвращает (clients, backup_path).
    backup_path создаётся только если целевая база уже существовала.

    Поддерживает два варианта:
    * ``source_path``+``target_storage`` — загрузить из файла.
    * ``preloaded_clients``+``target_storage`` — клиенты уже загружены
      вызывающим кодом (preview в UI). Без двойного парсинга JSON.
    """
    if preloaded_clients is not None:
        imported = preloaded_clients
    elif source_path is not None:
        imported = load_database_file(source_path)
    else:
        raise ValueError("Нужен source_path или preloaded_clients")
    if not imported:
        raise ValueError("Файл не содержит данных")

    backup_path = None
    if target_storage is not None and target_storage.path.exists():
        backup_path = target_storage.path.with_suffix(
            f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        shutil.copy2(target_storage.path, backup_path)
    return imported, backup_path


def parse_database_json_text(text: str) -> List[Client]:
    """Парсинг JSON для тестов и валидации без записи на диск."""
    data = json.loads(text)
    return _parse_clients_list(_extract_clients_payload(data))
