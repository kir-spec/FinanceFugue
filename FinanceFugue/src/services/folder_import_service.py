"""Сканирование папок и применение результатов импорта к списку клиентов."""
import os
import uuid
from datetime import datetime
from typing import List, Tuple

from ..models import Client, Order, ProjectFile

ScanResult = dict


def scan_client_folder(folder_path: str, client_name: str) -> List[ScanResult]:
    """Сканирует одну папку клиента: подпапки = заказы, файлы в корне = один заказ."""
    results: List[ScanResult] = []
    try:
        entries = os.listdir(folder_path)
    except OSError:
        return results

    order_folders = [
        os.path.join(folder_path, name)
        for name in entries
        if os.path.isdir(os.path.join(folder_path, name))
    ]

    if order_folders:
        for order_path in order_folders:
            order_name = os.path.basename(order_path)
            order_content = []
            try:
                for item in os.listdir(order_path):
                    order_content.append((item, os.path.join(order_path, item)))
            except OSError:
                continue
            if order_content:
                results.append({
                    "client_name": client_name,
                    "order_name": order_name,
                    "files": order_content,
                })
    else:
        files = [
            (name, os.path.join(folder_path, name))
            for name in entries
            if os.path.isfile(os.path.join(folder_path, name))
        ]
        if files:
            results.append({
                "client_name": client_name,
                "order_name": client_name,
                "files": files,
            })
    return results


def apply_folder_scan_results(
    clients: List[Client],
    scan_results: List[ScanResult],
) -> Tuple[int, int]:
    """Добавляет клиентов/заказы/файлы из результатов сканирования. Возвращает (новые клиенты, новые заказы)."""
    imported_count = 0
    order_count = 0

    for result in scan_results:
        client_name = result["client_name"]
        order_name = result["order_name"]
        files = result["files"]

        client = next((c for c in clients if c.name.lower() == client_name.lower()), None)
        if not client:
            client = Client(id=str(uuid.uuid4()), name=client_name)
            clients.append(client)
            imported_count += 1

        target_order = next((o for o in client.orders if o.service_type == order_name), None)
        if not target_order:
            order_date = datetime.now()
            if files:
                try:
                    order_date = datetime.fromtimestamp(os.path.getmtime(files[0][1]))
                except OSError:
                    pass
            target_order = Order(
                id=str(uuid.uuid4()),
                service_type=order_name,
                price=0.0,
                advance=0.0,
                created_at=order_date.strftime("%d.%m.%Y %H:%M"),
                deadline=order_date.strftime("%d.%m.%Y"),
                status="В работе",
                files=[],
                payments=[],
            )
            client.orders.append(target_order)
            order_count += 1

        for file_name, file_path in files:
            if not any(f.path == file_path for f in target_order.files):
                is_dir = os.path.isdir(file_path)
                target_order.files.append(
                    ProjectFile(
                        path=file_path,
                        name=file_name,
                        is_finished=False,
                        is_folder=is_dir,
                    )
                )

    return imported_count, order_count
