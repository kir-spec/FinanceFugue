import json
import logging
import os
from pathlib import Path

from ..utils.paths import user_data_path

logger = logging.getLogger("Settings")


def get_default_settings_path() -> Path:
    legacy_path = Path("crm_settings.json")
    if legacy_path.exists():
        return legacy_path
    
    new_path = user_data_path() / "crm_settings.json"
    new_path.parent.mkdir(parents=True, exist_ok=True)
    return new_path


DEFAULT_SETTINGS_PATH = get_default_settings_path()


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
    temp_path = path.with_suffix(".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
        os.replace(temp_path, path)
    except Exception as e:
        logger.error("Ошибка сохранения настроек %s: %s", path, e, exc_info=True)
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise
