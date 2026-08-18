import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

from .utils.paths import user_data_path

LOGS_DIR = user_data_path() / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

_level = logging.DEBUG if os.environ.get("FINANCEFUGUE_DEBUG") else logging.INFO

# Защита от FD-утечки: basicConfig добавляет новые хэндлеры при каждом
# импорте модуля (актуально для тестов, где модуль переимпортируется).
# Инициализируем лишь один раз за жизнь процесса.
if not logging.root.handlers:
    _file_handler = RotatingFileHandler(
        str(LOGS_DIR / f"crm_{datetime.now().strftime('%Y-%m-%d')}.log"),
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    _stream_handler = logging.StreamHandler()
    logging.basicConfig(
        level=_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[_file_handler, _stream_handler],
    )
else:
    # Корневой логгер уже настроен (тест/повторный импорт) —
    # только выставляем уровень, не трогаем хэндлеры.
    logging.root.setLevel(_level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
