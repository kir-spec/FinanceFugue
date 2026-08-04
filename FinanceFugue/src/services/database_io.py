"""Импорт и экспорт базы данных JSON."""
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from ..models import Client
from ..storage import CRMStorage, _extract_clients_payload, _parse_clients_list


def export_database(
    path: Path,
    clients: List[Client],
    *,
    file_storage_mode: Optional[str] = None,
    include_files: bool = False,
) -> Path:
    """Сохраняет БД в JSON.

    Параметры:
        path: целевой файл.
        clients: данные.
        file_storage_mode: 'copy' или 'link' из настроек. Сохраняется в
            ``__meta__.storage_mode`` чтобы импортёр видел режим источника.
        include_files: True → скопировать файлы в ``<export_dir>/files/``
            рядом с JSON. False → только метаданные (пути в БД остаются
            абсолютными или относительными как есть).

    Возвращает путь к созданному JSON. Если ``include_files=True``,
    возвращает ``path``, рядом с которым создана папка ``files/``.
    """
    if include_files and file_storage_mode == "copy":
        # Папка files/ рядом с JSON
        export_dir = path.parent
        files_dest = export_dir / "files"
        files_dest.mkdir(exist_ok=True)
        for client in clients:
            for order in client.orders:
                for file in order.files:
                    if not file.path:
                        continue
                    src = Path(file.path)
                    if not src.exists() or not src.is_file():
                        continue
                    dest = files_dest / f"{client.name}_{order.service_type}_{file.name}".replace(
                        "/", "_"
                    )
                    try:
                        shutil.copy2(src, dest)
                        file.path = str(dest)
                    except OSError:
                        # Не прерываем экспорт из-за одного файла
                        continue

    meta = {
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "file_storage_mode": file_storage_mode or "unknown",
        "include_files": include_files,
    }

    CRMStorage(path).save(clients)
    # Дописываем meta после save (минимальное изменение исходного формата).
    # Читаем сохранённый JSON, модифицируем верхний уровень, пишем обратно.
    tmp = path.with_suffix(".meta.tmp")
    with open(path, "r", encoding="utf-8") as f:
        envelope = json.load(f)
    envelope["__meta__"] = meta
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(envelope, f, ensure_ascii=False, indent=4)
    Path(tmp).replace(path)
    return path


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
