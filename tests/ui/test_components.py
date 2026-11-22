"""T29 tests: payloads for the motion components (route tracker, slide strip, value gauge) and the
static fallback when components are off. The JS itself is checked in a browser (HANDOFF).

Called by: pytest. Calls: ui/data.py, ui/components/__init__.py, core/config.py.
"""

import copy

import pytest

from core.config import load_rules
from ui import components, data


def _row(**kw):
    row = {"claim_id": "c1", "slide": 4, "type": "team_size", "metric": "headcount", "claimed_value": 300,
           "unit": "people", "verdict": "CONTRADICTED", "quote": "We are 300 people",
           "observed": {"headcount": 210, "record_date": "2026-11-01"}}
    row.update(kw)
    return row


def test_gauge_uses_found_number_and_rules_tolerance():
    rules = load_rules()
    g = data.gauge_payload(_row(), rules)
    assert g == {"claimed": 300.0, "found": 210.0, "tol_pct": float(rules["tolerances"]["team_size"]["tolerance_pct"]),
                 "unit": "people", "metric": "headcount", "label": "CONTRADICTED"}


def test_gauge_reads_matched_round_amount():
    row = _row(type="funding", metric="round_amount", claimed_value=50_000_000, unit="USD", verdict="SUPPORTED",
               observed={"matched_round": {"stage": "series_c", "amount": 50_000_000}})
    assert data.gauge_payload(row, load_rules())["found"] == 50_000_000.0


@pytest.mark.parametrize("change", [
    {"metric": "title"},                               # not a number metric
    {"observed": {}},                                  # checker found nothing
    {"observed": {"headcount": "about 200"}},          # not a number
    {"claimed_value": 0},                              # no scale around zero
    {"claimed_value": None},
    {"observed": {"headcount": True}},                 # bool is not a count
])
def test_gauge_none_when_nothing_to_draw(change):
    assert data.gauge_payload(_row(**change), load_rules()) is None


def test_gauge_none_without_tolerance():
    rules = copy.deepcopy(load_rules())
    del rules["tolerances"]["team_size"]["tolerance_pct"]
    assert data.gauge_payload(_row(), rules) is None


def test_strip_payload_in_slide_order():
    rows = [_row(claim_id="b", slide=6, verdict="HELD"), _row(claim_id="a", slide=3, verdict="SUPPORTED"),
            _row(claim_id="c", slide=6, verdict="PENDING")]
    assert [(p["claim_id"], p["label"]) for p in data.strip_payload(rows)] == \
        [("a", "SUPPORTED"), ("b", "HELD"), ("c", "PENDING")]


def _progress(**kw):
    p = {"state": "checking", "order": ["created", "extracted", "resolved", "checking", "decided", "reported", "done"],
         "index": 3, "failed": False, "error": None, "claims": 3,
         "claims_by_state": {"pending": 1, "checked": 0, "decided": 2}, "finished": False}
    p.update(kw)
    return p


def test_route_payload_running():
    r = data.route_payload(_progress(), [_row()])
    assert r["index"] == 3 and r["status"] == "At checking. 2 of 3 claims decided, 1 not checked yet."
    assert r["claims"][0]["claim_id"] == "c1"


def test_route_payload_failed_places_marker_where_claims_stopped():
    r = data.route_payload(_progress(state="failed", index=-1, failed=True, error="boom"), [])
    assert r["index"] == 3 and r["failed"] and "boom" in r["status"]
    none = data.route_payload(_progress(state="failed", index=-1, failed=True, claims=0,
                                        claims_by_state={"pending": 0, "checked": 0, "decided": 0}), [])
    assert none["index"] == 0


def test_motion_returns_missing_when_static(monkeypatch):
    monkeypatch.setenv("DECKCHECK_STATIC_UI", "1")
    assert not components.enabled()
    assert components.motion("strip", {}, key="x") is components.MISSING


def test_component_frontend_files_exist():
    names = {p.name for p in components.FRONTEND.iterdir()}
    assert {"index.html", "bridge.js", "style.css", "route.js", "strip.js", "gauge.js", "sent.js"} <= names
    for js in ("route.js", "strip.js", "gauge.js", "sent.js"):
        assert "innerHTML" not in (components.FRONTEND / js).read_text(encoding="utf-8")   # data stays text
