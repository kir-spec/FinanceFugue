import sys
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication, QWidget

from src.models import Client, Order, ProjectFile
from src.ui.app_bridge import AppBridge


class _StubWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.app_settings = {}
        self.clients = [
            Client(id="c1", name="A", orders=[Order(id="o1", service_type="X")])
        ]
        self.storage = type("S", (), {"path": Path(tempfile.gettempdir()) / "db.json"})()
        self.current_client = self.clients[0]
        self.cleared = False
        self.refreshed = False

    def clear_profile_layout(self):
        self.cleared = True

    def refresh_list(self):
        self.refreshed = True

    def export_client_files(self):
        pass

    def export_client_orders(self):
        pass


class TestAppBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.window = _StubWindow()
        self.bridge = AppBridge(self.window)
        self.saved = False
        self.bridge.save_requested.connect(lambda: setattr(self, "saved", True))

    def test_remove_file_from_order(self):
        order = self.window.clients[0].orders[0]
        f = ProjectFile(path="/tmp/f.txt", name="f.txt")
        order.files.append(f)
        self.assertTrue(self.bridge.remove_file_from_order(f, order))
        self.assertTrue(self.saved)
        self.assertEqual(order.files, [])

    def test_remove_client(self):
        client = self.window.clients[0]
        self.bridge.remove_client(client)
        self.assertEqual(self.window.clients, [])
        self.assertTrue(self.window.cleared)
        self.assertTrue(self.saved)


if __name__ == "__main__":
    unittest.main()
