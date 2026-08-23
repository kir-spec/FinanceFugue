"""Заполнение плейсхолдеров в EULA HTML.

Шаблон ``resources/eula.html`` содержит маркеры ``{{REVISION}}``, ``{{DATE}}``,
и (опционально для будущего расширения) ``{{COUNTRY_*}}``.

Аналог ``koshadrive/gui/dialogs/eula_legal_snippets.py``, но упрощённый —
FinanceFugue локальное приложение без облачных/юрисдикционных нюансов.
"""
from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

logger = logging.getLogger("EULA")

# Ревизия + дата подставляются из src/__init__.py.
DEFAULT_REVISION_KEY = "FF-EULA-23.08.2026-1"
DEFAULT_DATE = "23.08.2026"

_EULA_HTML_NAME = "eula.html"
_PLACEHOLDER_RE = re.compile(r"\{\{([A-Z_][A-Z0-9_]*)\}\}")


def _read_template(html_path: Path) -> str:
    try:
        return html_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning(
            "EULA HTML не найден по %s — будет использоваться встроенный fallback",
            html_path,
        )
        return ""


def _render_with_placeholders(template: str, values: dict[str, str]) -> str:
    """Заменяет ``{{KEY}}`` на ``values[KEY]`` для всех найденных маркеров."""

    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in values:
            return values[key]
        # Не нашли замену — оставляем маркер видимым, чтобы привлечь внимание.
        return f"<span style='color:#FF4B2B'>[?{key}?]</span>"

    return _PLACEHOLDER_RE.sub(_sub, template)


def load_eula_html(
    *,
    resources_dir: Path | None = None,
    revision: str = DEFAULT_REVISION_KEY,
    date: str = DEFAULT_DATE,
) -> str:
    """Загрузить и подготовить EULA HTML.

    Parameters
    ----------
    resources_dir :
        Путь к папке ``resources``. По умолчанию ищется относительно CWD
        (для запуска из исходников) и относительно ``sys._MEIPASS``
        (для PyInstaller-сборки).
    revision :
        Редакция EULA (например, ``"FF-EULA-04.08.2026-1"``).
    date :
        Дата редакции.
    """
    candidates: list[Path] = []
    if resources_dir is not None:
        candidates.append(Path(resources_dir) / _EULA_HTML_NAME)
    candidates.append(Path("resources") / _EULA_HTML_NAME)
    # Поддержка frozen-exe
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "resources" / _EULA_HTML_NAME)

    template = ""
    for candidate in candidates:
        if candidate.exists():
            template = _read_template(candidate)
            break

    if not template:
        return (
            "<p><strong>Пользовательское соглашение</strong></p>"
            f"<p>Редакция {revision} · {date}</p>"
            "<p><em>Полный текст EULA устанавливается из файла "
            "resources/eula.html в дистрибутиве.</em></p>"
        )

    return _render_with_placeholders(
        template,
        {
            "REVISION": revision,
            "DATE": date,
        },
    )
