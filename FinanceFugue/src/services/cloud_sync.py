import json
import shutil
import time
from typing import Dict, Any, Tuple
from pathlib import Path

import requests
from PySide6.QtCore import QThread, Signal
from webdav3.client import Client as WebDavClient

from ..logger import get_logger

logger = get_logger("CloudSync")

class CloudSyncWorker(QThread):
    """
    Фоновый воркер для синхронизации файла базы данных с облаком.
    """
    # Сигналы: (success, status_message)
    finished_sync = Signal(bool, str)

    def __init__(self, db_path: str, sync_settings: Dict[str, Any]):
        super().__init__()
        self.db_path = Path(db_path)
        self.settings = sync_settings

    def run(self):
        try:
            if not self.db_path.exists():
                self.finished_sync.emit(False, "База данных не найдена")
                return

            provider = self.settings.get("provider", "none")
            if provider == "none":
                self.finished_sync.emit(False, "Провайдер не выбран")
                return

            # Вызываем нужный метод
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
        token = self.settings.get("telegram_token", "").strip()
        chat_id = self.settings.get("telegram_chat_id", "").strip()
        
        if not token or not chat_id:
            return False, "Не указан токен или Chat ID"

        url = f"https://api.telegram.org/bot{token}/sendDocument"
        
        # Добавим таймстемп в имя файла, чтобы в телеграме они не перезаписывались
        # (в телеграме они и так не перезаписываются, но для красоты)
        timestamp = time.strftime("%Y%m%d_%H%M")
        doc_name = f"FinanceFugue_Backup_{timestamp}.json"
        
        try:
            with open(self.db_path, "rb") as f:
                response = requests.post(
                    url, 
                    data={"chat_id": chat_id, "caption": f"Бэкап базы данных CRM: {timestamp}"},
                    files={"document": (doc_name, f)}
                )
            if response.status_code == 200:
                return True, "Отправлено в Telegram"
            else:
                return False, f"Telegram API Error: {response.text}"
        except Exception as e:
            return False, str(e)

    def _sync_yandex(self) -> Tuple[bool, str]:
        token = self.settings.get("yandex_token", "").strip()
        if not token:
            return False, "Не указан OAuth токен Яндекс.Диска"

        headers = {"Authorization": f"OAuth {token}"}
        
        try:
            # 1. Запрашиваем URL для загрузки
            upload_url_req = requests.get(
                "https://cloud-api.yandex.net/v1/disk/resources/upload",
                params={"path": "app:/pro_database.json", "overwrite": "true"},
                headers=headers
            )
            
            if upload_url_req.status_code not in (200, 201):
                # Возможно, папка app: не инициализирована или токен кривой (например, не для папки приложения)
                # Попробуем загрузить в корень
                upload_url_req = requests.get(
                    "https://cloud-api.yandex.net/v1/disk/resources/upload",
                    params={"path": "/FinanceFugue_Backup.json", "overwrite": "true"},
                    headers=headers
                )
                
                if upload_url_req.status_code not in (200, 201):
                    return False, f"Yandex API Error (Get URL): {upload_url_req.text}"
            
            upload_url = upload_url_req.json().get("href")
            
            # 2. Загружаем файл
            with open(self.db_path, "rb") as f:
                upload_req = requests.put(upload_url, files={"file": f})
                
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
                response = requests.post(url, headers=headers, data=f)
                
            if response.status_code == 200:
                return True, "Загружено в Dropbox"
            else:
                return False, f"Dropbox API Error: {response.text}"
        except Exception as e:
            return False, str(e)

    def _sync_webdav(self) -> Tuple[bool, str]:
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
