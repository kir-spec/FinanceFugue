"""Защита от path traversal и небезопасных имён файлов/папок.

Единая точка валидации для всех мест, где пользовательский ввод
превращается в файловый путь (rename, drop, backup, импорт).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

_INVALID_WINDOWS_PATH_CHARS = set('<>:"/\\|?*')
_CONTROL_CHARS = {chr(c) for c in range(32)} - {'\t'}


def sanitize_path_component(name: str) -> str:
    """Удаляет/заменяет символы, запрещённые в Windows-именах.

    - Запрещённые Windows: ``<>:"/\\|?*``
    - Управляющие символы (0x00..0x1F) заменяются на ``_``.
    - Точки в начале и конце удаляются (Windows их не принимает).
    - Результат ограничен 200 символами (защита от MAX_PATH 260).
    """
    if not name:
        return "_"
    cleaned_chars = []
    for ch in name:
        if ch in _INVALID_WINDOWS_PATH_CHARS or ch in _CONTROL_CHARS:
            cleaned_chars.append("_")
        else:
            cleaned_chars.append(ch)
    cleaned = "".join(cleaned_chars).rstrip(".").strip()
    cleaned = cleaned or "_"
    return cleaned[:200]


def is_path_within(child: str | Path, parent: str | Path) -> bool:
    """True, если ``child`` находится внутри ``parent`` (с учётом регистра Windows).

    Использует ``Path.resolve()`` для борьбы с ``..`` и symlink-ами.
    """
    try:
        child_resolved = Path(child).resolve(strict=False)
        parent_resolved = Path(parent).resolve(strict=False)
        # commonpath ищет посимвольно, на Windows нужен normcase
        if os.name == "nt":
            child_resolved = Path(os.path.normcase(str(child_resolved)))
            parent_resolved = Path(os.path.normcase(str(parent_resolved)))
        else:
            child_resolved = Path(os.path.normpath(str(child_resolved)))
            parent_resolved = Path(os.path.normpath(str(parent_resolved)))
        try:
            common = os.path.commonpath([str(child_resolved), str(parent_resolved)])
        except ValueError:
            return False
        return common == str(parent_resolved)
    except (OSError, RuntimeError):
        return False


def safe_resolve_within(
    child: str | Path,
    parent: str | Path,
) -> Path | None:
    """Возвращает ``Path``, если путь внутри ``parent``, иначе None.

    Используется в местах, где новая сущность (drop, rename) добавляется
    в БД: если результат уходит за пределы ``parent`` — None,
    вызывающий код должен отказать.
    """
    try:
        child_resolved = Path(child).resolve(strict=False)
        parent_resolved = Path(parent).resolve(strict=False)
    except (OSError, RuntimeError):
        return None
    if is_path_within(child_resolved, parent_resolved):
        return child_resolved
    return None


_SAFE_NAME_RE = re.compile(r"[^\w.\- ]", re.UNICODE)


def safe_filename_candidate(name: str) -> str:
    """Готовит пользовательский ввод для использования как имя файла.

    - Запрет ``..`` и относительных сегментов (полностью удаляет их).
    - Заменяет небезопасные символы.
    - Если результат пустой — возвращает ``_``.
    """
    if not name:
        return "_"
    name = name.replace("/", "_").replace("\\", "_")
    name = name.replace("..", "_")  # блокируем path traversal
    name = _SAFE_NAME_RE.sub("_", name).rstrip(".").strip()
    return name or "_"
