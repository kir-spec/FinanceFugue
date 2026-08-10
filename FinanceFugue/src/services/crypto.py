import base64
import os
import json
import zlib
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet, InvalidToken

class InvalidPasswordError(Exception):
    pass

class DatabaseCrypto:
    SALT_SIZE = 16

    @staticmethod
    def _derive_key(password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    @staticmethod
    def encrypt_data(data: dict, password: str) -> bytes:
        """Сжимает и шифрует данные (JSON dict) в бинарный формат."""
        # 1. Сериализуем и сжимаем
        json_bytes = json.dumps(data, ensure_ascii=False).encode('utf-8')
        compressed_bytes = zlib.compress(json_bytes)

        # 2. Шифруем
        salt = os.urandom(DatabaseCrypto.SALT_SIZE)
        key = DatabaseCrypto._derive_key(password, salt)
        f = Fernet(key)
        encrypted_bytes = f.encrypt(compressed_bytes)

        # 3. Возвращаем соль + шифротекст
        return salt + encrypted_bytes

    @staticmethod
    def decrypt_data(file_bytes: bytes, password: str) -> dict:
        """Расшифровывает и распаковывает данные обратно в dict."""
        if len(file_bytes) <= DatabaseCrypto.SALT_SIZE:
            raise ValueError("Файл поврежден или слишком мал")

        salt = file_bytes[:DatabaseCrypto.SALT_SIZE]
        encrypted_bytes = file_bytes[DatabaseCrypto.SALT_SIZE:]

        key = DatabaseCrypto._derive_key(password, salt)
        f = Fernet(key)

        try:
            compressed_bytes = f.decrypt(encrypted_bytes)
        except InvalidToken:
            raise InvalidPasswordError("Неверный пароль или файл поврежден")

        # Распаковка
        json_bytes = zlib.decompress(compressed_bytes)
        return json.loads(json_bytes.decode('utf-8'))
