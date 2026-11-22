"""Loads and validates config/rules.yaml into the `Rules` model (defined in core/models.py).

Who calls it: runner, verdict engine, checkers, report, actions. cli.py passes an optional path.
What it calls: PyYAML and core.models. Env var DECKCHECK_RULES overrides the default path.
A wrong or misspelled key fails loudly here, so a live edit of rules.yaml cannot silently do nothing.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from core.models import Rules

DEFAULT_RULES_PATH = Path(__file__).resolve().parent.parent / "config" / "rules.yaml"


def load_rules(path: str | Path | None = None) -> Rules:
    """Read the YAML file and return validated rules. Raises ValueError with the file name on bad content."""
    rules_path = Path(path or os.environ.get("DECKCHECK_RULES") or DEFAULT_RULES_PATH)
    with open(rules_path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise ValueError(f"{rules_path}: expected a mapping at the top level")
    try:
        return Rules.model_validate(raw)
    except Exception as exc:  # pydantic.ValidationError: add the file name so a human can find it fast
        raise ValueError(f"{rules_path}: {exc}") from exc
