import json
import tempfile
import unittest
from pathlib import Path

from src.models import Client, Order
from src.services.crm_sync_payload import (
    build_sync_envelope,
    load_clients_for_sync,
    merge_active_and_archive,
    persist_clients_after_pull,
    split_active_and_archive,
)
from src.services.client_stats import calculate_client_stats
from src.storage import CRMStorage


class TestCrmSyncPayload(unittest.TestCase):
    def test_archive_roundtrip_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "pro_database.json"
            arch = Path(tmp) / "pro_archive.json"
            o = Order(id="O1", service_type="Mix", price=1000, advance=500, status="В работе")
            o.add_payment(500, payment_type="аванс")
            o.add_payment(500, payment_type="платеж")
            active = [Client(id="C1", name="A", orders=[])]
            archived = [Client(id="C1", name="A", orders=[o])]
            CRMStorage(db).save(active)
            CRMStorage(arch).save(archived)

            merged = load_clients_for_sync(db)
            self.assertEqual(len(merged[0].orders), 1)
            self.assertTrue(merged[0].orders[0].is_archived)

            env = build_sync_envelope(db)
            self.assertEqual(env["clients"][0]["orders"][0]["status"], "Завершен")

            db2 = Path(tmp) / "pro_database2.json"
            persist_clients_after_pull(db2, env)
            active2 = CRMStorage(db2).load()
            arch2 = CRMStorage(db2.parent / "pro_archive.json").load()
            self.assertEqual(len(active2[0].orders), 0)
            self.assertEqual(len(arch2[0].orders), 1)
            stats = calculate_client_stats(active2[0])
            self.assertEqual(stats["completed_orders"], 0)
            full = merge_active_and_archive(active2, arch2)
            stats2 = calculate_client_stats(full[0])
            self.assertEqual(stats2["completed_orders"], 1)


if __name__ == "__main__":
    unittest.main()
