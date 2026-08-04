"""End-to-end smoke-test FinanceFugue без UI.

Запускает три сценария:
  1. Пустая база → создание клиента, заказа, платежа, файла.
  2. Средняя база (~100 клиентов, ~10 заказов у каждого, ~5 платежей).
  3. Большая база (~10 000 клиентов, ~5 заказов, ~3 платежа).

Каждый сценарий:
  - Создаёт storage в TempDirectory.
  - Выполняет все основные операции.
  - Сериализует/десериализует БД.
  - Проверяет round-trip инвариантов.

Запуск:
    python scripts/smoke_test.py
"""
from __future__ import annotations

import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import List

sys.path.insert(0, ".")

from src.models import Client, Order, Payment, ProjectFile
from src.services.client_deletion import delete_client_files_from_disk
from src.services.client_stats import calculate_global_dashboard
from src.services.currency import sum_by_currency
from src.services.deadline_notifier import collect_deadline_alerts
from src.services.folder_import_service import (
    apply_folder_scan_results,
    scan_client_folder,
)
from src.storage import CRMStorage
from src.utils.path_safety import (
    is_path_within,
    safe_filename_candidate,
)


def _make_payment(amount: float, ptype: str = "платеж", note: str = "") -> Payment:
    return Payment(
        id=str(uuid.uuid4()),
        type=ptype,
        amount=amount,
        date="01.01.2026",
        note=note,
    )


def _build_client(
    name: str,
    num_orders: int = 1,
    payments_per_order: int = 1,
    *,
    price: float = 1000.0,
    advance: float = 500.0,
) -> Client:
    """Строит клиента с заказами; ``payments_per_order`` <= (price - advance) // 100."""
    orders = []
    for i in range(num_orders):
        order = Order(
            id=str(uuid.uuid4()),
            service_type=f"Заказ #{i + 1}",
            price=price,
            advance=advance,
            currency="RUB",
            files=[],
        )
        order.add_payment(advance, "аванс", "первоначальный аванс")
        for _ in range(payments_per_order):
            order.add_payment(100.0, "платеж", "промежуточный")
        orders.append(order)
    return Client(id=str(uuid.uuid4()), name=name, orders=orders)


def scenario_empty(temp_root: Path) -> dict:
    """Сценарий 1: пустая база."""
    storage = CRMStorage(temp_root / "db_empty.json")
    assert storage.load() == []
    clients = []
    client = _build_client("Тестовый клиент")
    clients.append(client)
    storage.save(clients)
    loaded = storage.load()
    assert len(loaded) == 1
    assert loaded[0].name == "Тестовый клиент"
    assert loaded[0].orders[0].debt == 400.0  # 1000 - 500 - 100
    return {"clients": 1, "orders": len(client.orders), "payments": 2}


def scenario_medium(temp_root: Path) -> dict:
    """Сценарий 2: 100 клиентов."""
    storage = CRMStorage(temp_root / "db_medium.json")
    # 5 платежей по 100 при price=2000, advance=500 → долг=1000 > 0
    clients = [
        _build_client(
            f"Клиент-{i:03d}",
            num_orders=10,
            payments_per_order=5,
            price=2000.0,
            advance=500.0,
        )
        for i in range(100)
    ]  
    storage.save(clients)
    loaded = storage.load()
    # Все total_* кэши корректны после reload
    for c, orig in zip(loaded, clients):
        for o_loaded, o_orig in zip(c.orders, orig.orders):
            assert o_loaded.total_received == o_orig.total_received, (
                f"total_received mismatch for {c.name}"
            )
            assert o_loaded.total_advance_received == o_orig.total_advance_received
    dashboard = calculate_global_dashboard(loaded)
    # Должен содержать RUB строку (currency symbol)
    assert any("₽" in v for _, v, _ in dashboard)
    # sum_by_currency не смешивает
    debt_by = sum_by_currency(
        [o for c in loaded for o in c.orders], field="debt", active_only=True
    )
    assert sum(debt_by.values()) > 0
    print(f"   dashboard rows={len(dashboard)}, currencies={list(debt_by.keys())}", flush=True)
    return {"clients": 100, "orders": 100 * 10, "payments": 100 * 10 * 6}


def scenario_large(temp_root: Path) -> dict:
    """Сценарий 3: ~10k клиентов — тест perf и atomic write."""
    storage = CRMStorage(temp_root / "db_large.json")

    t0 = time.perf_counter()
    clients = [
        _build_client(f"Клиент-{i:05d}", num_orders=5, payments_per_order=3)
        for i in range(10_000)
    ]
    t_build = time.perf_counter() - t0

    t1 = time.perf_counter()
    storage.save(clients)
    t_save = time.perf_counter() - t1

    t2 = time.perf_counter()
    loaded = storage.load()
    t_load = time.perf_counter() - t2

    # spot check totals через cache
    sample = loaded[::1000]
    for c in sample:
        for o in c.orders:
            assert o.total_received > 0
            assert o.debt > 0

    size_mb = (temp_root / "db_large.json").stat().st_size / (1024 * 1024)
    return {
        "clients": 10_000,
        "orders": 10_000 * 5,
        "payments": 10_000 * 5 * 4,
        "build_sec": round(t_build, 2),
        "save_sec": round(t_save, 2),
        "load_sec": round(t_load, 2),
        "size_mb": round(size_mb, 1),
    }


