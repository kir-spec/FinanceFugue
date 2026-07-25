import os
import sys
from pathlib import Path


def app_root() -> Path:
    """Корень приложения: папка FinanceFugue или _MEIPASS при сборке."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def resource_path(name: str) -> Path:
    return app_root() / name


def user_data_path() -> Path:
    """Путь к папке данных пользователя (сохранения, настройки, логи)."""
    app_name = "FinanceFugue"
    if sys.platform == "win32":
        base_dir = os.environ.get("LOCALAPPDATA")
        if base_dir:
            return Path(base_dir) / app_name
        return Path.home() / "AppData" / "Local" / app_name
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / app_name
    else:
        base_dir = os.environ.get("XDG_DATA_HOME")
        if base_dir:
            return Path(base_dir) / app_name
        return Path.home() / ".local" / "share" / app_name

