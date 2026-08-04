"""Общая логика удаления файлов клиентов с диска."""
from __future__ import annotations

import logging
import os
import shutil
from typing import Iterable

from ..models import Client
from ..utils.path_safety import is_path_within

logger = logging.getLogger("ClientDeletion")


def is_safe_to_delete(file_path: str, safe_root: str) -> bool:
    """True, если ``file_path`` находится внутри ``safe_root``.

    Использует ``Path.resolve()`` (разворачивает ``..`` и symlink-и)
    и учитывает регистр Windows.
    """
    return is_path_within(file_path, safe_root)


def delete_client_files_from_disk(
    clients: Iterable[Client],
    db_folder: str,
    *,
    log: logging.Logger | None = None,
) -> int:
    """Удаляет файлы заказов с диска. Возвращает число успешных удалений."""
    log = log or logger
    removed = 0
    for client in clients:
        for order in client.orders:
            for file in order.files:
                if not os.path.exists(file.path):
                    continue
                if not is_safe_to_delete(file.path, db_folder):
                    log.warning("Пропуск небезопасного пути: %s", file.path)
                    continue
                try:
                    if os.path.isdir(file.path):
                        shutil.rmtree(file.path)
                    else:
                        os.remove(file.path)
                    removed += 1
                except OSError as e:
                    log.error("Не удалось удалить %s: %s", file.path, e)
    return removed


def cleanup_empty_attached_dirs(db_folder: str, *, log: logging.Logger | None = None) -> None:
    log = log or logger
    attached_files_dir = os.path.join(db_folder, "attached_files")
    if not os.path.exists(attached_files_dir):
        return
    try:
        for root, dirs, _files in os.walk(attached_files_dir, topdown=False):
            for name in dirs:
                try:
                    os.rmdir(os.path.join(root, name))
                except OSError:
                    pass
    except OSError as e:
        log.debug("Очистка пустых папок: %s", e)
