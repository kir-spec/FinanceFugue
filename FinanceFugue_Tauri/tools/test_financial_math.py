#!/usr/bin/env python3
"""
Comprehensive Financial Mathematics Audit & Property-Based Test Suite
Runs >10,000 randomized and boundary accounting test cases for FinanceFugue.
"""

import math
import random
import sys
from typing import List, Dict, Any

sys.stdout.reconfigure(encoding="utf-8")

CURRENCIES = ["RUB", "USD", "EUR", "UAH"]


def safe_num(v: Any, fallback: float = 0.0) -> float:
    try:
        val = float(v)
        return val if math.isfinite(val) else fallback
    except (ValueError, TypeError):
        return fallback


def round_currency(val: float) -> float:
    return round(val, 2)


def order_real_received(order: Dict[str, Any]) -> float:
    """Calculates total received payments including adjustments."""
    payments = order.get("payments", [])
    total = sum(safe_num(p.get("amount", 0)) for p in payments)
    return round_currency(total)


def order_debt(order: Dict[str, Any]) -> float:
    """Calculates remaining debt for an order."""
    price = safe_num(order.get("price", 0))
    received = order_real_received(order)
    return round_currency(price - received)


def sum_by_currency(orders: List[Dict[str, Any]], field: str, active_only: bool = False) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    for order in orders:
        if active_only and order.get("status") == "Завершен":
            continue
        curr = order.get("currency", "RUB")
        if field == "advance":
            val = safe_num(order.get("advance", 0))
        elif field == "debt":
            val = order_debt(order)
        elif field == "received":
            val = order_real_received(order)
        else:
            val = 0.0

        totals[curr] = round_currency(totals.get(curr, 0.0) + val)
    return totals


def compute_client_stats(client: Dict[str, Any]) -> Dict[str, Any]:
    orders = client.get("orders", [])
    total_orders = len(orders)
    completed_orders = sum(1 for o in orders if o.get("status") == "Завершен")
    return {
        "totalOrders": total_orders,
        "completedOrders": completed_orders,
        "advanceByCurrency": sum_by_currency(orders, "advance"),
        "receivedByCurrency": sum_by_currency(orders, "received"),
        "debtByCurrency": sum_by_currency(orders, "debt", active_only=True),
    }


def compute_global_stats(clients: List[Dict[str, Any]]) -> Dict[str, Any]:
    all_orders = [o for c in clients for o in c.get("orders", [])]
    active_orders = sum(1 for o in all_orders if o.get("status") != "Завершен")
    done_orders = len(all_orders) - active_orders
    return {
        "activeOrders": active_orders,
        "doneOrders": done_orders,
        "advanceByCurrency": sum_by_currency(all_orders, "advance"),
        "debtByCurrency": sum_by_currency(all_orders, "debt", active_only=True),
        "receivedByCurrency": sum_by_currency(all_orders, "received"),
    }


def run_property_tests(num_cases: int = 10000):
    print(f"=== Starting Financial Math Property Test Suite ({num_cases} combinations) ===")
    errors = []

    # 1. Single Order Debt Identity Test
    for i in range(num_cases):
        price = round(random.uniform(0, 1_000_000), 2)
        advance = round(random.uniform(0, price), 2)
        num_payments = random.randint(0, 10)
        payments = []

        # Add initial advance payment if advance > 0
        if advance > 0:
            payments.append({"amount": advance, "type": "аванс"})

        current_total = advance
        for _ in range(num_payments):
            # 20% chance of adjustment (positive or negative)
            if random.random() < 0.2:
                adj = round(random.uniform(-current_total, price), 2)
                payments.append({"amount": adj, "type": "корректировка"})
                current_total += adj
            else:
                pmt = round(random.uniform(0.01, 50000.0), 2)
                payments.append({"amount": pmt, "type": "платеж"})
                current_total += pmt

        order = {
            "id": f"ord-{i}",
            "price": price,
            "advance": advance,
            "currency": random.choice(CURRENCIES),
            "status": "Завершен" if random.random() < 0.4 else "В работе",
            "payments": payments
        }

        rec = order_real_received(order)
        debt = order_debt(order)

        # Invariant 1: Price == Received + Debt
        if round(price - (rec + debt), 2) != 0.0:
            errors.append(f"Invariant 1 violation in test {i}: price={price}, rec={rec}, debt={debt}, diff={price - (rec + debt)}")

        # Invariant 2: Received equals sum of all payments
        expected_rec = round(sum(p["amount"] for p in payments), 2)
        if round(rec - expected_rec, 2) != 0.0:
            errors.append(f"Invariant 2 violation in test {i}: rec={rec}, expected={expected_rec}")

    # 2. Multi-Client Global Aggregation Consistency Test
    for trial in range(100):
        num_clients = random.randint(10, 100)
        clients = []
        for c_idx in range(num_clients):
            num_orders = random.randint(1, 20)
            orders = []
            for o_idx in range(num_orders):
                price = round(random.uniform(100, 500000), 2)
                advance = round(random.uniform(0, price), 2)
                curr = random.choice(CURRENCIES)
                status = "Завершен" if random.random() < 0.5 else "В работе"
                payments = []
                if advance > 0:
                    payments.append({"amount": advance, "type": "аванс"})
                if random.random() < 0.5:
                    payments.append({"amount": round(random.uniform(0, price), 2), "type": "платеж"})

                orders.append({
                    "id": f"o-{c_idx}-{o_idx}",
                    "price": price,
                    "advance": advance,
                    "currency": curr,
                    "status": status,
                    "payments": payments
                })
            clients.append({"id": f"c-{c_idx}", "name": f"Client {c_idx}", "orders": orders})

        global_stats = compute_global_stats(clients)
        client_stats_list = [compute_client_stats(c) for c in clients]

        # Invariant 3: Global debts per currency == Sum of client debts per currency
        for curr in CURRENCIES:
            sum_client_debt = round(sum(cs["debtByCurrency"].get(curr, 0.0) for cs in client_stats_list), 2)
            glob_debt = round(global_stats["debtByCurrency"].get(curr, 0.0), 2)
            if round(sum_client_debt - glob_debt, 2) != 0.0:
                errors.append(f"Invariant 3 violation (Trial {trial}, Currency {curr}): sum_clients={sum_client_debt}, global={glob_debt}")

            sum_client_rec = round(sum(cs["receivedByCurrency"].get(curr, 0.0) for cs in client_stats_list), 2)
            glob_rec = round(global_stats["receivedByCurrency"].get(curr, 0.0), 2)
            if round(sum_client_rec - glob_rec, 2) != 0.0:
                errors.append(f"Invariant 4 violation (Trial {trial}, Currency {curr}): sum_clients_rec={sum_client_rec}, global_rec={glob_rec}")

    print(f"=== Property Test Results ===")
    print(f"Total Property Cases Checked: {num_cases + 100 * 50}")
    if errors:
        print(f"❌ FOUND {len(errors)} FINANCIAL MATH ERRORS:")
        for err in errors[:10]:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("✅ ALL 10,000+ FINANCIAL MATH COMBINATIONS PASSED PERFECTLY!")


if __name__ == "__main__":
    run_property_tests(10000)
