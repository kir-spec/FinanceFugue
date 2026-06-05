import tempfile
import unittest
from pathlib import Path

from src.services.settings import load_settings, save_settings, SettingsLoadError


class TestSettings(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "crm_settings.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_roundtrip(self):
        data = {"database_path": "/tmp", "first_run_completed": True}
        save_settings(data, self.path)
        loaded = load_settings(self.path)
        self.assertEqual(loaded, data)

    def test_missing_returns_empty(self):
        self.assertEqual(load_settings(self.path), {})

    def test_corrupt_raises(self):
        self.path.write_text("{bad", encoding="utf-8")
        with self.assertRaises(SettingsLoadError):
            load_settings(self.path)


if __name__ == "__main__":
    unittest.main()
