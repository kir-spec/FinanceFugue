"""Сборка и разбор CRM-пакета для синхронизации ПК ⇄ бот (включая pro_archive.json)."""
from __future__ import annotations

import copy
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ..models import Client, Order
from ..storage import CRMStorage, _parse_clients_list
from .order_status import normalize_order_status, reconcile_crm_envelope, reconcile_order_dict
from .schema import SCHEMA_VERSION

PERSONAL_FINANCE_FILENAME = "personal_finance.json"


def merge_active_and_archive(
    active_clients: List[Client], archive_clients: List[Client]
) -> List[Client]:
    """Объединяет активную базу и pro_archive для отправки в бота."""
    result: List[Client] = [copy.deepcopy(c) for c in active_clients]
    by_id = {c.id: c for c in result}

    for arch_client in archive_clients:
        if arch_client.id in by_id:
            target = by_id[arch_client.id]
            existing_ids = {o.id for o in target.orders}
            for order in arch_client.orders:
                if order.id in existing_ids:
                    for o in target.orders:
                        if o.id == order.id:
                            o.is_archived = True
                            break
                    continue
                o_copy = copy.deepcopy(order)
                o_copy.is_archived = True
                target.orders.append(o_copy)
        else:
            nc = copy.deepcopy(arch_client)
            for o in nc.orders:
                o.is_archived = True
            result.append(nc)
    return result


def split_active_and_archive(clients: List[Client]) -> Tuple[List[Client], List[Client]]:
    """Разносит заказы по pro_database и pro_archive после pull с бота."""
    active_clients: List[Client] = []
    archive_by_id: Dict[str, Client] = {}

    for client in clients:
        ac = copy.deepcopy(client)
        ac_active: List[Order] = []
        ac_arch: List[Order] = []
        for order in ac.orders:
            if getattr(order, "is_archived", False):
                ac_arch.append(copy.deepcopy(order))
            else:
                ac_active.append(copy.deepcopy(order))
        ac.orders = ac_active
        active_clients.append(ac)

        if ac_arch:
            if client.id in archive_by_id:
                archive_by_id[client.id].orders.extend(ac_arch)
            else:
                arc = copy.deepcopy(client)
                arc.orders = ac_arch
                archive_by_id[client.id] = arc

    return active_clients, list(archive_by_id.values())


def load_clients_for_sync(db_path: Path | str, password: str = "") -> List[Client]:
    path = Path(db_path)
    active_store = CRMStorage(path)
    active_store.password = password
    active = active_store.load()
    
    arch_path = path.parent / "pro_archive.json"
    archive_store = CRMStorage(arch_path)
    archive_store.password = password
    archive = archive_store.load() if arch_path.exists() else []
    
    return merge_active_and_archive(active, archive)


def _clients_to_envelope_dict(clients: List[Client]) -> Dict[str, Any]:
    clients_data = []
    for c in clients:
        orders_data = []
        for order in c.orders:
            orders_data.append(
                reconcile_order_dict(
                    {
                        "id": order.id,
                        "service_type": order.service_type,
                        "price": order.price,
                        "currency": order.currency,
                        "advance": order.advance,
                        "created_at": order.created_at,
                        "deadline": order.deadline,
                        "status": normalize_order_status(order.status),
                        "is_deleted": order.is_deleted,
                        "is_archived": order.is_archived,
                        "files": [asdict(f) for f in order.files],
                        "payments": [p.to_dict() for p in order.payments],
                    }
                )
            )
        clients_data.append(
            {
                "id": c.id,
                "name": c.name,
                "email": c.email,
                "social_link": c.social_link,
                "avatar_path": c.avatar_path,
                "is_deleted": c.is_deleted,
                "is_archived": c.is_archived,
                "notes": c.notes,
                "requisites": c.requisites,
                "orders": orders_data,
            }
        )
    return reconcile_crm_envelope({"schema_version": SCHEMA_VERSION, "clients": clients_data})


def personal_finance_path(db_path: Path | str) -> Path:
    return Path(db_path).parent / PERSONAL_FINANCE_FILENAME


def load_personal_finance_sidecar(db_path: Path | str) -> Dict[str, Any]:
    path = personal_finance_path(db_path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_personal_finance_sidecar(db_path: Path | str, data: Dict[str, Any]) -> None:
    if not data:
        return
    path = personal_finance_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def persist_clients_after_pull(db_path: Path | str, merged_envelope: Dict[str, Any], password: str = "") -> None:
    path = Path(db_path)
    clients_raw = merged_envelope.get("clients") or []
    clients = _parse_clients_list(clients_raw)
    active, archive = split_active_and_archive(clients)
    
    # Чтобы сохранение двух файлов было транзакционным,
    # мы сначала сохраним их во временные пути, а затем переименуем.
    active_tmp = path.with_suffix(".tmp.active")
    archive_tmp = path.parent / "pro_archive.tmp.archive"
    arch_path = path.parent / "pro_archive.json"
    
    # Инициализируем хранилища с временными путями (но передаем пароль если есть)
    active_store = CRMStorage(active_tmp)
    active_store.password = password
    archive_store = CRMStorage(archive_tmp)
    archive_store.password = password
    
    # Пишем во временные файлы (внутри save() они тоже пишутся в .tmp.tmp и атомарно переименовываются в наш .tmp)
    active_store.save(active)
    archive_store.save(archive)
    
    import os
    # Атомарно переносим на боевые пути
    os.replace(active_tmp, path)
    os.replace(archive_tmp, arch_path)
    
    pf = merged_envelope.get("personal_finance")
    if isinstance(pf, dict) and pf:
        save_personal_finance_sidecar(path, pf)

def build_sync_envelope(db_path: Path | str, password: str = "") -> Dict[str, Any]:
    path = Path(db_path)
    clients = load_clients_for_sync(path, password=password)
    envelope = _clients_to_envelope_dict(clients)
    pf = load_personal_finance_sidecar(path)
    if pf:
        envelope["personal_finance"] = pf
    return envelope


def build_sync_bytes(db_path: Path | str, password: str = "") -> bytes:
    return json.dumps(build_sync_envelope(db_path, password=password), ensure_ascii=False, indent=2).encode("utf-8")
