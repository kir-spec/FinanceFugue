"""Пути к ресурсам приложения (dev и PyInstaller)."""
import sys
from pathlib import Path


def app_root() -> Path:
    """Корень приложения: папка FinanceFugue или _MEIPASS при сборке."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def resource_path(name: str) -> Path:
    return app_root() / name
