"""Блокировка единственного экземпляра приложения на файл базы."""
import errno
import os
import sys
from pathlib import Path


class InstanceLockError(Exception):
    pass


def _pid_alive(pid: int) -> bool:
    """True, если процесс с таким PID существует (кросс-платформенно)."""
    if pid <= 0:
        return False
    try:
        if sys.platform == "win32":
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle == 0:
                return False
            try:
                code = ctypes.c_ulong()
                if kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                    return code.value == STILL_ACTIVE
                return False
            finally:
                kernel32.CloseHandle(handle)
        else:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return False
            except PermissionError:
                return True
            except OSError:
                return False
            return True
    except (OSError, ImportError):
        return False


def _read_pid(lock_path: Path) -> int | None:
    """Читает PID из lock-файла. None при любой ошибке."""
    if not lock_path.exists():
        return None
    try:
        with open(lock_path, "rb") as f:
            data = f.read().strip()
        return int(data) if data else None
    except (OSError, ValueError):
        return None


def _clear_lock(lock_path: Path) -> None:
    """Удаляет lock-файл, если возможно (missing_ok=True)."""
    try:
        lock_path.unlink(missing_ok=True)
    except OSError:
        pass


class InstanceLock:
    def __init__(self, lock_path: Path):
        self._path = lock_path
        self._file = None

    def acquire(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

        # Stale lock: если в файле лежит PID несуществующего процесса —
        # безопасно удаляем и пробуем снова.
        for _attempt in range(2):
            self._file = open(self._path, "a+b")
            try:
                if sys.platform == "win32":
                    import msvcrt
                    self._file.seek(0)
                    try:
                        msvcrt.locking(self._file.fileno(), msvcrt.LK_NBLCK, 1)
                    except OSError as e:
                        # OSError(EACCES) — файл залочен другим процессом.
                        # OSError(EBADF) — невалидный FD.
                        if getattr(e, "errno", None) in (errno.EACCES, errno.EAGAIN):
                            self._maybe_break_stale_lock()
                            self._file.close()
                            self._file = None
                            continue
                        raise
                else:
                    import fcntl
                    try:
                        fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except OSError as e:
                        if e.errno in (errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK):
                            self._maybe_break_stale_lock()
                            self._file.close()
                            self._file = None
                            continue
                        raise
                break
            except BaseException:
                # Если уже открыли файл — закрываем.
                try:
                    self._file.close()
                except OSError:
                    pass
                self._file = None
                raise

        if self._file is None:
            raise InstanceLockError(
                "Другой экземпляр FinanceFugue уже использует эту базу данных."
            )

        try:
            self._file.seek(0)
            self._file.truncate()
            self._file.write(str(os.getpid()).encode())
            self._file.flush()
        except OSError as e:
            try:
                self._file.close()
            except OSError:
                pass
            self._file = None
            raise InstanceLockError(
                "Не удалось записать PID в lock-файл."
            ) from e

    def _maybe_break_stale_lock(self) -> None:
        """Если lock-файл содержит PID несуществующего процесса — удаляем."""
        pid = _read_pid(self._path)
        if pid and not _pid_alive(pid):
            try:
                self._path.unlink(missing_ok=True)
            except OSError:
                pass

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
        finally:
            try:
                self._file.close()
            except OSError:
                pass
            self._file = None
        _clear_lock(self._path)
