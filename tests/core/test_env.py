"""core/env.py: keys come from the environment first, then a tolerant .env parse."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.env import get_key, read_env_file


@pytest.fixture
def env_file(tmp_path: Path) -> Path:
    p = tmp_path / ".env"
    p.write_bytes(
        "﻿# comment\r\n"
        "export OPENAI_API_KEY=\"sk-quoted\"\r\n"
        "GEMINI_API_KEY = 'g-single' \r\n"
        "CRUSTDATA_API_KEY=c-plain # trailing comment\r\n"
        "\r\nEMPTY=\r\n".encode("utf-8")
    )
    return p


def test_parse_handles_bom_crlf_export_quotes_comments(env_file: Path) -> None:
    v = read_env_file(env_file)
    assert v["OPENAI_API_KEY"] == "sk-quoted"
    assert v["GEMINI_API_KEY"] == "g-single"
    assert v["CRUSTDATA_API_KEY"] == "c-plain"
    assert v["EMPTY"] == ""


def test_environment_wins_over_file(env_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-shell")
    assert get_key("OPENAI_API_KEY", path=env_file) == "sk-from-shell"


def test_file_used_when_environment_empty(env_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert get_key("GEMINI_API_KEY", "GOOGLE_API_KEY", path=env_file) == "g-single"


def test_missing_file_and_env_gives_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NOPE_KEY", raising=False)
    assert get_key("NOPE_KEY", path=tmp_path / "absent.env") == ""
