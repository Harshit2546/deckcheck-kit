"""One structured log line per pipeline step: run id, claim id, step, result (AGENTS.md: no print()).

Who calls it: every lane, once per step, through `log_step`; cli.py calls `configure` once at start.
What it calls: the standard `logging` module only. Never pass secrets or raw person payloads as extra fields.
Output: one JSON object per line on stderr and, when configured, appended to a log file (never edited).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOGGER_NAME = "deckcheck"
_configured = False


class _JsonLineFormatter(logging.Formatter):
    """The message is already a JSON line; the formatter only passes it through."""

    def format(self, record: logging.LogRecord) -> str:
        return record.getMessage()


def configure(log_file: str | Path | None = None, level: int = logging.INFO) -> logging.Logger:
    """Attach the stderr handler (and the file handler if given). Safe to call more than once."""
    global _configured
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False
    if not _configured:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(_JsonLineFormatter())
        logger.addHandler(handler)
        _configured = True
    if log_file is not None:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        already = any(
            isinstance(h, logging.FileHandler) and Path(h.baseFilename) == path.resolve() for h in logger.handlers
        )
        if not already:
            file_handler = logging.FileHandler(path, encoding="utf-8")
            file_handler.setFormatter(_JsonLineFormatter())
            logger.addHandler(file_handler)
    return logger


def log_step(
    run_id: str | None,
    step: str,
    result: str,
    claim_id: str | None = None,
    level: int = logging.INFO,
    **extra: Any,
) -> dict[str, Any]:
    """Write one line: {ts, run_id, claim_id, step, result, ...extra}. Returns the record (handy in tests)."""
    if not _configured:
        configure()
    record: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "claim_id": claim_id,
        "step": step,
        "result": result,
    }
    record.update(extra)
    logging.getLogger(_LOGGER_NAME).log(level, json.dumps(record, default=str, ensure_ascii=False))
    return record
