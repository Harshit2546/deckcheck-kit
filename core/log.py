"""Step logging: one line per step with run id, claim id, step and result (AGENTS.md section 3).

Called by: every module instead of print(). Calls: stdlib logging only.
Lines go to stderr and are appended to logs/deckcheck.log. Never edit that file by hand.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

LOG_DIR = Path(os.environ.get("DECKCHECK_LOG_DIR", "logs"))
_logger = logging.getLogger("deckcheck")


def _setup() -> None:
    if _logger.handlers:
        return
    _logger.setLevel(logging.INFO)
    _logger.propagate = False
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%dT%H:%M:%SZ")
    fmt.converter = time.gmtime   # UTC, same clock as ledger.ts and run ids
    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    _logger.addHandler(stream)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    file = logging.FileHandler(LOG_DIR / "deckcheck.log", encoding="utf-8")
    file.setFormatter(fmt)
    _logger.addHandler(file)


def _line(run_id: str | None, claim_id: str | None, step: str, result: str,
          extra: dict[str, Any]) -> str:
    parts = [f"run={run_id or '-'}", f"claim={claim_id or '-'}", f"step={step}",
             f"result={result}"]
    parts += [f"{k}={v!r}" if isinstance(v, str) and " " in v else f"{k}={v}"
              for k, v in extra.items()]
    return " ".join(parts)


def log_step(run_id: str | None, claim_id: str | None, step: str, result: str,
             **extra: Any) -> None:
    """Log one step, e.g. log_step(run.id, claim.id, "check.funding", "ok", calls=2)."""
    _setup()
    _logger.info(_line(run_id, claim_id, step, result, extra))


def log_error(run_id: str | None, claim_id: str | None, step: str, error: str,
              **extra: Any) -> None:
    """Log a failed step; the caller still decides whether the claim becomes HELD."""
    _setup()
    _logger.error(_line(run_id, claim_id, step, "error", {"error": error, **extra}))
