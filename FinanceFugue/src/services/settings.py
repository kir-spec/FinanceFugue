"""Загрузка и сохранение crm_settings.json."""
import json
import logging
from pathlib import Path

logger = logging.getLogger("Settings")

DEFAULT_SETTINGS_PATH = Path("crm_settings.json")


class SettingsLoadError(Exception):
    """Файл настроек существует, но не может быть прочитан."""


def load_settings(path: Path = DEFAULT_SETTINGS_PATH) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("Настройки должны быть JSON-объектом")
        return data
    except Exception as e:
        logger.error("Ошибка загрузки настроек %s: %s", path, e, exc_info=True)
        raise SettingsLoadError(str(e)) from e


def save_settings(settings: dict, path: Path = DEFAULT_SETTINGS_PATH) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error("Ошибка сохранения настроек %s: %s", path, e, exc_info=True)
        raise
