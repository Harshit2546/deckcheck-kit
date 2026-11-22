"""Read API keys from the process environment, falling back to the repo-root `.env` file.

Who calls it: extract/claims.py (OPENAI_API_KEY, GEMINI_API_KEY), sources/crust.py
(CRUSTDATA_API_KEY). What it calls: only the filesystem. The shell no longer has to
`source .env` first, so runs work the same from bash, PowerShell, cmd and Streamlit.
A value already set in the environment always wins over `.env`. Never logs values.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def _norm(name: str) -> str:
    return "_".join(name.strip().upper().split())


def read_env_file(path: Path = ENV_FILE) -> dict[str, str]:
    """Parse KEY=VALUE lines; tolerant of a BOM, CRLF, `export `, quotes, comments and blanks."""
    if not path.is_file():
        return {}
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError):
        raise RuntimeError(f"Unable to read the ignored {path.name}") from None
    values: dict[str, str] = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.removeprefix("export ").partition("=")
        value = value.strip()
        if value[:1] in ("'", '"') and value[-1:] == value[:1] and len(value) >= 2:
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        values[_norm(name)] = value.strip()
    return values


def get_key(*names: str, path: Path = ENV_FILE) -> str:
    """First non-empty value among `names`: environment first, then `.env`. Empty string if none."""
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    file_values = read_env_file(path)
    for name in names:
        value = file_values.get(_norm(name), "").strip()
        if value:
            return value
    return ""
