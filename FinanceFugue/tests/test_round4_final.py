"""Тесты Round 4 — P1-10 (atomic lock rebind) и P3-4 (schema migration)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# P1-10: atomic rebind — новый lock захватывается до снятия старого
# ---------------------------------------------------------------------------
class TestRebindAtomicLock:
    """rebind_storage: acquire new lock before release of old."""

    def _make_mixin(self, tmp_path: Path):
        """Создаёт минимальный mock DatabaseOpsMixin."""
        from src.ui.main_window.mixins.database_ops import DatabaseOpsMixin

        obj = object.__new__(DatabaseOpsMixin)
        obj.storage = MagicMock()
        obj.storage.path = tmp_path / "pro_database.json"
        obj.clients = []
        obj.current_client = None
        return obj

    def test_acquire_before_release_order(self, tmp_path: Path):
        """Новый lock.acquire() вызывается ДО старого lock.release()."""
        from src.ui.main_window.mixins.database_ops import DatabaseOpsMixin

        obj = self._make_mixin(tmp_path)

        # Создаём mock старого lock
        old_lock = MagicMock()
        obj._instance_lock = old_lock

        # Перехватываем порядок вызовов
        call_order: list[str] = []
        new_lock_mock = MagicMock()
        new_lock_mock.acquire.side_effect = lambda: call_order.append("new.acquire")
        old_lock.release.side_effect = lambda: call_order.append("old.release")

        # Создаём новую папку БД
        new_db_folder = tmp_path / "new_db"
        new_db_folder.mkdir()
        (new_db_folder / "pro_database.json").write_text(
            '{"schema_version": 1, "clients": []}', encoding="utf-8"
        )

        # Патчим InstanceLock чтобы вернуть наш mock
        from unittest.mock import patch
        with patch(
            "src.ui.main_window.mixins.database_ops.InstanceLock",
            return_value=new_lock_mock,
        ):
            # Мокаем Qt-методы которых нет в тесте
            obj.storage = MagicMock()
            obj.storage.load.return_value = []
            with patch(
                "src.ui.main_window.mixins.database_ops.CRMStorage",
                return_value=obj.storage,
            ):
                DatabaseOpsMixin.rebind_storage(obj, str(new_db_folder))

        assert call_order == ["new.acquire", "old.release"], (
            f"Неправильный порядок: {call_order}. "
            "Новый lock должен захватываться ДО снятия старого."
        )

    def test_acquire_failure_keeps_old_lock(self, tmp_path: Path):
        """Если новый lock.acquire() бросает, старый lock остаётся нетронутым."""
        from src.ui.main_window.mixins.database_ops import DatabaseOpsMixin
        from src.utils.instance_lock import InstanceLockError

        obj = self._make_mixin(tmp_path)
        old_lock = MagicMock()
        obj._instance_lock = old_lock

        failing_lock = MagicMock()
        failing_lock.acquire.side_effect = InstanceLockError("locked")

        new_db_folder = tmp_path / "busy_db"
        new_db_folder.mkdir()

        with pytest.raises(InstanceLockError):
            from unittest.mock import patch
            with patch(
                "src.ui.main_window.mixins.database_ops.InstanceLock",
                return_value=failing_lock,
            ):
                with patch(
                    "src.ui.main_window.mixins.database_ops.QMessageBox"
                ):
                    DatabaseOpsMixin.rebind_storage(obj, str(new_db_folder))

        # Старый lock не должен быть отпущен
        old_lock.release.assert_not_called()


# ---------------------------------------------------------------------------
# P3-4: schema migration — migrate_order / migrate_client
# ---------------------------------------------------------------------------
class TestSchemaMigration:
    """migrate_order и migrate_client заполняют отсутствующие поля."""

    def test_migrate_order_fills_missing_fields(self):
        from src.services.schema import migrate_order, ORDER_DEFAULTS

        raw = {"id": "x", "service_type": "test"}
        result = migrate_order(raw)

        for field in ORDER_DEFAULTS:
            assert field in result, f"Поле {field!r} не заполнено migrate_order"

    def test_migrate_order_does_not_overwrite_existing(self):
        from src.services.schema import migrate_order

        raw = {"id": "x", "service_type": "Фото", "price": 9999.0, "currency": "EUR"}
        result = migrate_order(raw)

        assert result["service_type"] == "Фото"
        assert result["price"] == 9999.0
        assert result["currency"] == "EUR"

    def test_migrate_client_fills_missing_fields(self):
        from src.services.schema import migrate_client, CLIENT_DEFAULTS

        raw = {"id": "c1", "name": "Иван"}
        result = migrate_client(raw)

        for field in CLIENT_DEFAULTS:
            assert field in result, f"Поле {field!r} не заполнено migrate_client"

    def test_migrate_client_does_not_overwrite_existing(self):
        from src.services.schema import migrate_client

        raw = {"id": "c1", "name": "Иван", "email": "ivan@example.com", "notes": "VIP"}
        result = migrate_client(raw)

        assert result["email"] == "ivan@example.com"
        assert result["notes"] == "VIP"


class TestStorageMigrationIntegration:
    """Загрузка JSON без новых полей не вызывает ошибок."""

    def test_load_order_without_notes_field(self, tmp_path: Path):
        """БД с заказами без поля notes загружается без KeyError."""
        db_path = tmp_path / "pro_database.json"
        # Формат без поля "notes" в заказе — как старые версии
        data = {
            "schema_version": 1,
            "clients": [
                {
                    "id": "c1",
                    "name": "Тест",
                    "orders": [
                        {
                            "id": "o1",
                            "service_type": "Фото",
                            # "notes" отсутствует намеренно
                        }
                    ],
                }
            ],
        }
        db_path.write_text(json.dumps(data), encoding="utf-8")

        from src.storage import CRMStorage
        storage = CRMStorage(str(db_path))
        clients = storage.load()

        assert len(clients) == 1
        assert clients[0].name == "Тест"
        assert len(clients[0].orders) == 1

    def test_load_client_without_requisites(self, tmp_path: Path):
        """Клиент без поля requisites загружается с дефолтным значением ''."""
        db_path = tmp_path / "pro_database.json"
        data = {
            "schema_version": 1,
            "clients": [
                {
                    "id": "c2",
                    "name": "Без реквизитов",
                    # "requisites" отсутствует
                }
            ],
        }
        db_path.write_text(json.dumps(data), encoding="utf-8")

        from src.storage import CRMStorage
        storage = CRMStorage(str(db_path))
        clients = storage.load()

        assert clients[0].requisites == ""


# ---------------------------------------------------------------------------
# P3-10: instance_lock.__all__
# ---------------------------------------------------------------------------
class TestInstanceLockPublicAPI:
    def test_all_defined(self):
        import src.utils.instance_lock as m
        assert hasattr(m, "__all__")

    def test_all_contains_public_names(self):
        from src.utils.instance_lock import __all__
        assert "InstanceLock" in __all__
        assert "InstanceLockError" in __all__

    def test_private_not_in_all(self):
        from src.utils.instance_lock import __all__
        assert "_pid_alive" not in __all__
        assert "_read_pid" not in __all__
        assert "_clear_lock" not in __all__
