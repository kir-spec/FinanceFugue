import copy
import json
import shutil
import time
import os
from typing import Any, Dict, Tuple, Optional, List
from pathlib import Path

import requests
from PySide6.QtCore import QThread, Signal
try:
    from webdav3.client import Client as WebDavClient
except ImportError:
    WebDavClient = None

from ..logger import get_logger

logger = get_logger("CloudSync")

DEFAULT_TELEGRAM_BOT_TOKEN = os.getenv("FINANCE_BOT_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN", "8833825596:AAGFSunb0dXg27TM0W4Ff45W7Vd18I1P95Y"))

# Протокол обмена с ботом. getUpdates использовать нельзя: бот уже
# держит long-poll, а исходящие документы бота в updates не попадают.
SYNC_TAG = "#FINANCE_FUGUE_SYNC"
SNAPSHOT_TAG = "#FINANCE_FUGUE_SNAPSHOT"
PULL_TAG = "#FINANCE_FUGUE_PULL_REQUEST"
TG_API_BASE = "https://api.telegram.org"


def is_crm_database_payload(data: Any) -> bool:
    """Проверяет, что JSON — база FinanceFugue, а не служебный pull-запрос."""
    if isinstance(data, list):
        return True
    if not isinstance(data, dict):
        return False
    if data.get("_sync_action") == "pull":
        return False
    return "clients" in data


def _caption_has(caption: Optional[str], tag: str) -> bool:
    return tag in (caption or "")


def _clients_list(payload: Any) -> List[dict]:
    if isinstance(payload, list):
        return [c for c in payload if isinstance(c, dict)]
    if isinstance(payload, dict):
        clients = payload.get("clients", [])
        if isinstance(clients, list):
            return [c for c in clients if isinstance(c, dict)]
    return []


def _record_id(item: dict, id_key: Optional[str]) -> str:
    if id_key and item.get(id_key):
        return str(item[id_key])
    if item.get("id"):
        return str(item["id"])
    return f"{item.get('name', '')}|{item.get('path', '')}|{item.get('tg_file_id', '')}"


def _merge_record_lists(
    local_items: List[dict],
    remote_items: List[dict],
    prefer_remote: bool,
    id_key: str = "id",
    nested: Optional[List[Tuple[str, str]]] = None,
) -> List[dict]:
    nested = nested or []
    local_map = {_record_id(item, id_key): item for item in local_items if _record_id(item, id_key)}
    remote_map = {_record_id(item, id_key): item for item in remote_items if _record_id(item, id_key)}
    merged: List[dict] = []
    seen = set()
    for key in list(local_map) + [k for k in remote_map if k not in local_map]:
        if key in seen:
            continue
        seen.add(key)
        local_item = local_map.get(key)
        remote_item = remote_map.get(key)
        if local_item and remote_item:
            merged.append(_merge_records(local_item, remote_item, prefer_remote, nested))
        else:
            merged.append(copy.deepcopy(remote_item or local_item))
    return merged


def _merge_records(
    local: dict,
    remote: dict,
    prefer_remote: bool,
    nested: List[Tuple[str, str]],
) -> dict:
    winner, loser = (remote, local) if prefer_remote else (local, remote)
    out = {**copy.deepcopy(loser), **copy.deepcopy(winner)}
    for key, child_id in nested:
        child_nested: List[Tuple[str, str]] = []
        if key == "orders":
            child_nested = [("payments", "id"), ("files", "id")]
        out[key] = _merge_record_lists(
            local.get(key) or [],
            remote.get(key) or [],
            prefer_remote,
            id_key=child_id,
            nested=child_nested,
        )
    return out


def merge_crm_payloads(local: Any, remote: Any, prefer_remote: bool) -> dict:
    """Объединяет две CRM-базы: уникальные записи с обеих сторон сохраняются.

    Для совпадающих id побеждает сторона, которую указали как более свежую.
    Вложенные заказы, платежи и файлы тоже объединяются по id.
    """
    merged_clients = _merge_record_lists(
        _clients_list(local),
        _clients_list(remote),
        prefer_remote,
        id_key="id",
        nested=[("orders", "id")],
    )
    schema = 1
    for payload in (remote, local):
        if isinstance(payload, dict) and payload.get("schema_version"):
            schema = payload["schema_version"]
            break
    envelope: Dict[str, Any] = {"schema_version": schema, "clients": merged_clients}
    if isinstance(remote, dict) and remote.get("exported_at"):
        envelope["exported_at"] = remote["exported_at"]
    return envelope


