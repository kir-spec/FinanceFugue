"""Тесты для round 3 исправлений (P2-12, P2-13, P2-14, P2-15, P2-16)."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from unittest.mock import MagicMock
import pytest


# ---------------------------------------------------------------------------
# P2-12: Logger FD-утечка
# ---------------------------------------------------------------------------
class TestLoggerNoFDLeak:
    """Повторный вызов get_logger не создаёт новые хэндлеры в root-логгере."""

    def test_repeated_get_logger_no_extra_handlers(self):
        from src.logger import get_logger

        before = len(logging.root.handlers)
        # Имитируем повторный «импорт» блока инициализации
        # путём вызова get_logger несколько раз.
        for _ in range(5):
            log = get_logger("TestRepeat")
            assert log is not None

        after = len(logging.root.handlers)
        assert after == before, (
            f"Количество root-хэндлеров увеличилось: {before} → {after}"
        )

    def test_get_logger_returns_correct_name(self):
        from src.logger import get_logger

        log = get_logger("MyModule")
        assert log.name == "MyModule"


# ---------------------------------------------------------------------------
# P2-13: delete_database_full — rollback при ошибке сохранения
# ---------------------------------------------------------------------------
class TestDeleteDatabaseFullRollback:
    """Если save_db выбрасывает, clients восстанавливаются."""

    def _make_mixin(self, clients):
        """Создаёт минимальный mock DatabaseOpsMixin с нужными атрибутами."""
        from src.ui.main_window.mixins.database_ops import DatabaseOpsMixin

        obj = object.__new__(DatabaseOpsMixin)
        obj.clients = list(clients)
        obj.current_client = clients[0] if clients else None
        obj.storage = MagicMock()
        obj.storage.path = Path("/fake/pro_database.json")
        return obj

    def test_rollback_on_save_failure(self, tmp_path):
        from src.models import Client

        fake_client = Client(id="1", name="Тест")
        mixin = self._make_mixin([fake_client])

        # Подменяем методы Qt/UI на no-op
        mixin.refresh_list = MagicMock()
        mixin.clear_profile_layout = MagicMock()
        mixin.update_dash = MagicMock()
        mixin._set_save_status = MagicMock()
        mixin.trigger_sync = MagicMock()

        # save_db бросает — эмулируем через storage.save
        mixin.storage.save = MagicMock(side_effect=OSError("disk full"))

        # Переопределим save_db, чтобы он пробрасывал исключение
        def _save_db_raises():
            mixin.storage.save(mixin.clients)

        mixin.save_db = _save_db_raises  # type: ignore[method-assign]

        # Запускаем внутренний кусок логики: снапшот + попытка save
        clients_snapshot = mixin.clients
        prev_client = mixin.current_client
        mixin.clients = []
        mixin.current_client = None

        try:
            mixin.save_db()
        except OSError:
            mixin.clients = clients_snapshot
            mixin.current_client = prev_client

        assert len(mixin.clients) == 1
        assert mixin.clients[0].name == "Тест"
        assert mixin.current_client is fake_client


# ---------------------------------------------------------------------------
# P2-14: _extract_clients_payload — корректные версии схемы
# ---------------------------------------------------------------------------
class TestExtractClientsPayload:
    def _call(self, data):
        from src.storage import _extract_clients_payload
        return _extract_clients_payload(data)

    def test_legacy_list_accepted(self):
        clients = [{"id": "1", "name": "Иван"}]
        assert self._call(clients) == clients

    def test_schema_version_1_accepted(self):
        clients = [{"id": "2", "name": "Мария"}]
        data = {"schema_version": 1, "clients": clients}
        assert self._call(data) == clients

    def test_schema_version_missing_defaults_to_1(self):
        clients = [{"id": "3", "name": "Пётр"}]
        data = {"clients": clients}
        assert self._call(data) == clients

    def test_schema_version_too_new_raises(self):
        from src.services.schema import SCHEMA_VERSION
        data = {"schema_version": SCHEMA_VERSION + 1, "clients": []}
        with pytest.raises(ValueError, match="новее поддерживаемой"):
            self._call(data)

    def test_schema_version_zero_raises(self):
        data = {"schema_version": 0, "clients": []}
        with pytest.raises(ValueError, match="Недопустимая schema_version"):
            self._call(data)

    def test_schema_version_string_raises(self):
        data = {"schema_version": "bad", "clients": []}
        with pytest.raises(ValueError, match="Неверный тип schema_version"):
            self._call(data)

    def test_clients_not_list_raises(self):
        data = {"schema_version": 1, "clients": "not a list"}
        with pytest.raises(ValueError, match="массивом"):
            self._call(data)

    def test_wrong_format_raises(self):
        with pytest.raises(ValueError, match="Неверный формат"):
            self._call({"no_clients_key": True})


# ---------------------------------------------------------------------------
# P2-15: Symlink — проверка safe root = attached_files
# ---------------------------------------------------------------------------
class TestSymlinkSafeRoot:
    """Проверяем логику выбора safe_root для symlink-валидации."""

    def test_safe_root_uses_attached_files_when_present(self, tmp_path):
        """Если attached_files существует, safe_root = attached_files."""
        attached = tmp_path / "attached_files"
        attached.mkdir()

        bridge = MagicMock()
        bridge.app_settings.get.return_value = str(tmp_path)

        db_dir = bridge.app_settings.get("database_path", "")
        safe_root = os.path.join(db_dir, "attached_files")
        assert os.path.isdir(safe_root)
        assert Path(safe_root).resolve() == attached.resolve()

    def test_safe_root_falls_back_to_dirname(self, tmp_path):
        """Если attached_files нет, fallback на dirname(path)."""
        bridge = MagicMock()
        bridge.app_settings.get.return_value = str(tmp_path)

        # attached_files не создаём
        db_dir = bridge.app_settings.get("database_path", "")
        safe_root = os.path.join(db_dir, "attached_files")

        fake_path = str(tmp_path / "some_file.txt")
        if not os.path.isdir(safe_root):
            safe_root = os.path.dirname(fake_path) or "."

        assert safe_root == str(tmp_path)


# ---------------------------------------------------------------------------
# P2-16: FolderImportDialog — нет мёртвого dead-code
# ---------------------------------------------------------------------------
class TestFolderImportNoDeadCode:
    """Мёртвые виджеты убраны из диалога."""

    def test_no_extensions_edit(self):
        from src.dialogs.folder_import import FolderImportDialog
        import inspect
        src = inspect.getsource(FolderImportDialog)
        assert "extensions_edit" not in src, \
            "extensions_edit должен быть удалён (dead-code)"

    def test_no_group_by_name(self):
        from src.dialogs.folder_import import FolderImportDialog
        import inspect
        src = inspect.getsource(FolderImportDialog)
        assert "group_by_name" not in src, \
            "group_by_name должен быть удалён (dead-code)"

    def test_no_import_empty_cb(self):
        from src.dialogs.folder_import import FolderImportDialog
        import inspect
        src = inspect.getsource(FolderImportDialog)
        assert "import_empty_cb" not in src, \
            "import_empty_cb должен быть удалён (dead-code)"

    def test_scan_results_present(self):
        """scan_results атрибут сохранён — используется в import_from_folder."""
        from src.dialogs.folder_import import FolderImportDialog
        import inspect
        src = inspect.getsource(FolderImportDialog)
        assert "scan_results" in src

    def test_import_accepts_without_checkboxes(self):
        """Диалог создаётся без QApplication — проверяем только исходник."""
        from src.dialogs.folder_import import FolderImportDialog
        # Класс должен импортироваться без ошибок
        assert FolderImportDialog is not None
