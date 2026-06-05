import json
import logging
import os
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, List

from .models import Client, Order, Payment, ProjectFile
from .services.schema import SCHEMA_VERSION

logger = logging.getLogger("Storage")


class DatabaseLoadError(Exception):
    """База данных существует, но не может быть прочитана."""


def _parse_clients_list(data: list) -> List[Client]:
    clients = []
    for c_dict in data:
        if not isinstance(c_dict, dict):
            raise ValueError("Элемент клиента должен быть объектом")
        if not c_dict.get("id"):
            raise ValueError("У клиента отсутствует обязательное поле id")
        if not c_dict.get("name"):
            raise ValueError("У клиента отсутствует обязательное поле name")

        orders = []
        for o in c_dict.get("orders", []):
            if not isinstance(o, dict):
                raise ValueError("Элемент заказа должен быть объектом")
            if not o.get("id"):
                raise ValueError("У заказа отсутствует обязательное поле id")

            files = [ProjectFile(**fi) for fi in o.get("files", [])]
            payments = []
            for p in o.get("payments", []):
                payments.append(
                    Payment(
                        id=p.get("id", str(uuid.uuid4())),
                        type=p.get("type", "платеж"),
                        amount=p.get("amount", 0.0),
                        date=p.get("date", ""),
                        note=p.get("note", ""),
                    )
                )
            orders.append(
                Order(
                    id=o["id"],
                    service_type=o.get("service_type", ""),
                    price=o.get("price", 0.0),
                    currency=o.get("currency", "RUB"),
                    advance=o.get("advance", 0.0),
                    created_at=o.get("created_at", ""),
                    deadline=o.get("deadline", ""),
                    status=o.get("status", "В работе"),
                    files=files,
                    payments=payments,
                )
            )

        clients.append(
            Client(
                id=c_dict["id"],
                name=c_dict["name"],
                email=c_dict.get("email", ""),
                social_link=c_dict.get("social_link", ""),
                notes=c_dict.get("notes", ""),
                orders=orders,
            )
        )
    return clients


def _extract_clients_payload(data: Any) -> list:
    """Поддержка legacy (массив) и нового формата {schema_version, clients}."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "clients" in data:
        version = data.get("schema_version", 1)
        if version > SCHEMA_VERSION:
            raise ValueError(
                f"Версия схемы {version} новее поддерживаемой ({SCHEMA_VERSION})"
            )
        clients = data["clients"]
        if not isinstance(clients, list):
            raise ValueError("Поле clients должно быть массивом")
        return clients
    raise ValueError("Неверный формат файла базы данных")


class CRMStorage:
    def __init__(self, filename="pro_database.json"):
        self.path = Path(filename)

    def load(self) -> List[Client]:
        if not self.path.exists():
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            payload = _extract_clients_payload(data)
            return _parse_clients_list(payload)
        except Exception as e:
            logger.error("Ошибка загрузки базы данных %s: %s", self.path, e, exc_info=True)
            raise DatabaseLoadError(str(e)) from e

    def save(self, clients: List[Client]):
        temp_path = self.path.with_suffix(".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            clients_data = []
            for c in clients:
                c_dict = asdict(c)
                orders_data = []
                for order in c.orders:
                    order_dict = {
                        "id": order.id,
                        "service_type": order.service_type,
                        "price": order.price,
                        "currency": order.currency,
                        "advance": order.advance,
                        "created_at": order.created_at,
                        "deadline": order.deadline,
                        "status": order.status,
                        "files": [asdict(f) for f in order.files],
                        "payments": [p.to_dict() for p in order.payments],
                    }
                    orders_data.append(order_dict)
                c_dict["orders"] = orders_data
                clients_data.append(c_dict)

            envelope = {"schema_version": SCHEMA_VERSION, "clients": clients_data}
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(envelope, f, ensure_ascii=False, indent=4)

            os.replace(temp_path, self.path)
        except Exception as e:
            logger.error("Ошибка сохранения базы данных %s: %s", self.path, e, exc_info=True)
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            raise
