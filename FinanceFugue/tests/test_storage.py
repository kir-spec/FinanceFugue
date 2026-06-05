import json
import tempfile
import unittest
from pathlib import Path

from src.models import Client, Order
from src.storage import CRMStorage, DatabaseLoadError
from src.services.schema import SCHEMA_VERSION


class TestCRMStorage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "pro_database.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_missing_returns_empty(self):
        storage = CRMStorage(self.db_path)
        self.assertEqual(storage.load(), [])

    def test_save_and_load_roundtrip(self):
        storage = CRMStorage(self.db_path)
        clients = [
            Client(
                id="c1",
                name="Test",
                orders=[Order(id="o1", service_type="Work", price=100.0)],
            )
        ]
        storage.save(clients)
        raw = json.loads(self.db_path.read_text(encoding="utf-8"))
        self.assertEqual(raw["schema_version"], SCHEMA_VERSION)
        self.assertEqual(len(raw["clients"]), 1)
        loaded = storage.load()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].name, "Test")
        self.assertEqual(loaded[0].orders[0].price, 100.0)

    def test_legacy_list_format_loads(self):
        legacy = [{"id": "c1", "name": "Legacy", "orders": []}]
        self.db_path.write_text(json.dumps(legacy), encoding="utf-8")
        loaded = CRMStorage(self.db_path).load()
        self.assertEqual(loaded[0].name, "Legacy")

    def test_corrupt_db_raises(self):
        self.db_path.write_text("{broken", encoding="utf-8")
        storage = CRMStorage(self.db_path)
        with self.assertRaises(DatabaseLoadError):
            storage.load()

    def test_missing_client_id_raises(self):
        self.db_path.write_text(
            json.dumps({"schema_version": 1, "clients": [{"name": "X"}]}),
            encoding="utf-8",
        )
        with self.assertRaises(DatabaseLoadError):
            CRMStorage(self.db_path).load()

    def test_atomic_replace_keeps_data_on_rewrite(self):
        storage = CRMStorage(self.db_path)
        storage.save([Client(id="c1", name="A")])
        storage.save([Client(id="c2", name="B")])
        loaded = storage.load()
        self.assertEqual(loaded[0].name, "B")
        self.assertTrue(self.db_path.exists())
        self.assertFalse(self.db_path.with_suffix(".tmp").exists())


if __name__ == "__main__":
    unittest.main()
