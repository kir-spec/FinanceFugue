import json
import shutil
import time
import os
from typing import Dict, Any, Tuple, Optional, List
from pathlib import Path

import requests
from PySide6.QtCore import QThread, Signal
try:
    from webdav3.client import Client as WebDavClient
except ImportError:
    WebDavClient = None

from ..logger import get_logger

logger = get_logger("CloudSync")

DEFAULT_TELEGRAM_BOT_TOKEN = "8833825596:AAGFSunb0dXg27TM0W4Ff45W7Vd18I1P95Y"

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
    def push_database(db_path: Path, token: str, chat_id: str) -> Tuple[bool, str]:
        token = token.strip() or DEFAULT_TELEGRAM_BOT_TOKEN
        chat_id = chat_id.strip()
        if not token or not chat_id:
            return False, "Не указан токен или Chat ID"
        if not db_path.exists():
            return False, f"Файл базы данных не найден: {db_path}"

        url = f"https://api.telegram.org/bot{token}/sendDocument"
        timestamp = time.strftime("%d.%m.%Y %H:%M:%S")
        doc_name = "pro_database.json"

        try:
            with open(db_path, "rb") as f:
                response = requests.post(
                    url,
                    data={
                        "chat_id": chat_id,
                        "caption": f"🔄 <b>Автосинхронизация FinanceFugue</b>\n📅 {timestamp}\n#FINANCE_FUGUE_SYNC",
                        "parse_mode": "HTML"
                    },
                    files={"document": (doc_name, f)},
                    timeout=30
                )
            if response.status_code == 200:
                return True, "База успешно отправлена в Telegram-бота!"
            else:
                return False, f"Telegram API Error ({response.status_code}): {response.text}"
        except Exception as e:
            return False, f"Ошибка отправки в Telegram: {e}"

    @staticmethod
    def pull_latest_database(target_db_path: Path, token: str, chat_id: str) -> Tuple[bool, str]:
        """
        Получает последнюю версию базы данных из чата пользователя с ботом.
        """
        token = token.strip() or DEFAULT_TELEGRAM_BOT_TOKEN
        chat_id = chat_id.strip()
        if not token or not chat_id:
            return False, "Не указан токен или Chat ID"

        try:
            # Запрашиваем последние обновления
            resp = requests.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={"limit": 50, "allowed_updates": ["message"]},
                timeout=15
            )
            if resp.status_code != 200:
                return False, f"Ошибка получения данных от Telegram API: {resp.text}"

            updates = resp.json().get("result", [])
            latest_doc = None
            latest_time = 0

            # Ищем самый свежий pro_database.json или .json документ для данного chat_id
            for u in reversed(updates):
                msg = u.get("message") or u.get("channel_post")
                if not msg:
                    continue
                sender_id = str(msg.get("chat", {}).get("id", ""))
                if sender_id != chat_id:
                    continue

                doc = msg.get("document")
                if doc:
                    fname = (doc.get("file_name") or "").lower()
                    if fname.endswith(".json") or fname.endswith(".db"):
                        latest_doc = doc
                        latest_time = msg.get("date", 0)
                        break

            if not latest_doc:
                return False, "В чате с ботом пока нет файлов базы данных. Отправьте /sync в боте или нажмите 'Выгрузить базу в программу'."

            # Скачиваем файл
            file_id = latest_doc.get("file_id")
            f_resp = requests.get(f"https://api.telegram.org/bot{token}/getFile", params={"file_id": file_id}, timeout=10)
            if f_resp.status_code != 200:
                return False, f"Не удалось получить ссылку на файл: {f_resp.text}"

            file_path_tg = f_resp.json().get("result", {}).get("file_path")
            download_url = f"https://api.telegram.org/file/bot{token}/{file_path_tg}"

            down_resp = requests.get(download_url, timeout=30)
            if down_resp.status_code != 200:
                return False, f"Ошибка скачивания файла базы: {down_resp.status_code}"

            content_bytes = down_resp.content

            # Валидируем JSON
            try:
                data = json.loads(content_bytes.decode("utf-8"))
                if not isinstance(data, (dict, list)):
                    return False, "Полученный файл не содержит валидных данных CRM"
            except Exception as e:
                return False, f"Полученный файл поврежден: {e}"

            # Создаем резервную копию перед заменой
            if target_db_path.exists():
                backup_path = target_db_path.with_suffix(f".backup_{int(time.time())}.json")
                shutil.copy2(target_db_path, backup_path)

            # Сохраняем новую базу
            with open(target_db_path, "wb") as f:
                f.write(content_bytes)

            return True, f"База данных успешно загружена из бота! (Обновлена {time.strftime('%d.%m.%Y %H:%M', time.localtime(latest_time))})"

        except Exception as e:
            return False, f"Ошибка получения базы из бота: {e}"


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

            if self.action == "pull_telegram":
                token = self.settings.get("telegram_token", DEFAULT_TELEGRAM_BOT_TOKEN).strip()
                chat_id = self.settings.get("telegram_chat_id", "").strip()
                success, msg = TelegramBotSync.pull_latest_database(self.db_path, token, chat_id)
                self.finished_sync.emit(success, msg)
                return

            if not self.db_path.exists():
                self.finished_sync.emit(False, "База данных не найдена")
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
        return TelegramBotSync.push_database(self.db_path, token, chat_id)

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
