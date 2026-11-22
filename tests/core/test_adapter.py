"""D3 tests: io/adapter.py maps a request JSON to RunInput and a report to the result JSON.

Called by: pytest. Calls: core/adapter_loader.py, io/adapter.py, core/models.py.
"""

import pytest

from core.adapter_loader import load_adapter
from core.models import Action, ActionStatus, ActionType

REQUEST = {"request": "Check this deck before our second meeting.", "deck_path": "deck.pdf",
           "company_domain": "Example.IN", "deck_date": "2026-10-01",
           "founder_urls": ["https://example.com/in/a"]}

REPORT = {
    "run": {"id": "run-1", "domain": "example.in", "deck_date": "2026-10-01"},
    "claims": [{"claim_id": "run-1-c001", "slide": 3, "quote": "120 people", "type": "team_size",
                "value": 120, "label": "CONTRADICTED", "reason_code": "outside_tolerance",
                "explanation": "x", "confidence": "high", "missing": None, "new_field": "kept",
                "sources": [{"source_type": "crustdata_company", "locator": "/company/enrich",
                             "field_or_quote": "headcount", "value": 80,
                             "record_date": "2026-09-30", "retrieved_at": "2026-11-22T10:00:00+00:00",
                             "call_id": "call-1"}]}],
    "red_flags": [{"claim_id": "run-1-c001"}], "founder_questions": [{"question": "q"}],
    "evidence_requests": [], "held": [],
    "ledger": {"calls": 3, "credits": 2.0, "cost_inr": 4.5, "duration_ms": 2350},
}


def test_from_kit_maps_request():
    r = load_adapter().from_kit(REQUEST)
    assert (r.deck_path, r.domain, r.deck_date, r.deck_date_source) == \
        ("deck.pdf", "example.in", "2026-10-01", "input")
    assert r.founder_urls == ["https://example.com/in/a"]


def test_from_kit_null_date_falls_back_to_pdf():
    r = load_adapter().from_kit({**REQUEST, "deck_date": None, "founder_urls": None})
    assert r.deck_date is None and r.deck_date_source == "missing" and r.founder_urls == []


@pytest.mark.parametrize("bad, match", [({"company_domain": ""}, "company_domain"),
                                        ({"deck_path": None}, "deck_path"),
                                        ({"deck_date": "01/10/2026"}, "does not match"),
                                        ({"founder_urls": "https://x"}, "founder_urls")])
def test_from_kit_rejects_bad_requests(bad, match):
    with pytest.raises(ValueError, match=match):
        load_adapter().from_kit({**REQUEST, **bad})


def test_to_kit_matches_d3():
    email = Action("a1", "run-1", ActionType.FOUNDER_EMAIL, "k", "inbox@test", "s", "b",
                   status=ActionStatus.PENDING)
    out = load_adapter().to_kit(REPORT, company={"name": "Example", "confidence": "high",
                                                 "locator": "/company/identify"},
                                founder_email=email)
    assert list(out) == ["run_id", "company", "as_of", "claims", "red_flags", "founder_questions",
                         "evidence_requests", "ledger", "founder_email"]
    assert out["company"] == {"name": "Example", "domain": "example.in", "identity": "high",
                              "source": "/company/identify"}
    claim = out["claims"][0]
    assert list(claim)[4:6] == ["claimed_value", "verdict"]
    assert claim["claimed_value"] == 120 and claim["verdict"] == "CONTRADICTED"
    assert claim["new_field"] == "kept"
    assert claim["sources"] == [{"url_or_endpoint": "/company/enrich", "field_or_quote": "headcount",
                                 "value": 80, "record_date": "2026-09-30",
                                 "retrieved_at": "2026-11-22T10:00:00+00:00"}]
    assert out["ledger"] == {"calls": 3, "credits": 2.0, "cost_inr": 4.5, "seconds": 2.4}
    assert out["founder_email"] == {"status": "pending", "recipient": "inbox@test"}


def test_to_kit_without_company_or_email():
    out = load_adapter().to_kit(REPORT)
    assert out["company"]["domain"] == "example.in" and out["company"]["name"] is None
    assert out["founder_email"] is None
