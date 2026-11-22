"""T04 tests: request files are found, inputs go through the D3 adapter, a run row is created,
and the Run page lists it with a Resume choice.

Called by: pytest. Calls: ui/data.py, ui/app.py (Streamlit AppTest), core/store.py.
"""

import json
import subprocess

import pytest
from conftest import open_app

from core import store
from ui import data


def test_request_files_lists_decks_then_examples(tmp_path, monkeypatch):
    (tmp_path / "tests" / "decks").mkdir(parents=True)
    (tmp_path / "tests" / "requests").mkdir()
    (tmp_path / "tests" / "decks" / "deck_a_request.json").write_text("{}")
    (tmp_path / "tests" / "decks" / "deck_a.pdf").write_bytes(b"%PDF")
    (tmp_path / "tests" / "requests" / "example_request.json").write_text("{}")
    monkeypatch.setattr(data, "ROOT", tmp_path)
    assert [p.name for p in data.request_files()] == ["deck_a_request.json", "example_request.json"]


def test_request_file_deck_path_is_relative_to_the_file(tmp_path, deck):
    req = tmp_path / "r.json"
    req.write_text(json.dumps({"deck_path": "deck.pdf", "company_domain": "Locus.sh",
                               "deck_date": "2026-11-15"}))
    run_input = data.input_from_request_file(req)
    assert run_input.deck_path == str(deck.resolve()) and run_input.domain == "locus.sh"


def test_form_input_goes_through_adapter(deck):
    run_input = data.input_from_form(deck, "locus.sh", None, ["https://x/in/a"])
    assert run_input.deck_date_source == "missing" and run_input.founder_urls == ["https://x/in/a"]
    with pytest.raises(ValueError):
        data.input_from_form(deck, "locus.sh", "15-11-2026", [])


def test_create_run_and_page_lists_it(conn, db_path, deck):
    with pytest.raises(ValueError, match="deck not found"):
        data.create_run(conn, data.input_from_form(deck.with_name("nope.pdf"), "locus.sh", None, []))
    rid = data.create_run(conn, data.input_from_form(deck, "locus.sh", "2026-11-15", []))
    assert store.get_run(conn, rid).state.value == "created"
    at = open_app(db_path, "Run")
    assert rid in at.dataframe[0].value["run_id"].tolist()
    assert rid in at.selectbox[-1].options          # resume choice


def test_launch_runs_cli_resume_in_background(db_path):
    proc = data.launch(db_path, "run-does-not-exist")
    assert proc.wait(timeout=60) == 2                # cli.py resume: unknown run id
    assert isinstance(proc, subprocess.Popen)
