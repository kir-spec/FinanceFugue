import json
import tempfile
import unittest
from pathlib import Path

from src.models import Client, Order, ProjectFile
from src.services.database_io import export_database


class TestExportDatabase(unittest.TestCase):
    def test_metadata_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.json"
            export_database(path, [], file_storage_mode="copy")
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("__meta__", data)
            self.assertEqual(data["__meta__"]["file_storage_mode"], "copy")
            self.assertIn("exported_at", data["__meta__"])

    def test_copy_mode_with_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = Path(tmp) / "source"
            src_dir.mkdir()
            src_file = src_dir / "test.txt"
            src_file.write_text("hello", encoding="utf-8")

            out = Path(tmp) / "out.json"
            clients = [
                Client(
                    id="c1",
                    name="Test",
                    orders=[
                        Order(
                            id="o1",
                            service_type="X",
                            files=[
                                ProjectFile(path=str(src_file), name="test.txt"),
                            ],
                        )
                    ],
                )
            ]
            export_database(
                out, clients,
                file_storage_mode="copy",
                include_files=True,
            )
            files_dir = Path(tmp) / "files"
            self.assertTrue(files_dir.exists(), "files/ должна быть создана")
            copied = list(files_dir.glob("*.txt"))
            self.assertEqual(len(copied), 1)
            # И БД должна указывать на новый путь
            data = json.loads(out.read_text(encoding="utf-8"))
            file_path_in_db = data["clients"][0]["orders"][0]["files"][0]["path"]
            self.assertIn("files", file_path_in_db)

    def test_link_mode_does_not_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            src_file = Path(tmp) / "test.txt"
            src_file.write_text("hello", encoding="utf-8")

            out = Path(tmp) / "out.json"
            clients = [
                Client(
                    id="c1",
                    name="Test",
                    orders=[
                        Order(
                            id="o1",
                            service_type="X",
                            files=[
                                ProjectFile(path=str(src_file), name="test.txt"),
                            ],
                        )
                    ],
                )
            ]
            export_database(out, clients, file_storage_mode="link", include_files=False)
            files_dir = Path(tmp) / "files"
            self.assertFalse(files_dir.exists())
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["__meta__"]["file_storage_mode"], "link")


if __name__ == "__main__":
    unittest.main()
