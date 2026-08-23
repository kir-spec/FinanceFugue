import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.services.cloud_sync import (
    PULL_TAG,
    SNAPSHOT_TAG,
    SYNC_TAG,
    TelegramBotSync,
    is_crm_database_payload,
    merge_crm_payloads,
)


def _json_response(payload, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    resp.text = json.dumps(payload)
    resp.content = b""
    return resp


def _bytes_response(content: bytes, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.content = content
    resp.text = ""
    resp.json.return_value = {}
    return resp


class TestCrmPayload(unittest.TestCase):
    def test_accepts_clients_envelope(self):
        self.assertTrue(is_crm_database_payload({"schema_version": 1, "clients": []}))

    def test_rejects_pull_request(self):
        self.assertFalse(is_crm_database_payload({"clients": [], "_sync_action": "pull"}))
        self.assertFalse(is_crm_database_payload({"clients": [], "_sync_action": "pull"}))


class TestTelegramPull(unittest.TestCase):
    def test_pull_always_requests_fresh_snapshot(self):
        """Старый pin игнорируется: ПК просит новый снимок и ждёт другой message_id."""
        snapshot = {
            "schema_version": 1,
            "clients": [{"id": "c1", "name": "Анна", "orders": []}],
        }
        raw = json.dumps(snapshot, ensure_ascii=False).encode("utf-8")
        calls = {"chat": 0}

        def fake_get(url, params=None, timeout=None, **kwargs):
            self.assertNotIn("getUpdates", url)
            if url.endswith("/getChat"):
                calls["chat"] += 1
                if calls["chat"] == 1:
                    return _json_response({
                        "ok": True,
                        "result": {
                            "pinned_message": {
                                "message_id": 10,
                                "date": 1700000000,
                                "caption": f"устаревший {SNAPSHOT_TAG}",
                                "document": {"file_id": "old", "file_name": "pro_database.json"},
                            }
                        },
                    })
                return _json_response({
                    "ok": True,
                    "result": {
                        "pinned_message": {
                            "message_id": 42,
                            "date": 1700000100,
                            "caption": f"свежий {SNAPSHOT_TAG}",
                            "document": {
                                "file_id": "file-1",
                                "file_name": "pro_database.json",
                            },
                        }
                    },
                })
            if url.endswith("/getFile"):
                return _json_response({"ok": True, "result": {"file_path": "docs/db.json"}})
            if "/file/bot" in url:
                return _bytes_response(raw)
            self.fail(f"Неожиданный GET {url}")

        def fake_post(url, data=None, json=None, files=None, timeout=None, **kwargs):
            if url.endswith("/sendDocument"):
                caption = (data or {}).get("caption", "")
                self.assertIn(PULL_TAG, caption)
                return _json_response({"ok": True, "result": {"message_id": 55}})
            if url.endswith("/pinChatMessage"):
                return _json_response({"ok": True, "result": True})
            self.fail(f"Неожиданный POST {url}")

        with tempfile.TemporaryDirectory() as td, \
             patch("src.services.cloud_sync.requests.get", side_effect=fake_get), \
             patch("src.services.cloud_sync.requests.post", side_effect=fake_post), \
             patch("src.services.cloud_sync.time.sleep"):
            target = Path(td) / "pro_database.json"
            ok, msg = TelegramBotSync.pull_latest_database(target, "123:token", "999", timeout_sec=2)
            self.assertTrue(ok, msg)
            data = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(data["clients"][0]["name"], "Анна")

    def test_pull_sends_request_when_no_snapshot(self):
        calls = {"chat": 0}

        def fake_get(url, params=None, timeout=None, **kwargs):
            self.assertNotIn("getUpdates", url)
            if url.endswith("/getChat"):
                calls["chat"] += 1
                if calls["chat"] == 1:
                    return _json_response({"ok": True, "result": {}})
                return _json_response({
                    "ok": True,
                    "result": {
                        "pinned_message": {
                            "message_id": 77,
                            "date": 1700000001,
                            "caption": SNAPSHOT_TAG,
                            "document": {"file_id": "file-2", "file_name": "pro_database.json"},
                        }
                    },
                })
            if url.endswith("/getFile"):
                return _json_response({"ok": True, "result": {"file_path": "docs/db.json"}})
            if "/file/bot" in url:
                body = json.dumps({"schema_version": 1, "clients": [{"id": "c2", "name": "Борис"}]})
                return _bytes_response(body.encode("utf-8"))
            self.fail(f"Неожиданный GET {url}")

        def fake_post(url, data=None, json=None, files=None, timeout=None, **kwargs):
            if url.endswith("/sendDocument"):
                caption = (data or {}).get("caption", "")
                self.assertIn(PULL_TAG, caption)
                return _json_response({"ok": True, "result": {"message_id": 55}})
            if url.endswith("/pinChatMessage"):
                return _json_response({"ok": True, "result": True})
            self.fail(f"Неожиданный POST {url}")

        with tempfile.TemporaryDirectory() as td, \
             patch("src.services.cloud_sync.requests.get", side_effect=fake_get), \
             patch("src.services.cloud_sync.requests.post", side_effect=fake_post), \
             patch("src.services.cloud_sync.time.sleep"):
            target = Path(td) / "pro_database.json"
            ok, msg = TelegramBotSync.pull_latest_database(
                target, "123:token", "999", timeout_sec=2
            )
            self.assertTrue(ok, msg)
            data = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(data["clients"][0]["name"], "Борис")

    def test_snapshot_ready_ignores_pc_push(self):
        pinned = {
            "message_id": 1,
            "caption": SYNC_TAG,
            "document": {"file_name": "pro_database.json", "file_id": "x"},
        }
        self.assertFalse(TelegramBotSync._pinned_snapshot_ready(pinned))

    def test_live_pull_uses_new_snapshot_without_request(self):
        snapshot = {"schema_version": 1, "clients": [{"id": "c1", "name": "Катя"}]}
        raw = json.dumps(snapshot).encode("utf-8")
        posted = {"send": 0}

        def fake_get(url, params=None, timeout=None, **kwargs):
            if url.endswith("/getChat"):
                return _json_response({
                    "ok": True,
                    "result": {
                        "pinned_message": {
                            "message_id": 90,
                            "date": 1700000200,
                            "caption": SNAPSHOT_TAG,
                            "document": {"file_id": "f90", "file_name": "pro_database.json"},
                        }
                    },
                })
            if url.endswith("/getFile"):
                return _json_response({"ok": True, "result": {"file_path": "docs/db.json"}})
            if "/file/bot" in url:
                return _bytes_response(raw)
            self.fail(f"Неожиданный GET {url}")

        def fake_post(url, data=None, json=None, files=None, timeout=None, **kwargs):
            posted["send"] += 1
            self.fail(f"Live-pull не должен слать документы: {url}")

        with tempfile.TemporaryDirectory() as td, \
             patch("src.services.cloud_sync.requests.get", side_effect=fake_get), \
             patch("src.services.cloud_sync.requests.post", side_effect=fake_post):
            target = Path(td) / "pro_database.json"
            settings = {"last_telegram_snapshot_msg_id": 10}
            ok, msg = TelegramBotSync.pull_latest_database(
                target, "123:token", "999", settings=settings, force_refresh=False
            )
            self.assertTrue(ok, msg)
            self.assertEqual(posted["send"], 0)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["clients"][0]["name"], "Катя")
            self.assertEqual(settings["last_telegram_snapshot_msg_id"], 90)


class TestCrmMerge(unittest.TestCase):
    def test_union_keeps_unique_clients(self):
        local = {"schema_version": 2, "clients": [{"id": "pc", "name": "ПК", "orders": []}]}
        remote = {"schema_version": 2, "clients": [{"id": "bot", "name": "Бот", "orders": []}]}
        merged = merge_crm_payloads(local, remote, prefer_remote=True)
        ids = {c["id"] for c in merged["clients"]}
        self.assertEqual(ids, {"pc", "bot"})

    def test_overlapping_prefers_requested_side(self):
        local = {"clients": [{"id": "c1", "name": "Старое с ПК", "orders": [{"id": "o-pc"}]}]}
        remote = {"clients": [{"id": "c1", "name": "Новое из бота", "orders": [{"id": "o-bot"}]}]}
        bot_wins = merge_crm_payloads(local, remote, prefer_remote=True)
        self.assertEqual(bot_wins["clients"][0]["name"], "Новое из бота")
        order_ids = {o["id"] for o in bot_wins["clients"][0]["orders"]}
        self.assertEqual(order_ids, {"o-pc", "o-bot"})
        pc_wins = merge_crm_payloads(local, remote, prefer_remote=False)
        self.assertEqual(pc_wins["clients"][0]["name"], "Старое с ПК")


if __name__ == "__main__":
    unittest.main()
