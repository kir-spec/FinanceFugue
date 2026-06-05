import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

LOGS_DIR = "logs"
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

log_filename = os.path.join(LOGS_DIR, f"crm_{datetime.now().strftime('%Y-%m-%d')}.log")

_level = logging.DEBUG if os.environ.get("FINANCEFUGUE_DEBUG") else logging.INFO

_file_handler = RotatingFileHandler(
    log_filename,
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


def get_logger(name):
    return logging.getLogger(name)