class TelegramBotSync:
    """
    Класс для работы с двусторонней синхронизацией через Telegram Bot API.
    """
    @staticmethod
    def test_connection(token: str, chat_id: str) -> Tuple[bool, str]:
        token = token.strip() or DEFAULT_TELEGRAM_BOT_TOKEN
        chat_id = chat_id.strip()
        if not token:
            return False, "Токен бота не указан"
        if not chat_id:
            return False, "Telegram Chat ID не указан"

        try:
            # 1. Проверяем валидность токена бота
            me_resp = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
            if me_resp.status_code != 200:
                return False, f"Ошибка токена бота: {me_resp.text}"
            bot_info = me_resp.json().get("result", {})
            bot_name = bot_info.get("first_name", "Bot")
            bot_username = bot_info.get("username", "")

            # 2. Отправляем проверочное сервисное сообщение в чат пользователя
            msg_text = (
                f"🤝 <b>Программа FinanceFugue успешно подключена!</b>\n\n"
                f"✅ Связь между программой на ПК и ботом @{bot_username} установлена.\n"
                f"Время проверки: {time.strftime('%d.%m.%Y %H:%M:%S')}"
            )
            send_resp = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data={"chat_id": chat_id, "text": msg_text, "parse_mode": "HTML"},
                timeout=10
            )
            if send_resp.status_code == 200:
                return True, f"Связь успешна! Бот @{bot_username} доступен, тестовое сообщение отправлено."
            else:
                err_data = send_resp.json()
                return False, f"Бот не может отправить сообщение в Chat ID {chat_id}: {err_data.get('description', send_resp.text)}. Нажмите /start в боте!"
        except Exception as e:
            return False, f"Сетевая ошибка подключения: {e}"

    @staticmethod
    def push_database(db_path: Path, token: str, chat_id: str, settings: Optional[dict] = None) -> Tuple[bool, str]:
        token = token.strip() or DEFAULT_TELEGRAM_BOT_TOKEN
        chat_id = chat_id.strip()
        if not token or not chat_id:
            return False, "Не указан токен или Chat ID"
        
        # 1. Удаляем предыдущее сообщение синхронизации, чтобы в чате не копился мусор
        if settings:
            last_msg_id = settings.get("last_telegram_sync_msg_id")
            if last_msg_id:
                try:
                    requests.post(
                        f"https://api.telegram.org/bot{token}/deleteMessage",
                        json={"chat_id": chat_id, "message_id": last_msg_id},
                        timeout=5
                    )
                except Exception as e:
                    logger.debug("Не удалось удалить старое сообщение синхронизации: %s", e)

        if not db_path.exists():
            try:
                db_path.parent.mkdir(parents=True, exist_ok=True)
                with open(db_path, "w", encoding="utf-8") as f:
                    json.dump({"schema_version": 2, "clients": []}, f, ensure_ascii=False, indent=2)
            except Exception as e:
                return False, f"Файл базы данных не найден: {db_path} ({e})"

        url = f"{TG_API_BASE}/bot{token}/sendDocument"
        timestamp = time.strftime("%d.%m.%Y %H:%M:%S")
        doc_name = "pro_database.json"

        try:
            with open(db_path, "rb") as f:
                response = requests.post(
                    url,
                    data={
                        "chat_id": chat_id,
                        "caption": (
                            f"🔄 <b>Автосинхронизация FinanceFugue</b>\n"
                            f"📅 {timestamp}\n{SYNC_TAG}"
                        ),
                        "parse_mode": "HTML"
                    },
                    files={"document": (doc_name, f)},
                    timeout=30
                )
            if response.status_code == 200:
                res_json = response.json().get("result", {})
                new_msg_id = res_json.get("message_id")
                if settings is not None and new_msg_id:
                    settings["last_telegram_sync_msg_id"] = new_msg_id
                    try:
                        from .settings import save_settings
                        save_settings(settings)
                    except Exception:
                        pass
                if new_msg_id:
                    TelegramBotSync._pin_message(token, chat_id, new_msg_id)
                return True, "База успешно отправлена в Telegram-бота!"
            else:
                return False, f"Telegram API Error ({response.status_code}): {response.text}"
        except Exception as e:
            return False, f"Ошибка отправки в Telegram: {e}"

    @staticmethod
    def _api(token: str, method: str) -> str:
        return f"{TG_API_BASE}/bot{token}/{method}"

    @staticmethod
    def _pin_message(token: str, chat_id: str, message_id: int) -> None:
        try:
            requests.post(
                TelegramBotSync._api(token, "pinChatMessage"),
                json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "disable_notification": True,
                },
                timeout=10,
            )
        except Exception as e:
            logger.debug("Не удалось закрепить сообщение синхронизации: %s", e)

    @staticmethod
    def _get_pinned_message(token: str, chat_id: str) -> Optional[dict]:
        try:
            resp = requests.get(
                TelegramBotSync._api(token, "getChat"),
                params={"chat_id": chat_id},
                timeout=15,
            )
        except Exception as e:
            logger.debug("getChat не удался: %s", e)
            return None
        if resp.status_code != 200:
            return None
        return (resp.json().get("result") or {}).get("pinned_message")

    @staticmethod
    def _download_file_bytes(token: str, file_id: str) -> Tuple[bool, bytes, str]:
        f_resp = requests.get(
            TelegramBotSync._api(token, "getFile"),
            params={"file_id": file_id},
            timeout=10,
        )
        if f_resp.status_code != 200:
            return False, b"", f"Не удалось получить ссылку на файл: {f_resp.text}"
        file_path_tg = (f_resp.json().get("result") or {}).get("file_path")
        if not file_path_tg:
            return False, b"", "Telegram не вернул путь к файлу"
        download_url = f"{TG_API_BASE}/file/bot{token}/{file_path_tg}"
        down_resp = requests.get(download_url, timeout=30)
        if down_resp.status_code != 200:
            return False, b"", f"Ошибка скачивания файла базы: {down_resp.status_code}"
        return True, down_resp.content, ""

    @staticmethod
    def _parse_crm_bytes(content_bytes: bytes) -> Tuple[bool, Any, str]:
        try:
            data = json.loads(content_bytes.decode("utf-8"))
        except Exception as e:
            return False, None, f"Полученный файл поврежден: {e}"
        if not is_crm_database_payload(data):
            return False, None, "Полученный файл не содержит валидных данных CRM"
        return True, data, ""

    @staticmethod
    def _write_database(target_db_path: Path, content_bytes: bytes) -> None:
        if target_db_path.exists():
            backup_path = target_db_path.with_suffix(f".backup_{int(time.time())}.json")
            shutil.copy2(target_db_path, backup_path)
        target_db_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_db_path, "wb") as f:
            f.write(content_bytes)

    @staticmethod
    def _pinned_snapshot_ready(pinned: Optional[dict], *, ignore_message_id: Optional[int] = None) -> bool:
        if not pinned:
            return False
        if ignore_message_id and pinned.get("message_id") == ignore_message_id:
            return False
        caption = pinned.get("caption") or ""
        if _caption_has(caption, PULL_TAG):
            return False
        doc = pinned.get("document") or {}
        fname = (doc.get("file_name") or "").lower()
        if not fname.endswith(".json"):
            return False
        # Только снимок бота. Документ ПК с SYNC_TAG закреплять можно,
        # но забирать его обратно нельзя — там нет данных, внесённых в боте.
        return _caption_has(caption, SNAPSHOT_TAG)

    @staticmethod
    def _send_pull_request(token: str, chat_id: str) -> Tuple[bool, Optional[int], str]:
        payload = {
            "schema_version": 1,
            "clients": [],
            "_sync_action": "pull",
            "_sync_action": "pull",
        }
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            response = requests.post(
                TelegramBotSync._api(token, "sendDocument"),
                data={
                    "chat_id": chat_id,
                    "caption": (
                        f"⬇️ <b>Запрос базы из бота</b>\n"
                        f"{PULL_TAG}"
                    ),
                    "parse_mode": "HTML",
                },
                files={"document": ("sync_pull_request.json", raw)},
                timeout=30,
            )
        except Exception as e:
            return False, None, f"Ошибка отправки запроса в бота: {e}"
        if response.status_code != 200:
            return False, None, f"Telegram API Error ({response.status_code}): {response.text}"
        msg_id = (response.json().get("result") or {}).get("message_id")
        if msg_id:
            TelegramBotSync._pin_message(token, chat_id, msg_id)
        return True, msg_id, ""

    @staticmethod
    def _download_pinned_crm(token: str, pinned: dict) -> Tuple[bool, bytes, str, int]:
        doc = pinned.get("document") or {}
        file_id = doc.get("file_id")
        if not file_id:
            return False, b"", "В закреплённом сообщении нет файла базы", 0
        ok, content, err = TelegramBotSync._download_file_bytes(token, file_id)
        if not ok:
            return False, b"", err, 0
        parsed_ok, _, parse_err = TelegramBotSync._parse_crm_bytes(content)
        if not parsed_ok:
            return False, b"", parse_err, 0
        return True, content, "", int(pinned.get("date") or 0)

    @staticmethod
    def _remember_snapshot_id(settings: Optional[dict], message_id: Optional[int]) -> None:
        if settings is None or not message_id:
            return
        settings["last_telegram_snapshot_msg_id"] = int(message_id)
        try:
            from .settings import save_settings
            save_settings(settings)
        except Exception:
            pass

    @staticmethod
    def _apply_remote_database(
        target_db_path: Path,
        content_bytes: bytes,
        remote_date: int = 0,
        prefer_remote: bool = True,
    ) -> Tuple[bool, str]:
        ok, remote_data, err = TelegramBotSync._parse_crm_bytes(content_bytes)
        if not ok:
            return False, err

        local_data: Any = None
        if target_db_path.exists():
            try:
                local_data = json.loads(target_db_path.read_text(encoding="utf-8"))
            except Exception:
                local_data = None

        if local_data is None or not is_crm_database_payload(local_data):
            TelegramBotSync._write_database(target_db_path, content_bytes)
            return True, ""

        merged = merge_crm_payloads(local_data, remote_data, prefer_remote=prefer_remote)
        raw = json.dumps(merged, ensure_ascii=False, indent=2).encode("utf-8")
        TelegramBotSync._write_database(target_db_path, raw)
        return True, ""

    @staticmethod
    def pull_latest_database(
        target_db_path: Path,
        token: str,
        chat_id: str,
        timeout_sec: float = 25.0,
        settings: Optional[dict] = None,
        force_refresh: bool = True,
        prefer_remote: bool = True,
    ) -> Tuple[bool, str]:
        """Загружает актуальную базу бота через закреплённый снимок (без getUpdates)."""
        token = token.strip() or DEFAULT_TELEGRAM_BOT_TOKEN
        chat_id = chat_id.strip()
        if not token or not chat_id:
            return False, "Не указан токен или Chat ID"

        try:
            if not force_refresh:
                pinned = TelegramBotSync._get_pinned_message(token, chat_id)
                last_id = (settings or {}).get("last_telegram_snapshot_msg_id")
                pinned_id = (pinned or {}).get("message_id")
                if not TelegramBotSync._pinned_snapshot_ready(pinned):
                    return True, "Нет новых данных из бота"
                if last_id and pinned_id == last_id:
                    return True, "Нет новых данных из бота"
                ok, content, err, latest_time = TelegramBotSync._download_pinned_crm(token, pinned)
                if not ok:
                    return False, err
                applied, apply_err = TelegramBotSync._apply_remote_database(
                    target_db_path, content, latest_time, prefer_remote=prefer_remote
                )
                if not applied:
                    return False, apply_err
                TelegramBotSync._remember_snapshot_id(settings, pinned_id)
                stamp = time.strftime("%d.%m.%Y %H:%M", time.localtime(latest_time or time.time()))
                return True, f"База данных успешно загружена из бота! (Обновлена {stamp})"

            previous = TelegramBotSync._get_pinned_message(token, chat_id)
            previous_id = (previous or {}).get("message_id")

            sent, pull_msg_id, send_err = TelegramBotSync._send_pull_request(token, chat_id)
            if not sent:
                return False, send_err

            ignore_ids = {mid for mid in (previous_id, pull_msg_id) if mid}

            deadline = time.time() + timeout_sec
            while time.time() < deadline:
                pinned = TelegramBotSync._get_pinned_message(token, chat_id)
                pinned_id = (pinned or {}).get("message_id")
                if (
                    pinned_id not in ignore_ids
                    and TelegramBotSync._pinned_snapshot_ready(pinned)
                ):
                    ok, content, err, latest_time = TelegramBotSync._download_pinned_crm(token, pinned)
                    if ok:
                        applied, apply_err = TelegramBotSync._apply_remote_database(
                            target_db_path, content, latest_time, prefer_remote=prefer_remote
                        )
                        if not applied:
                            return False, apply_err
                        TelegramBotSync._remember_snapshot_id(settings, pinned_id)
                        stamp = time.strftime("%d.%m.%Y %H:%M", time.localtime(latest_time or time.time()))
                        return True, f"База данных успешно загружена из бота! (Обновлена {stamp})"
                    if err:
                        return False, err
                time.sleep(1.2)

            return False, (
                "Бот не вернул базу за отведённое время. "
                "Убедитесь, что бот запущен, и в чате с ботом нажмите "
                "«Выгрузить базу в программу», затем повторите загрузку."
            )
        except Exception as e:
            return False, f"Ошибка получения базы из бота: {e}"

    @staticmethod
    def full_sync(
        db_path: Path,
        token: str,
        chat_id: str,
        settings: Optional[dict] = None,
        timeout_sec: float = 30.0,
    ) -> Tuple[bool, str]:
        """Забирает свежий снимок бота, сливает с базой ПК и отправляет результат в бота."""
        token = token.strip() or DEFAULT_TELEGRAM_BOT_TOKEN
        chat_id = chat_id.strip()
        pull_ok, pull_msg = TelegramBotSync.pull_latest_database(
            db_path,
            token,
            chat_id,
            timeout_sec=timeout_sec,
            settings=settings,
            force_refresh=True,
            prefer_remote=False,
        )
        if not pull_ok:
            push_ok, push_msg = TelegramBotSync.push_database(
                db_path, token, chat_id, settings=settings
            )
            if push_ok:
                return True, (
                    f"База отправлена в бота. Снимок из бота не получен: {pull_msg}"
                )
            return False, f"{pull_msg} | {push_msg}"

        push_ok, push_msg = TelegramBotSync.push_database(
            db_path, token, chat_id, settings=settings
        )
        if not push_ok:
            return False, f"Базы объединены на ПК, но отправка в бота не удалась: {push_msg}"
        return True, (
            "Двусторонняя синхронизация завершена. "
            "Программа взяла свежие данные бота, сохранила уникальные записи с ПК "
            "и отправила объединённую базу в бота."
        )


