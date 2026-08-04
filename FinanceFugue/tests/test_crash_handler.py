import tempfile
import unittest
from pathlib import Path

from src.utils.crash_handler import write_crash


class TestCrashHandler(unittest.TestCase):
    def test_write_crash_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            from src.utils import paths as p

            original = p.user_data_path
            p.user_data_path = lambda: Path(tmp)
            try:
                result = write_crash(
                    ValueError,
                    ValueError("test crash"),
                    None,
                )
            finally:
                p.user_data_path = original

            self.assertIsNotNone(result)
            self.assertTrue(result.exists(), f"{result} not created")
            text = result.read_text(encoding="utf-8")
            self.assertIn("test crash", text)
            self.assertIn("FinanceFugue crash report", text)

    def test_write_crash_handles_io_error(self):
        """Если директорию создать нельзя, write_crash должен не упасть."""
        with tempfile.TemporaryDirectory() as tmp:
            # Передаём путь на файл (не директорию) → Path.mkdir(parent=True) упадёт
            broken_path = Path(tmp) / "file.txt"
            broken_path.write_text("x", encoding="utf-8")
            from src.utils import paths as p
            original = p.user_data_path
            p.user_data_path = lambda: broken_path  # logs/ в файле — упадёт
            try:
                result = write_crash(RuntimeError, RuntimeError("x"), None)
                # Должен вернуть None или Path без исключения
                self.assertTrue(result is None or isinstance(result, Path))
            finally:
                p.user_data_path = original


if __name__ == "__main__":
    unittest.main()
