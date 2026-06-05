import logging
import os
from datetime import datetime

# Создаем папку для логов, если её нет
LOGS_DIR = "logs"
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

# Имя файла лога с текущей датой
log_filename = os.path.join(LOGS_DIR, f"crm_{datetime.now().strftime('%Y-%m-%d')}.log")

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def get_logger(name):
    return logging.getLogger(name)
