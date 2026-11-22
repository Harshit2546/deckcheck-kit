"""Shared helper for the web-sourced verdict rules (market_size, customer; D16, T33).

Who calls it: verdict/market_size.py, verdict/customer.py.
What it calls: verdict/common.py (parse_date). Pure: no I/O.
"""

from __future__ import annotations

from datetime import date
from typing import Any

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
