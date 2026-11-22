"""Shared helpers for the web-sourced verdict rules (market_size, customer; D16, T33; undated items D17, T34).

Who calls it: verdict/market_size.py, verdict/customer.py.
What it calls: verdict/common.py (parse_date). Pure: no I/O.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from core.models import Confidence
from verdict.common import parse_date


def admissible(items: Any, ref: date, max_age_days: float) -> list[dict[str, Any]]:
    """Keep dicts whose own published_date is on or before `ref` (D3) and not older than max_age_days."""
    kept = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        published = parse_date(item.get("published_date"))
        if published is not None and published <= ref and (ref - published).days <= max_age_days:
            kept.append(item)
    return kept


def select(items: Any, st: dict[str, Any], max_age_days: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """D17: dated items that pass `admissible` always win. Only when none pass, and the undated guard holds
    (st["undated_ok"]), items with published_date None are used, and the returned state is marked undated
    (low confidence, `_undated` reason). Returns (items, state to pass to make)."""
    dated = admissible(items, st["ref"], max_age_days)
    if dated:
        return dated, st
    if not st.get("undated_ok"):
        return [], st
    undated = [i for i in (items if isinstance(items, list) else [])
               if isinstance(i, dict) and i.get("published_date") is None]
    if not undated:
        return [], st
    return undated, {**st, "undated": True, "ceiling": Confidence.LOW, "fresh": False}
