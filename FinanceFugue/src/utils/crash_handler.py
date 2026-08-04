"""Crash-reporting через sys.excepthook + PySide excepthook.

Любое необработанное исключение (включая краши в Qt-слотах) пишет
полный traceback в ``logs/crash_<timestamp>.log`` + ``logs/crm_<date>.log``.

При запуске из EXE PyInstaller выводит краш-окно (если не PySide crash
handler). Этот модуль дополняет их: лог-файл, который пользователь
может прислать в поддержку.
"""
from __future__ import annotations

import io
import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("CrashHandler")


def _crash_log_dir() -> Path:
    """Директория для crash-логов; создаём при первом вызове."""
    from src.utils.paths import user_data_path

    logs_dir = user_data_path() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def _format_excepthook(type_, value, tb) -> str:
    """Полный traceback в строку, включая locals (кастомизированно)."""
    buf = io.StringIO()
    # Без locals — может содержать незакрытые файлы, сокеты и т.д.
    traceback.print_exception(type_, value, tb, file=buf, chain=True)
    return buf.getvalue()


def write_crash(exc_type, exc_value, exc_tb) -> None:
    """Записать traceback в crash-файл с timestamp."""
    try:
        text = _format_excepthook(exc_type, exc_value, exc_tb)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = _crash_log_dir() / f"crash_{timestamp}.log"
        path.write_text(
            f"=== FinanceFugue crash report ===\n"
            f"timestamp: {datetime.now().isoformat()}\n"
            f"python: {sys.version}\n"
            f"platform: {sys.platform}\n"
            f"pid: {os.getpid()}\n"
            f"argv: {sys.argv}\n"
            f"\n--- Traceback ---\n{text}\n",
            encoding="utf-8",
        )
        logger.critical(
            "Необработанное исключение (см. %s):\n%s", path, text
        )
        return path
    except Exception as e:  # noqa: BLE001
        # Если даже crash-лог не пишется — отдаём в stderr
        sys.stderr.write(f"CRASH: failed to write crash log: {e}\n")
        return None


def install() -> None:
    """Установить глобальный excepthook для Python + Qt."""
    _original_hook = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb):
        write_crash(exc_type, exc_value, exc_tb)
        # Передаём дальше — стандартное поведение (для PyInstaller crash window).
        if _original_hook is not None and _original_hook is not sys.excepthook:
            try:
                _original_hook(exc_type, exc_value, exc_tb)
            except Exception:  # noqa: BLE001
                pass
        # Напечатать в stderr (для отладки из консоли)
        try:
            traceback.print_exception(exc_type, exc_value, exc_tb)
        except Exception:  # noqa: BLE001
            sys.stderr.write(f"CRASH: {exc_value!r}\n")

    sys.excepthook = _hook

    # PySide excepthook для крашей в Qt-слотах.
    try:
        from PySide6.QtCore import qInstallMessageHandler, QtMsgType
    except ImportError:
        return

    def _qt_hook(msg_type, ctx, msg):
        """Qt-сообщения → logger."""
        if msg_type == QtMsgType.QtDebugMsg:
            logger.debug("Qt: %s", msg)
        elif msg_type == QtMsgType.QtInfoMsg:
            logger.info("Qt: %s", msg)
        elif msg_type == QtMsgType.QtWarningMsg:
            logger.warning("Qt: %s", msg)
        elif msg_type in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
            # Fatal — пишем как crash
            logger.critical("Qt fatal: %s", msg)
            crash_path = _crash_log_dir() / f"crash_qt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            crash_path.write_text(
                f"=== FinanceFugue Qt crash ===\n"
                f"timestamp: {datetime.now().isoformat()}\n"
                f"message: {msg}\n"
                f"context: {ctx}\n",
                encoding="utf-8",
            )

    try:
        qInstallMessageHandler(_qt_hook)
    except Exception:  # noqa: BLE001
        pass
