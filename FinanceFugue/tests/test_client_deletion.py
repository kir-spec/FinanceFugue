import os
import tempfile
import unittest
from pathlib import Path

from src.models import Client, Order, ProjectFile
from src.services.client_deletion import (
    cleanup_empty_attached_dirs,
    delete_client_files_from_disk,
    is_safe_to_delete,
)


class TestClientDeletion(unittest.TestCase):
    def test_is_safe_to_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            safe = os.path.join(tmp, "attached_files", "f.txt")
            os.makedirs(os.path.dirname(safe), exist_ok=True)
            Path(safe).write_text("x", encoding="utf-8")
            self.assertTrue(is_safe_to_delete(safe, tmp))
            self.assertFalse(is_safe_to_delete("C:\\Windows\\system.ini", tmp))

    def test_delete_client_files_from_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            fpath = os.path.join(tmp, "file.txt")
            Path(fpath).write_text("data", encoding="utf-8")
            client = Client(
                id="c1",
                name="A",
                orders=[
                    Order(
                        id="o1",
                        service_type="S",
                        files=[ProjectFile(path=fpath, name="file.txt")],
                    )
                ],
            )
            removed = delete_client_files_from_disk([client], tmp)
            self.assertEqual(removed, 1)
            self.assertFalse(os.path.exists(fpath))

    def test_cleanup_empty_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            nested = os.path.join(tmp, "attached_files", "order1")
            os.makedirs(nested)
            cleanup_empty_attached_dirs(tmp)
            self.assertFalse(os.path.exists(nested))


if __name__ == "__main__":
    unittest.main()
