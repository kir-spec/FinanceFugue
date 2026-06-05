import tempfile
import unittest
import zipfile
from pathlib import Path

from src.models import Client, Order, ProjectFile
from src.services.backup import (
    backup_settings_file,
    create_full_backup_zip,
    format_database_size,
    sanitize_path_component,
)


class TestBackup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_settings_backup_prunes(self):
        backup_dir = self.root / "settings_backups"
        for i in range(7):
            backup_settings_file({"n": i}, str(backup_dir), keep=5)
        self.assertEqual(len(list(backup_dir.glob("crm_settings_*.json"))), 5)

    def test_full_backup_zip(self):
        db = self.root / "db.json"
        db.write_text("[]", encoding="utf-8")
        clients = [
            Client(
                id="c1",
                name="Client",
                orders=[
                    Order(
                        id="o1",
                        service_type="S",
                        files=[ProjectFile(path=str(self.root / "f.txt"), name="f.txt")],
                    )
                ],
            )
        ]
        (self.root / "f.txt").write_text("data", encoding="utf-8")
        zip_path = self.root / "backup.zip"
        count = create_full_backup_zip(zip_path, db, clients)
        self.assertEqual(count, 1)
        with zipfile.ZipFile(zip_path) as zf:
            self.assertIn("database.json", zf.namelist())

    def test_sanitize_path_component(self):
        self.assertEqual(sanitize_path_component('a/b:c'), "a_b_c")

    def test_format_size(self):
        db = self.root / "db.json"
        db.write_text("x" * 2048, encoding="utf-8")
        self.assertIn("КБ", format_database_size(db))


if __name__ == "__main__":
    unittest.main()
