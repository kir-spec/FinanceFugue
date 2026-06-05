import tempfile
import unittest
from pathlib import Path

from src.models import Client
from src.services.folder_import_service import scan_client_folder, apply_folder_scan_results


class TestFolderImportService(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_scan_client_with_order_folders(self):
        client_dir = self.root / "ClientA"
        order_dir = client_dir / "Order1"
        order_dir.mkdir(parents=True)
        (order_dir / "file.txt").write_text("x", encoding="utf-8")

        results = scan_client_folder(str(client_dir), "ClientA")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["order_name"], "Order1")
        self.assertEqual(len(results[0]["files"]), 1)

    def test_apply_creates_client_and_order(self):
        clients: list[Client] = []
        scan = [{
            "client_name": "New",
            "order_name": "Job",
            "files": [("a.txt", str(self.root / "a.txt"))],
        }]
        (self.root / "a.txt").write_text("1", encoding="utf-8")
        imported, orders = apply_folder_scan_results(clients, scan)
        self.assertEqual(imported, 1)
        self.assertEqual(orders, 1)
        self.assertEqual(clients[0].orders[0].files[0].name, "a.txt")


if __name__ == "__main__":
    unittest.main()
