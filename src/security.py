import os
import base64
import hashlib
import json
from enum import Enum
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class SecurityMode(Enum):
    UNENCRYPTED = "unencrypted"
    ENCRYPTED = "encrypted"

class SecurityManager:
    def __init__(self, settings_path="crm_settings.json"):
        self.settings_path = Path(settings_path)
        self.key = None
        self.cipher_suite = None
        self.mode = SecurityMode.UNENCRYPTED
        self._load_security_config()

    def _load_security_config(self):
        """Загрузка конфигурации безопасности из настроек"""
        self.app_salt = None
        self.app_hash = None
        if self.settings_path.exists():
            try:
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    mode_str = settings.get("security_mode", "unencrypted")
                    self.mode = SecurityMode(mode_str)
                    self.salt = base64.b64decode(settings.get("security_salt", "")) if "security_salt" in settings else None
                    self.password_hash = settings.get("password_hash", None)
                    
                    self.app_salt = base64.b64decode(settings.get("app_salt", "")) if "app_salt" in settings else None
                    self.app_hash = settings.get("app_hash", None)
            except Exception as e:
                print(f"Error loading security config: {e}")
                self.mode = SecurityMode.UNENCRYPTED

    def is_encrypted(self):
        return self.mode == SecurityMode.ENCRYPTED

    def is_configured(self):
        """Проверка, была ли произведена первоначальная настройка безопасности"""
        if self.settings_path.exists():
            try:
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    return "security_mode" in settings
            except:
                return False
        return False

    def setup_encryption(self, db_password: str = None):
        """Включение шифрования. Если пароль не передан, используется внутренний ключ без хеширования пароля."""
        key = Fernet.generate_key()
        with open("crm.key", "wb") as f:
            f.write(key)
            
        if db_password:
            salt = os.urandom(16)
            password_hash = hashlib.sha256(db_password.encode() + salt).hexdigest()
            self.salt = salt
            self.password_hash = password_hash
        else:
            self.salt = None
            self.password_hash = None

        self.key = key
        self.cipher_suite = Fernet(key)
        self.mode = SecurityMode.ENCRYPTED

        self._save_security_config()
        return True
    
    def auto_unlock(self):
        if self.mode == SecurityMode.ENCRYPTED:
            if os.path.exists("crm.key"):
                with open("crm.key", "rb") as f:
                    self.key = f.read()
                self.cipher_suite = Fernet(self.key)
                return True
            return False
        return True

    def setup_no_encryption(self):
        """Отключение шифрования"""
        self.mode = SecurityMode.UNENCRYPTED
        self.key = None
        self.cipher_suite = None
        self.salt = None
        self.password_hash = None
        if os.path.exists("crm.key"):
            os.remove("crm.key")
        self._save_security_config()

    def set_app_password(self, password: str):
        salt = os.urandom(16)
        ph = hashlib.sha256(password.encode() + salt).hexdigest()
        self.app_salt = salt
        self.app_hash = ph
        self._save_security_config()

    def remove_app_password(self):
        self.app_salt = None
        self.app_hash = None
        self._save_security_config()

    def has_app_password(self):
        return self.app_hash is not None

    def check_app_password(self, password: str) -> bool:
        if not self.app_salt or not self.app_hash:
            return True
        verify = hashlib.sha256(password.encode() + self.app_salt).hexdigest()
        return verify == self.app_hash
    
    def check_db_password(self, password: str) -> bool:
        if not self.salt or not self.password_hash:
            return True
        verify = hashlib.sha256(password.encode() + self.salt).hexdigest()
        return verify == self.password_hash

    def unlock(self, password: str) -> bool:
        if self.has_app_password():
            if not self.check_app_password(password):
                return False
        
        if self.is_encrypted():
             # Если установлен хэш пароля БД, проверяем его
             if self.password_hash:
                 if not password or not self.check_db_password(password):
                     return False
             
             # Загружаем ключ шифрования
             if os.path.exists("crm.key"):
                 try:
                     with open("crm.key", "rb") as f:
                         self.key = f.read()
                     self.cipher_suite = Fernet(self.key)
                 except:
                     return False
             else:
                 # Если файла ключа нет, но режим ENCRYPTED - это ошибка
                 return False
        return True

    def change_password(self, old_password: str, new_password: str):
        """Смена пароля (требует перешифровки БД, здесь только смена ключа в памяти/конфиге)"""
        # Примечание: Полная смена пароля требует перешифровки всех данных в БД.
        # Это сложная операция. Для упрощения пока реализуем только смену доступа.
        # Но если ключ зависит от пароля, то данные станут недоступны.
        # Решение: Генерировать мастер-ключ, шифровать его ключом пользователя.
        # Пока реализуем простую схему: смена пароля = перешифровка данных (будет реализовано в Backend).
        pass 

    def encrypt(self, data: str) -> str:
        """Шифрование строки"""
        if self.mode == SecurityMode.UNENCRYPTED or not self.cipher_suite:
            return data
        if not data:
            return ""
        try:
            # Добавляем префикс, чтобы отличать зашифрованные данные
            encrypted_bytes = self.cipher_suite.encrypt(data.encode())
            return "ENC:" + base64.urlsafe_b64encode(encrypted_bytes).decode()
        except Exception as e:
            print(f"Encryption error: {e}")
            return data

    def decrypt(self, data: str) -> str:
        """Дешифрование строки"""
        if self.mode == SecurityMode.UNENCRYPTED or not self.cipher_suite:
            return data
        if not data or not data.startswith("ENC:"):
            return data
        try:
            encrypted_bytes = base64.urlsafe_b64decode(data[4:])
            return self.cipher_suite.decrypt(encrypted_bytes).decode()
        except Exception as e:
            # print(f"Decryption error: {e}") # Может спамить если неверный ключ
            return "[ENCRYPTED]"

    def _save_security_config(self):
        settings = {}
        if self.settings_path.exists():
            try:
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
            except:
                pass
        
        settings["security_mode"] = self.mode.value
        if self.salt:
            settings["security_salt"] = base64.b64encode(self.salt).decode()
        if self.password_hash:
            settings["password_hash"] = self.password_hash
            
        if self.app_salt:
            settings["app_salt"] = base64.b64encode(self.app_salt).decode()
        if self.app_hash:
            settings["app_hash"] = self.app_hash
        
        with open(self.settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