def scenario_safety_smoke(temp_root: Path = None) -> dict:
    """Проверка path safety утилит."""
    with tempfile.TemporaryDirectory() as tmp:
        # Создаём две НЕ-связанные папки на одном уровне.
        tmp_a = Path(tmp) / "a"
        tmp_b = Path(tmp) / "b"
        tmp_a.mkdir()
        tmp_b.mkdir()
        root = tmp_a.resolve()
        inner = root / "sub" / "file.txt"
        inner.parent.mkdir(parents=True, exist_ok=True)
        inner.touch()

        assert is_path_within(inner, root), "inner внутри root"
        # tmp_b — НЕ внутри root.
        assert not is_path_within(tmp_b, root), "tmp_b вне root"

        # safe_filename_candidate блокирует path traversal
        assert ".." not in safe_filename_candidate("../../etc/passwd")
        assert "/" not in safe_filename_candidate("a/b")
    return {"is_path_within": "ok", "safe_filename_candidate": "ok"}


def scenario_deletion(temp_root: Path) -> dict:
    """Удаление клиента + безопасная очистка файлов."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve()
        attached = root / "attached_files"
        attached.mkdir()
        order_id = str(uuid.uuid4())
        order_folder = attached / order_id
        order_folder.mkdir()
        f1 = order_folder / "a.txt"
        f1.write_text("data", encoding="utf-8")
        f2 = order_folder / "b.txt"
        f2.write_text("data", encoding="utf-8")

        # Файл ВНЕ attached_files (например, absolute path в другом месте).
        # Создаём его в отдельной песочнице, чтобы он точно был снаружи.
        with tempfile.TemporaryDirectory() as outer_tmp:
            outside = Path(outer_tmp) / "evil.txt"
            outside.write_text("data", encoding="utf-8")

            client = Client(
                id=str(uuid.uuid4()),
                name="Test",
                orders=[
                    Order(
                        id=order_id,
                        service_type="X",
                        files=[
                            ProjectFile(path=str(f1), name="a.txt"),
                            ProjectFile(path=str(f2), name="b.txt"),
                            # Внешний файл — НЕ должен удаляться.
                            ProjectFile(path=str(outside), name="evil.txt"),
                        ],
                    )
                ],
            )
            removed = delete_client_files_from_disk([client], str(root))
            assert removed == 2, f"expected 2 removals, got {removed}"
            assert not f1.exists()
            assert not f2.exists()
            assert outside.exists(), "внешний файл не должен удаляться"
    return {"removed": 2, "outside_kept": True}


def scenario_deadline(temp_root: Path) -> dict:
    """Deadline notifier — собрать горящие дедлайны."""
    from datetime import datetime, timedelta
    today = datetime.now().date()
    c1 = Client(
        id="c1",
        name="A",
        orders=[
            Order(
                id="o1",
                service_type="Горящий",
                deadline=(today + timedelta(days=2)).strftime("%d.%m.%Y"),
            ),
            Order(
                id="o2",
                service_type="Просроченный",
                deadline=(today - timedelta(days=1)).strftime("%d.%m.%Y"),
            ),
            Order(
                id="o3",
                service_type="OK",
                deadline=(today + timedelta(days=30)).strftime("%d.%m.%Y"),
            ),
            Order(
                id="o4",
                service_type="Завершён",
                deadline=(today + timedelta(days=1)).strftime("%d.%m.%Y"),
                status="Завершен",
            ),
        ],
    )
    alerts = collect_deadline_alerts([c1])
    # Должны попасть 3: o1 (Горящий), o2 (просроченный), o4 завершённый нет.
    order_names = {a.order_name for a in alerts}
    assert "Горящий" in order_names
    assert "Просроченный" in order_names
    assert "OK" not in order_names
    assert "Завершён" not in order_names  # статус "Завершен" исключает
    return {"alerts": len(alerts)}


def scenario_import(temp_root: Path) -> dict:
    """Folder import: создать временную структуру, просканировать, применить."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        client_dir = root / "Иван"
        order_dir = client_dir / "Заказ-1"
        order_dir.mkdir(parents=True)
        (order_dir / "материал.txt").write_text("x", encoding="utf-8")
        (order_dir / "черновик.txt").write_text("y", encoding="utf-8")

        scan = scan_client_folder(str(root), "Иван")
        assert len(scan) == 1
        assert scan[0]["client_name"] == "Иван"
        clients: List[Client] = []
        applied, orders_created = apply_folder_scan_results(clients, scan)
        assert applied == 1
        assert orders_created == 1
        assert len(clients) == 1
        assert clients[0].orders[0].files  # хотя бы один файл
    return {"imported_clients": 1, "orders": 1}


def main() -> int:
    # Force UTF-8 stdout for emoji/currency symbols in CP1251 consoles.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    print("=== FinanceFugue smoke-test ===\n")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        results = {}
        for name, fn in [
            ("1. Empty", scenario_empty),
            ("2. Medium (100)", scenario_medium),
            ("3. Large (10k)", scenario_large),
            ("4. Path safety", scenario_safety_smoke),
            ("5. Deletion", scenario_deletion),
            ("6. Deadline", scenario_deadline),
            ("7. Folder import", scenario_import),
        ]:
            t0 = time.perf_counter()
            try:
                res = fn(tmp_root)
                elapsed = time.perf_counter() - t0
                results[name] = {"ok": True, "sec": round(elapsed, 2), **res}
                print(f"  [OK] {name:<22} ({elapsed:.2f}s)")
                for k, v in res.items():
                    print(f"        {k}: {v}")
            except Exception as e:  # noqa: BLE001
                results[name] = {"ok": False, "error": str(e)}
                print(f"  [FAIL] {name}: {e}")
                return 1
    failures = [n for n, r in results.items() if not r["ok"]]
    print(f"\n=== {len(results) - len(failures)}/{len(results)} OK ===")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
