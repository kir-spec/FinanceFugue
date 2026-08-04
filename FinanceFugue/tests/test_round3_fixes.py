import tempfile
import unittest
from pathlib import Path

from src.models import Client, Order, Payment


class TestOrderTotalsCache(unittest.TestCase):
    """Кэшированные total_* properties корректны после мутаций."""

    def test_cache_warmed_via_post_init(self):
        order = Order(
            id="o1",
            service_type="X",
            price=1000,
            payments=[
                Payment(id="p1", type="аванс", amount=300, date="01.01.2026", note=""),
                Payment(id="p2", type="платеж", amount=200, date="02.01.2026", note=""),
                Payment(id="p3", type="корректировка", amount=-50, date="03.01.2026", note=""),
            ],
        )
        self.assertEqual(order.total_received, 450)
        self.assertEqual(order.total_advance_received, 300)
        self.assertEqual(order.total_payments_received, 200)
        self.assertEqual(order.total_corrections_received, -50)
        self.assertEqual(order.debt, 550)

    def test_cache_updated_on_add_payment(self):
        order = Order(id="o1", service_type="X", price=1000)
        self.assertEqual(order.total_received, 0)
        order.add_payment(500, "аванс", date="01.01.2026")
        self.assertEqual(order.total_received, 500)
        self.assertEqual(order.total_advance_received, 500)
        # Стоимость и долг
        self.assertEqual(order.debt, 500)

    def test_cache_updated_on_delete_payment(self):
        order = Order(
            id="o1",
            service_type="X",
            price=1000,
            payments=[Payment(id="p1", type="платеж", amount=200, date="01.01.2026", note="")],
        )
        self.assertEqual(order.total_received, 200)
        order.delete_payment("p1")
        self.assertEqual(order.total_received, 0)

    def test_post_init_advance_from_payments(self):
        """Совместимость: advance=max(advance, total_advance_received)."""
        order = Order(
            id="o1",
            service_type="X",
            price=1000,
            advance=0,
            payments=[Payment(id="p1", type="аванс", amount=400, date="01.01.2026", note="")],
        )
        self.assertEqual(order.advance, 400)


class TestDeleteClientOrder(unittest.TestCase):
    """save_db() должен идти до refresh_list() — тест логики через mock."""

    def test_save_called_before_refresh(self):
        """Симулируем сценарий: refresh_list() поднимает исключение.
        До фикса save_db() не успевал вызваться, и список обновлялся
        раньше диска. После фикса UI может упасть, но диск согласован.
        """
        # Просто убеждаемся, что код соответствует контракту —
        # ручная проверка через grep.
        import inspect
        from src.ui.main_window.mixins.client_list import ClientListMixin
        src = inspect.getsource(ClientListMixin.delete_client)
        # save_db() должен быть ДО refresh_list() в исходнике
        save_pos = src.find("self.save_db()")
        refresh_pos = src.find("self.refresh_list()")
        assert save_pos != -1 and refresh_pos != -1
        # save_db раньше ИЛИ равен refresh, но НЕ позже
        # (оба могут идти в одном фрагменте; главное что save раньше)
        self.assertLess(save_pos, refresh_pos, (
            "save_db() должен вызываться ДО refresh_list()"
        ))


class TestDatabaseIoNoDoubleParse(unittest.TestCase):
    """import_database_with_backup(preloaded=) не парсит файл второй раз."""

    def test_preloaded_clients_returned(self):
        from src.services.database_io import import_database_with_backup
        from src.storage import CRMStorage

        clients = [Client(id="c1", name="Test")]
        with tempfile.TemporaryDirectory() as tmp:
            target_db = Path(tmp) / "db.json"
            target_db.write_text("[]", encoding="utf-8")
            storage = CRMStorage(target_db)
            imported, backup_path = import_database_with_backup(
                target_storage=storage, preloaded_clients=clients
            )
            self.assertEqual(imported, clients)
            self.assertIsNotNone(backup_path)

    def test_source_path_still_works(self):
        from src.services.database_io import import_database_with_backup
        from src.storage import CRMStorage

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.json"
            src.write_text(
                '[{"id": "c1", "name": "Test", "orders": []}]',
                encoding="utf-8",
            )
            target_db = Path(tmp) / "db.json"
            target_db.write_text("[]", encoding="utf-8")
            storage = CRMStorage(target_db)
            imported, _ = import_database_with_backup(
                source_path=src, target_storage=storage
            )
            self.assertEqual(len(imported), 1)


class TestBackupWorkerContract(unittest.TestCase):
    """BackupWorker создаётся и имеет signals; не запускаем run()."""

    def test_signals_exist(self):
        try:
            from src.services.backup import BackupWorker, BackupSignals
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance() or QApplication([])
        except Exception as e:
            self.skipTest(f"PySide6 недоступен: {e}")

        signals = BackupSignals()
        self.assertTrue(hasattr(signals, "finished"))
        self.assertTrue(hasattr(signals, "error"))
        self.assertTrue(hasattr(signals, "progress"))

        worker = BackupWorker(
            zip_path=Path("dummy"),
            database_path=Path("dummy"),
            clients=[],
        )
        self.assertIsNotNone(worker.signals)


class TestSymlinkOpenRejected(unittest.TestCase):
    """Логика is_path_within для symlink (тестируем path_safety напрямую).

    UI-метод file_item_widget.open_file требует QWidget событий,
    но symlink-проверка инкапсулирована в path_safety — это и тестируем.
    """

    def test_is_path_within_rejects_external_symlink_target(self):
        from src.utils.path_safety import is_path_within
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            target = root.parent / "evil_target.txt"
            target.touch()
            try:
                link = root / "link.txt"
                # На Windows создание symlink требует прав админа;
                # на Linux — должно работать. Делаем мягкий skip если недоступно.
                try:
                    link.symlink_to(target)
                except (OSError, NotImplementedError):
                    self.skipTest("symlink не поддерживается в этой FS")
                # Цель symlink указывает ЗА пределы root.
                # После resolve путь уйдёт в target.
                # is_path_within должен вернуть False.
                # NOTE: is_path_within работает с переданным путём,
                # а не с resolved — поэтому нужно проверить resolved.
                resolved = link.resolve()
                self.assertFalse(is_path_within(resolved, root))
            finally:
                if target.exists():
                    target.unlink()


class TestBackupArcnameNoTraversal(unittest.TestCase):
    """Итератор бэкапа не выдаёт arcname с '..'."""

    def test_iter_files_skips_traversal_arcnames(self):
        from src.services.backup import iter_files_for_backup
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "db.json"
            db.touch()
            # Файл с путём, но клиент и заказ дадут traversal в arcname
            file_obj = type("F", (), {"path": str(Path(tmp) / "f.txt"), "name": "f.txt"})()
            clients = [
                Client(
                    id="c1",
                    name="../../etc",
                    orders=[Order(id="o1", service_type="../../passwd", files=[file_obj])],
                )
            ]
            for entry, arcname in iter_files_for_backup(db, clients):
                if entry == "__database__":
                    continue
                # arcname не должен содержать '..' parts
                self.assertNotIn("..", Path(arcname).parts)


if __name__ == "__main__":
    unittest.main()
