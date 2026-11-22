"""Name and domain normalisation for entity matching. Pure functions, no I/O.

Who calls it: resolve/entities.py, resolve/payloads.py, and checkers that need to find a founder entity
(`find_founder`). What it calls: the standard library only.
Matching is deliberately strict (equal after cleaning, no fuzzy score): a near-miss is NOT a signal.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

# Legal-form words dropped from company names so "Acme Pvt Ltd" equals "Acme". Words like "technologies" are kept.
LEGAL_SUFFIXES = frozenset({
    "inc", "incorporated", "ltd", "limited", "llc", "llp", "pvt", "private", "corp", "corporation",
    "co", "gmbh", "plc", "pte", "sa", "bv", "ag",
})


def _tokens(text: str) -> list[str]:
    """Lower-case, accent-free word tokens; punctuation splits words."""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    return re.findall(r"[a-z0-9]+", folded)


def company_key(name: Any) -> tuple[str, ...]:
    """Order-sensitive token tuple with legal suffixes removed; empty tuple if nothing is left."""
    return tuple(t for t in _tokens(str(name or "")) if t not in LEGAL_SUFFIXES)


def person_key(name: Any) -> frozenset[str]:
    """Order-free token set, so 'Sharma, Priya' equals 'Priya Sharma'. A single token is too weak: empty set."""
    tokens = frozenset(_tokens(str(name or "")))
    return tokens if len(tokens) >= 2 else frozenset()


def company_names_match(a: Any, b: Any) -> bool:
    ka, kb = company_key(a), company_key(b)
    return bool(ka) and ka == kb


def person_names_match(a: Any, b: Any) -> bool:
    ka, kb = person_key(a), person_key(b)
    return bool(ka) and ka == kb


def normalize_domain(value: Any) -> str:
    """'https://www.Acme.com/about' -> 'acme.com'. Empty string if there is nothing usable."""
    text = str(value or "").strip().lower()
    text = re.sub(r"^[a-z][a-z0-9+.-]*://", "", text)
    text = text.split("/")[0].split("?")[0].split("#")[0].split(":")[0].rstrip(".")
    return text[4:] if text.startswith("www.") else text


def normalize_url(value: Any) -> str:
    """Profile URL key: no scheme, no 'www.', no query or trailing slash, lower case."""
    text = str(value or "").strip().lower()
    text = re.sub(r"^[a-z][a-z0-9+.-]*://", "", text).split("?")[0].split("#")[0].rstrip("/")
    return text[4:] if text.startswith("www.") else text


def find_founder(entities: dict[str, Any], subject: str) -> dict[str, Any] | None:
    """The founder entity whose deck name equals `subject` (for checkers); None if there is none."""
    for founder in (entities or {}).get("founders", []):
        if person_names_match(founder.get("name"), subject):
            return founder
    return None