class CloudSyncWorker(QThread):
    """
    Фоновый воркер для синхронизации файла базы данных с облаком / ботом.
    """
    # Сигналы: (success, status_message)
    finished_sync = Signal(bool, str)

    def __init__(self, db_path: str, sync_settings: Dict[str, Any], action: str = "push"):
        super().__init__()
        self.db_path = Path(db_path)
        self.settings = sync_settings
        self.action = action

    def run(self):
        try:
            provider = self.settings.get("cloud_provider", self.settings.get("provider", "telegram"))

            if self.action == "test_telegram":
                token = self.settings.get("telegram_token", DEFAULT_TELEGRAM_BOT_TOKEN).strip()
                chat_id = self.settings.get("telegram_chat_id", "").strip()
                success, msg = TelegramBotSync.test_connection(token, chat_id)
                self.finished_sync.emit(success, msg)
                return

            if self.action in ("pull_telegram", "pull_live"):
                token = self.settings.get("telegram_token", DEFAULT_TELEGRAM_BOT_TOKEN).strip()
                chat_id = self.settings.get("telegram_chat_id", "").strip()
                success, msg = TelegramBotSync.pull_latest_database(
                    self.db_path,
                    token,
                    chat_id,
                    settings=self.settings,
                    force_refresh=self.action != "pull_live",
                )
                self.finished_sync.emit(success, msg)
                return

            if self.action == "full_sync":
                token = self.settings.get("telegram_token", DEFAULT_TELEGRAM_BOT_TOKEN).strip()
                chat_id = self.settings.get("telegram_chat_id", "").strip()
                success, msg = TelegramBotSync.full_sync(
                    self.db_path, token, chat_id, settings=self.settings
                )
                self.finished_sync.emit(success, msg)
                return

            if not self.db_path.exists():
                try:
                    self.db_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.db_path, "w", encoding="utf-8") as f:
                        json.dump({"schema_version": 2, "clients": []}, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    self.finished_sync.emit(False, f"База данных не найдена: {e}")
                    return

            if provider == "none":
                self.finished_sync.emit(False, "Провайдер синхронизации не выбран")
                return

            sync_methods = {
                "telegram": self._sync_telegram,
                "yandex": self._sync_yandex,
                "dropbox": self._sync_dropbox,
                "webdav": self._sync_webdav,
                "local": self._sync_local,
            }

            if provider not in sync_methods:
                self.finished_sync.emit(False, f"Неизвестный провайдер: {provider}")
                return

            logger.info("Начинаем синхронизацию через %s...", provider)
            success, msg = sync_methods[provider]()
            
            self.finished_sync.emit(success, msg)
            if success:
                logger.info("Успешная синхронизация: %s", msg)
            else:
                logger.warning("Ошибка синхронизации: %s", msg)

        except Exception as e:
            logger.error("Критическая ошибка синхронизации: %s", e, exc_info=True)
            self.finished_sync.emit(False, f"Ошибка: {e}")

    def _sync_telegram(self) -> Tuple[bool, str]:
        token = self.settings.get("telegram_token", DEFAULT_TELEGRAM_BOT_TOKEN).strip()
        chat_id = self.settings.get("telegram_chat_id", "").strip()
        return TelegramBotSync.push_database(self.db_path, token, chat_id, settings=self.settings)

    def _sync_yandex(self) -> Tuple[bool, str]:
        token = self.settings.get("yandex_token", "").strip()
        if not token:
            return False, "Не указан OAuth токен Яндекс.Диска"

        headers = {"Authorization": f"OAuth {token}"}
        try:
            upload_url_req = requests.get(
                "https://cloud-api.yandex.net/v1/disk/resources/upload",
                params={"path": "app:/pro_database.json", "overwrite": "true"},
                headers=headers,
                timeout=15
            )
            
            if upload_url_req.status_code not in (200, 201):
                upload_url_req = requests.get(
                    "https://cloud-api.yandex.net/v1/disk/resources/upload",
                    params={"path": "/FinanceFugue_Backup.json", "overwrite": "true"},
                    headers=headers,
                    timeout=15
                )
                if upload_url_req.status_code not in (200, 201):
                    return False, f"Yandex API Error (Get URL): {upload_url_req.text}"
            
            upload_url = upload_url_req.json().get("href")
            with open(self.db_path, "rb") as f:
                upload_req = requests.put(upload_url, files={"file": f}, timeout=30)
                
            if upload_req.status_code in (200, 201, 202):
                return True, "Загружено на Яндекс.Диск"
            else:
                return False, f"Yandex API Error (Upload): {upload_req.text}"
        except Exception as e:
            return False, str(e)

    def _sync_dropbox(self) -> Tuple[bool, str]:
        token = self.settings.get("dropbox_token", "").strip()
        if not token:
            return False, "Не указан Access Token Dropbox"

        url = "https://content.dropboxapi.com/2/files/upload"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream",
            "Dropbox-API-Arg": json.dumps({
                "path": "/FinanceFugue_Backup.json",
                "mode": "overwrite",
                "autorename": False,
                "mute": True,
                "strict_conflict": False
            })
        }

        try:
            with open(self.db_path, "rb") as f:
                response = requests.post(url, headers=headers, data=f, timeout=30)
            if response.status_code == 200:
                return True, "Загружено в Dropbox"
            else:
                return False, f"Dropbox API Error: {response.text}"
        except Exception as e:
            return False, str(e)

    def _sync_webdav(self) -> Tuple[bool, str]:
        if WebDavClient is None:
            return False, "Модуль webdav3 не установлен"
        url = self.settings.get("webdav_url", "").strip()
        login = self.settings.get("webdav_login", "").strip()
        password = self.settings.get("webdav_password", "").strip()
        path = self.settings.get("webdav_path", "/FinanceFugue_Backup.json").strip()
        
        if not url or not login or not password:
            return False, "Не заполнены параметры WebDAV"

        if not path.startswith("/"):
            path = "/" + path

        options = {
            'webdav_hostname': url,
            'webdav_login':    login,
            'webdav_password': password
        }

        try:
            client = WebDavClient(options)
            client.upload_sync(remote_path=path, local_path=str(self.db_path))
            return True, f"Загружено по WebDAV ({url})"
        except Exception as e:
            return False, str(e)

    def _sync_local(self) -> Tuple[bool, str]:
        target_dir_str = self.settings.get("local_path", "").strip()
        if not target_dir_str:
            return False, "Не указана папка назначения"
            
        target_dir = Path(target_dir_str)
        if not target_dir.exists() or not target_dir.is_dir():
            return False, f"Папка не найдена: {target_dir}"

        target_path = target_dir / "FinanceFugue_Backup.json"
        try:
            shutil.copy2(self.db_path, target_path)
            return True, f"Скопировано в {target_dir}"
        except Exception as e:
            return False, str(e)
