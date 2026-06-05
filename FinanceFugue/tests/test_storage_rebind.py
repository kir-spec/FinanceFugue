import tempfile
import unittest
from pathlib import Path
from src.storage import CRMStorage
from src.utils.instance_lock import InstanceLock


class TestStorageRebind(unittest.TestCase):
    def test_different_db_paths_have_independent_locks(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_a = Path(tmp) / "a" / "pro_database.json"
            db_b = Path(tmp) / "b" / "pro_database.json"
            db_a.parent.mkdir(parents=True)
            db_b.parent.mkdir(parents=True)

            lock_a = InstanceLock(db_a.with_suffix(".lock"))
            lock_b = InstanceLock(db_b.with_suffix(".lock"))
            lock_a.acquire()
            lock_b.acquire()
            lock_b.release()
            lock_a.release()

    def test_rebind_storage_releases_old_lock(self):
        from src.ui.main_window.mixins.database_ops import DatabaseOpsMixin

        with tempfile.TemporaryDirectory() as tmp:
            folder_a = Path(tmp) / "a"
            folder_b = Path(tmp) / "b"
            folder_a.mkdir()
            folder_b.mkdir()
            CRMStorage(str(folder_a / "pro_database.json")).save([])

            window = DatabaseOpsMixin()
            window.storage = CRMStorage(str(folder_a / "pro_database.json"))
            window._instance_lock = InstanceLock(window.storage.path.with_suffix(".lock"))
            window._instance_lock.acquire()
            try:
                window.rebind_storage(str(folder_b), reload_clients=True)
                self.assertEqual(window.storage.path, folder_b / "pro_database.json")
            finally:
                window._instance_lock.release()


if __name__ == "__main__":
    unittest.main()
