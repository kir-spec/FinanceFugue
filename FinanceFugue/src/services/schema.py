"""Версия схемы файла базы данных и миграционные утилиты.

Текущая версия схемы: ``SCHEMA_VERSION = 1``.

При добавлении нового поля в ``Order`` или ``Client``:
1. Добавьте поле в ``ORDER_DEFAULTS`` / ``CLIENT_DEFAULTS`` с разумным дефолтом.
2. Функции ``migrate_order`` / ``migrate_client`` автоматически заполнят его
   для старых записей при загрузке — без смены версии схемы и без миграций.
3. Если изменение **ломающее** (смена типа, удаление поля), увеличьте
   ``SCHEMA_VERSION`` и добавьте явную ветку в ``_extract_clients_payload``.
"""
from __future__ import annotations

SCHEMA_VERSION: int = 1
"""Версия формата JSON-файла базы данных."""

# ---------------------------------------------------------------------------
# Значения по умолчанию для полей модели Order (все — опциональные).
# При добавлении нового поля в Order — добавьте его сюда же.
# ---------------------------------------------------------------------------
ORDER_DEFAULTS: dict = {
    "service_type": "",
    "price": 0.0,
    "currency": "RUB",
    "advance": 0.0,
    "created_at": "",
    "deadline": "",
    "status": "В работе",
    "is_deleted": False,
    "files": [],
    "payments": [],
    "notes": "",         # поле зарезервировано для будущего использования
}

# ---------------------------------------------------------------------------
# Значения по умолчанию для полей модели Client.
# ---------------------------------------------------------------------------
CLIENT_DEFAULTS: dict = {
    "email": "",
    "social_link": "",
    "avatar_path": "",
    "is_deleted": False,
    "notes": "",
    "requisites": "",
    "orders": [],
}


def migrate_order(raw: dict) -> dict:
    """Заполняет отсутствующие поля заказа значениями по умолчанию.

    Не изменяет существующие поля. Безопасно вызывать на любом dict из JSON.

    Args:
        raw: Сырой словарь заказа из JSON.

    Returns:
        Тот же dict с заполненными отсутствующими полями.
    """
    for field, default in ORDER_DEFAULTS.items():
        if field not in raw:
            raw[field] = default
    return raw


def migrate_client(raw: dict) -> dict:
    """Заполняет отсутствующие поля клиента значениями по умолчанию.

    Args:
        raw: Сырой словарь клиента из JSON.

    Returns:
        Тот же dict с заполненными отсутствующими полями.
    """
    for field, default in CLIENT_DEFAULTS.items():
        if field not in raw:
            raw[field] = default
    return raw
