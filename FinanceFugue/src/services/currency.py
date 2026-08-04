"""Форматирование и агрегация сумм по валютам (без конвертации)."""
from __future__ import annotations

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

CURRENCY_SYMBOLS = {
    "RUB": "₽",
    "USD": "$",
    "EUR": "€",
    "UAH": "₴",
}


def currency_symbol(code: str) -> str:
    return CURRENCY_SYMBOLS.get((code or "RUB").upper(), code or "RUB")


def _round_half_up(amount: float) -> Decimal:
    """Финансовое округление (HALF_UP), а не банкирское HALF_EVEN."""
    return Decimal(str(amount)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def format_amount(amount: float, currency: str = "RUB") -> str:
    rounded = _round_half_up(amount)
    return f"{rounded:,} {currency_symbol(currency)}".replace(",", " ")


def format_multi_currency(totals: dict[str, float]) -> str:
    """Форматирует суммы по валютам без смешивания."""
    if not totals:
        return format_amount(0.0)
    non_zero = {c: v for c, v in totals.items() if v != 0}
    if not non_zero:
        return format_amount(0.0, next(iter(totals), "RUB"))
    parts = [format_amount(v, c) for c, v in sorted(non_zero.items())]
    return " + ".join(parts)


def sum_by_currency(
    orders: Iterable,
    *,
    field: str,
    active_only: bool = False,
) -> dict[str, float]:
    """Суммирует поле заказа (advance, debt, total_received) в разрезе валют."""
    totals: dict[str, float] = defaultdict(float)
    for order in orders:
        if active_only and getattr(order, "status", "") == "Завершен":
            continue
        currency = getattr(order, "currency", "RUB") or "RUB"
        if field == "debt":
            value = order.debt
        elif field == "advance":
            value = order.advance
        elif field == "total_received":
            value = order.total_received
        else:
            raise ValueError(f"Unknown field: {field}")
        totals[currency] += value
    return dict(totals)


def has_outstanding_debt(debt_by_currency: dict[str, float]) -> bool:
    """Семантически корректная проверка «есть ли долги» с учётом валют.

    Раньше делали ``sum(debt_by_currency.values()) > 0`` — это смешивало
    разные валюты (например, RUB-долг и EUR-долг давали сумму, отличную
    от любого реального значения).
    """
    return any(v > 0 for v in debt_by_currency.values())
