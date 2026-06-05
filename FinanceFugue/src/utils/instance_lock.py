"""Блокировка единственного экземпляра приложения на файл базы."""
import os
import sys
from pathlib import Path


class InstanceLockError(Exception):
    pass


class InstanceLock:
    def __init__(self, lock_path: Path):
        self._path = lock_path
        self._file = None

    def acquire(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self._path, "a+b")
        try:
            if sys.platform == "win32":
                import msvcrt
                self._file.seek(0)
                msvcrt.locking(self._file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError) as e:
            self._file.close()
            self._file = None
            raise InstanceLockError(
                "Другой экземпляр FinanceFugue уже использует эту базу данных."
            ) from e
        self._file.seek(0)
        self._file.truncate()
        self._file.write(str(os.getpid()).encode())
        self._file.flush()

    def release(self) -> None:
        if not self._file:
            return
        try:
            if sys.platform == "win32":
                import msvcrt
                self._file.seek(0)
                msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        self._file.close()
        self._file = None
        try:
            self._path.unlink(missing_ok=True)
        except OSError:
            pass
