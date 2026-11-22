"""Loads config/rules.yaml and checks the keys every module relies on are present.

Called by: cli.py, core/runner.py, core/ledger.py, verdict/, report/, sources/.
Calls: PyYAML. Values belong to the finance partner; code reads them, never hard-codes them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEFAULT_RULES = Path(__file__).resolve().parent.parent / "config" / "rules.yaml"

REQUIRED_KEYS = [
    "limits.max_cost_inr", "limits.max_seconds", "limits.max_credits",
    "limits.per_call_timeout_s",
    "costs.crustdata.inr_per_credit", "costs.llm.default.inr_per_1k_tokens_in",
    "costs.llm.default.inr_per_1k_tokens_out", "costs.web.inr_per_call",
    "identity.min_signals", "materiality", "tolerances", "output.fields",
    "actions.test_inbox",
    "verdict.supported_margin", "verdict.strong_margin", "verdict.fresh_days",   # D8
]


def rule(rules: dict[str, Any], dotted: str) -> Any:
    """rule(rules, "limits.max_cost_inr") -> value. KeyError names the missing key."""
    node: Any = rules
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(f"config/rules.yaml is missing '{dotted}'")
        node = node[part]
    return node


def load_rules(path: str | Path = DEFAULT_RULES) -> dict[str, Any]:
    """Read and validate rules.yaml. Fails fast so a bad live edit is caught at start."""
    with open(path, encoding="utf-8") as f:
        rules = yaml.safe_load(f) or {}
    missing = []
    for key in REQUIRED_KEYS:
        try:
            rule(rules, key)
        except KeyError:
            missing.append(key)
    if missing:
        raise ValueError(f"{path} is missing required keys: {', '.join(missing)}")
    return rules
