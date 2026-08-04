import math
import tempfile
import unittest
from pathlib import Path

from src.models import Client, Order, ProjectFile
from src.services.backup import create_full_backup_zip
from src.storage import _parse_clients_list
from src.utils.path_safety import (
    is_path_within,
    safe_filename_candidate,
    safe_resolve_within,
    sanitize_path_component,
)


class TestPathSafety(unittest.TestCase):
    def test_sanitize_path_component_basic(self):
        self.assertEqual(sanitize_path_component("a/b:c"), "a_b_c")
        self.assertEqual(sanitize_path_component(""), "_")
        self.assertEqual(sanitize_path_component("."), "_")

    def test_sanitize_strips_control_chars(self):
        self.assertEqual(sanitize_path_component("a\x00b"), "a_b")
        self.assertEqual(sanitize_path_component("a\x07b"), "a_b")

    def test_sanitize_truncates_long_names(self):
        very_long = "a" * 300
        self.assertLessEqual(len(sanitize_path_component(very_long)), 200)

    def test_is_path_within_basic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            inner = root / "sub" / "file.txt"
            inner.parent.mkdir(parents=True, exist_ok=True)
            inner.touch()
            self.assertTrue(is_path_within(inner, root))
            # Создаём файл ЗА пределами root (на родительском уровне)
            outside_dir = root.parent / "outside_dir_test"
            outside_dir.mkdir(exist_ok=True)
            outside = outside_dir / "f.txt"
            outside.touch()
            try:
                self.assertFalse(is_path_within(outside, root))
            finally:
                outside.unlink()
                outside_dir.rmdir()

    def test_is_path_within_rejects_parent_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sibling = root.parent / "evil.txt"
            self.assertFalse(is_path_within(sibling, root))

    def test_safe_filename_candidate_blocks_traversal(self):
        # `..` заменяются на `_`; `/` тоже. Итог: безопасное имя без сегментов.
        cleaned = safe_filename_candidate("../../etc/passwd")
        self.assertNotIn("..", cleaned)
        self.assertNotIn("/", cleaned)
        self.assertNotIn("\\", cleaned)
        self.assertEqual(safe_filename_candidate("normal_file.txt"), "normal_file.txt")
        self.assertEqual(safe_filename_candidate(""), "_")
        self.assertEqual(safe_filename_candidate("..."), "_")

    def test_safe_resolve_within(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            inner = root / "x" / "file.txt"
            inner.parent.mkdir(parents=True, exist_ok=True)
            inner.touch()
            self.assertEqual(
                safe_resolve_within(inner, root),
                inner.resolve(),
            )
            self.assertIsNone(safe_resolve_within(root.parent / "evil", root))


class TestOrderIsFinite(unittest.TestCase):
    """Финансовые значения должны быть конечными числами."""

    def _order(self):
        return Order(id="o1", service_type="X", price=1000.0, advance=500.0)

    def test_add_payment_rejects_nan(self):
        order = self._order()
        with self.assertRaises(ValueError):
            order.add_payment(math.nan, "платеж")

    def test_add_payment_rejects_inf(self):
        order = self._order()
        with self.assertRaises(ValueError):
            order.add_payment(math.inf, "платеж")

    def test_update_price_rejects_nan(self):
        order = self._order()
        with self.assertRaises(ValueError):
            order.update_price(math.nan)

    def test_update_advance_rejects_inf(self):
        order = self._order()
        with self.assertRaises(ValueError):
            order.update_advance(math.inf)


class TestStorageFiniteParsing(unittest.TestCase):
    """NaN/Inf в БД должны превращаться в default, не молча портить долг."""

    def test_nan_amount_in_payment_replaced_with_zero(self):
        data = [
            {
                "id": "c1",
                "name": "Test",
                "orders": [
                    {
                        "id": "o1",
                        "service_type": "X",
                        "price": 1000.0,
                        "advance": 0.0,
                        "payments": [
                            {
                                "id": "p1",
                                "type": "платеж",
                                "amount": float("inf"),
                                "date": "01.01.2026",
                                "note": "",
                            }
                        ],
                        "files": [],
                    }
                ],
            }
        ]
        clients = _parse_clients_list(data)
        payment = clients[0].orders[0].payments[0]
        self.assertEqual(payment.amount, 0.0)
        self.assertFalse(math.isinf(payment.amount))

    def test_nan_price_replaced_with_zero(self):
        data = [
            {
                "id": "c1",
                "name": "Test",
                "orders": [
                    {
                        "id": "o1",
                        "service_type": "X",
                        "price": float("nan"),
                        "advance": 0.0,
                        "payments": [],
                        "files": [],
                    }
                ],
            }
        ]
        clients = _parse_clients_list(data)
        self.assertEqual(clients[0].orders[0].price, 0.0)


class TestBackupArcnameSafety(unittest.TestCase):
    """create_full_backup_zip не должен создавать arcname с '..'."""

    def test_arcname_with_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "db.json"
            db.write_text("[]", encoding="utf-8")
            file_path = root / "f.txt"
            file_path.write_text("x", encoding="utf-8")
            clients = [
                Client(
                    id="c1",
                    name="../../etc",  # После sanitize: .._.._etc
                    orders=[
                        Order(
                            id="o1",
                            service_type="../../passwd",
                            files=[ProjectFile(path=str(file_path), name="f.txt")],
                        )
                    ],
                )
            ]
            zip_path = root / "backup.zip"
            create_full_backup_zip(zip_path, db, clients)
            # Не должно быть arcname, уходящего выше files/
            import zipfile as zf_mod
            with zf_mod.ZipFile(zip_path) as zf:
                for name in zf.namelist():
                    self.assertFalse(
                        ".." in Path(name).parts,
                        f"arcname {name} содержит ..",
                    )


if __name__ == "__main__":
    unittest.main()
