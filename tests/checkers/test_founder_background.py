"""Tests for checkers/founder_background.py: the resolved founder's own person record (D18), sources faked."""

from typing import Any

import pytest

from checker_fakes import make_ctx
from checkers.founder_background import check
from core.models import RunContext
from sources import crust

PEOPLE: dict[str, Any] = {}
URL = "https://www.linkedin.com/in/priya-sharma-test/"


@pytest.fixture(autouse=True)
def fake_people(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Any]]:
    calls: list[tuple[str, Any]] = []

    def get_people(ctx: RunContext, urls: list[str]) -> tuple[dict[str, Any] | None, str | None]:
        calls.append(("enrich", list(urls)))
        return PEOPLE.get("enrich"), "call-enrich"

    def search_people(ctx: RunContext, name: str, company_id: str) -> tuple[dict[str, Any] | None, str | None]:
        calls.append(("search", (name, company_id)))
        return PEOPLE.get("search"), "call-search"

    PEOPLE.clear()
    monkeypatch.setattr(crust, "get_people", get_people)
    monkeypatch.setattr(crust, "search_people", search_people)
    return calls


def _founder(identity: str = "confirmed", signals: int = 2, profile_url: str | None = URL,
             person_id: str = "p-1", name: str = "Priya Sharma") -> dict[str, Any]:
    return {"id": person_id, "identity": identity, "identity_signals": signals, "confidence": "high",
            "signals": [], "reason": None, "call_id": "call-enrich", "name": name, "profile_url": profile_url}


def _ctx(record: dict[str, Any] | None, founder: dict[str, Any] | None = None, **kw: Any) -> RunContext:
    ctx = make_ctx(run_id="run_1", company=None, deck_date="2024-05-15", **kw)
    founder = founder or _founder()
    ctx.entities["founders"] = [founder]
    if record is not None:
        key = "enrich" if founder.get("profile_url") else "search"
        PEOPLE[key] = ({"matches": [{"confidence_score": 1, "person_data": record}]} if key == "enrich"
                       else {"profiles": [record]})
    return ctx
from core.config import load_rules
from core.models import Claim, ClaimType, SourceType, VerdictLabel
from verdict.engine import decide


@pytest.fixture
def rules():
    r = load_rules()
    r["verdict"] = {"supported_margin": 0.5, "strong_margin": 2.0, "fresh_days": 90}
    return r


@pytest.fixture
def person_profile_fixture() -> dict:
    return {
        "crustdata_person_id": "p-1",
        "basic_profile": {
            "name": "Priya Sharma",
            "current_title": "Co-founder & CTO",
        },
        "experience": {
            "employment_details": {
                "past": [
                    {
                        "employer": "Flipkart",
                        "title": "VP Engineering",
                        "start_date": "2015-01-01",
                        "end_date": "2020-01-01",
                    }
                ],
                "current": [
                    {
                        "employer": "LogiFast",
                        "title": "Co-founder & CTO",
                        "start_date": "2020-02-01",
                        "end_date": None,
                    }
                ],
            }
        },
        "updated_at": "2024-05-15T00:00:00Z",
    }


def test_founder_past_employer_success(person_profile_fixture: dict, rules: dict) -> None:
    claim = Claim(
        id="c_founder_1",
        run_id="run_1",
        slide=1,
        quote="Priya Sharma was previously VP Engineering at Flipkart",
        type=ClaimType.FOUNDER_BACKGROUND,
        subject="Priya Sharma",
        metric="past_employer",
        value="Flipkart",
    )
    ctx = _ctx(person_profile_fixture)

    result = check(claim, ctx)

    assert result.comparable is True
    assert result.held_reason is None
    assert result.observed["identity"] == "confirmed"
    assert result.observed["identity_signals"] == 2
    assert result.observed["employer_found"] is True
    assert len(result.observed["positions"]) == 1
    assert result.observed["positions"][0]["employer"] == "Flipkart"
    assert result.observed["positions"][0]["title"] == "VP Engineering"
    assert result.observed["title_observed"] == "VP Engineering"
    assert len(result.evidence) == 1
    assert result.evidence[0].source_type == SourceType.CRUSTDATA_PERSON

    v = decide(claim, result, rules)
    assert v.label == VerdictLabel.SUPPORTED
    assert v.reason_code == "employer_listed"


def test_founder_title_check(person_profile_fixture: dict, rules: dict) -> None:
    claim = Claim(
        id="c_founder_title",
        run_id="run_1",
        slide=1,
        quote="Former VP Engineering at Flipkart",
        type=ClaimType.FOUNDER_BACKGROUND,
        subject="Priya Sharma",
        metric="title",
        value="VP Engineering",
    )
    ctx = _ctx(person_profile_fixture)

    result = check(claim, ctx)
    assert result.observed["employer_found"] is True
    assert result.observed["title_observed"] == "VP Engineering"

    v = decide(claim, result, rules)
    assert v.label == VerdictLabel.SUPPORTED
    assert v.reason_code == "title_level_met"


def test_founder_title_contradicted(person_profile_fixture: dict, rules: dict) -> None:
    claim = Claim(
        id="c_founder_title_contra",
        run_id="run_1",
        slide=1,
        quote="Former CEO of Flipkart",
        type=ClaimType.FOUNDER_BACKGROUND,
        subject="Priya Sharma",
        metric="title",
        value="CEO",
    )
    ctx = _ctx(person_profile_fixture)

    result = check(claim, ctx)
    v = decide(claim, result, rules)
    assert v.label == VerdictLabel.CONTRADICTED
    assert v.reason_code == "title_level_lower"


def test_founder_tenure_check(person_profile_fixture: dict, rules: dict) -> None:
    claim = Claim(
        id="c_founder_tenure",
        run_id="run_1",
        slide=1,
        quote="5 years as VP Engineering at Flipkart",
        type=ClaimType.FOUNDER_BACKGROUND,
        subject="Priya Sharma",
        metric="tenure_years",
        value=5,
    )
    ctx = _ctx(person_profile_fixture)

    result = check(claim, ctx)
    assert len(result.observed["positions"]) == 1

    v = decide(claim, result, rules)
    assert v.label == VerdictLabel.SUPPORTED
    assert v.reason_code == "tenure_within_tolerance"


def test_founder_employer_not_found(person_profile_fixture: dict, rules: dict) -> None:
    claim = Claim(
        id="c_founder_missing_emp",
        run_id="run_1",
        slide=1,
        quote="Former VP at Amazon",
        type=ClaimType.FOUNDER_BACKGROUND,
        subject="Priya Sharma",
        metric="past_employer",
        value="Amazon",
    )
    ctx = _ctx(person_profile_fixture)

    result = check(claim, ctx)
    assert result.observed["employer_found"] is False
    assert len(result.observed["positions"]) == 0
    assert result.observed["title_observed"] is None

    assert result.observed["record_date"] is None  # D19 rule 5: a missing job has no date

    v = decide(claim, result, rules)
    assert v.label == VerdictLabel.CANNOT_VERIFY
    # The engine checks dates before the employer rule, so an old deck stops at missing_record_date
    # (a recent deck would give employer_not_in_profile_undated, D17). Never CONTRADICTED.
    assert v.reason_code in ("missing_record_date", "employer_not_in_profile_undated")


def test_founder_missing_payload(rules: dict) -> None:
    claim = Claim(
        id="c_founder_none",
        run_id="run_1",
        slide=1,
        quote="Worked at Google",
        type=ClaimType.FOUNDER_BACKGROUND,
        subject="Unknown Person",
        metric="past_employer",
        value="Google",
    )
    ctx = make_ctx(run_id="run_1", company=None)
    ctx.entities["founders"] = []

    result = check(claim, ctx)
    assert result.comparable is True
    assert result.observed["identity"] == "not_found"
    assert len(result.evidence) == 0

    v = decide(claim, result, rules)
    assert v.label == VerdictLabel.CANNOT_VERIFY
    assert v.reason_code == "no_evidence"


def _employer_claim(subject: str = "Priya Sharma") -> Claim:
    return Claim(id="c_emp", run_id="run_1", slide=1, quote=f"{subject} was VP Engineering at Flipkart",
                 type=ClaimType.FOUNDER_BACKGROUND, subject=subject, metric="past_employer", value="Flipkart")


def test_reads_founders_own_record_by_id_not_a_namesake(person_profile_fixture: dict,
                                                       fake_people: list) -> None:
    namesake = {**person_profile_fixture, "crustdata_person_id": "p-other"}
    ctx = _ctx(None)
    PEOPLE["enrich"] = {"matches": [{"person_data": namesake}, {"person_data": person_profile_fixture}]}
    result = check(_employer_claim(), ctx)
    assert result.observed["employer_found"] is True
    assert result.evidence[0].call_id == "call-enrich"
    assert result.evidence[0].locator.endswith("/person/enrich")
    assert fake_people == [("enrich", [URL])]

    PEOPLE["enrich"] = {"matches": [{"person_data": namesake}]}
    result = check(_employer_claim(), ctx)
    assert result.evidence == [] and "employer_found" not in result.observed


def test_unconfirmed_founder_is_never_looked_up(person_profile_fixture: dict, fake_people: list) -> None:
    ctx = _ctx(person_profile_fixture, founder=_founder(identity="unclear", signals=1))
    result = check(_employer_claim(), ctx)
    assert result.observed["identity"] == "unclear" and result.observed["identity_signals"] == 1
    assert result.evidence == [] and fake_people == []


def test_founder_found_by_search_uses_search_record(person_profile_fixture: dict, fake_people: list) -> None:
    ctx = _ctx(person_profile_fixture, founder=_founder(profile_url=None))
    result = check(_employer_claim(), ctx)
    assert fake_people == [("search", ("Priya Sharma", "co-test"))]
    assert result.observed["employer_found"] is True
    assert result.evidence[0].locator.endswith("/person/search")


def test_crustdata_role_shape_name_key(fake_people: list) -> None:
    record = {"crustdata_person_id": "p-1", "basic_profile": {"name": "Priya Sharma"},
              "experience": {"employment_details": {"current": [], "past": [
                  {"name": "Flipkart", "title": "Director, Engineering", "crustdata_company_id": 42,
                   "start_date": "2016-04-01", "end_date": "2019-03-01"}]}}}
    result = check(_employer_claim(), _ctx(record))
    assert result.observed["positions"] == [{"employer": "Flipkart", "title": "Director, Engineering",
                                             "start_date": "2016-04-01", "end_date": "2019-03-01"}]


def test_recorded_locus_founder_record(fake_people: list) -> None:
    """Live T36 probe (call-457fe7a8507b, 2026-11-22), contact fields dropped and trimmed."""
    import json
    from pathlib import Path

    from resolve import payloads
    from sources.crust import _parse_people

    raw = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "crustdata"
                      / "person_enrich_locus.json").read_text(encoding="utf-8"))
    payload, credits = _parse_people(1)(raw)
    assert credits == 1.0
    [cand] = payloads.person_candidates(payload)
    assert cand["id"] == "44441" and cand["name"] == "Nishith Rastogi"
    assert "7403" in cand["company_ids"]  # Locus' crustdata_company_id in the company record

    url = "https://www.linkedin.com/in/nishithrastogi/"
    ctx = _ctx(None, founder=_founder(person_id="44441", name="Nishith Rastogi", profile_url=url))
    PEOPLE["enrich"] = payload
    claim = Claim(id="c_f2", run_id="run_1", slide=2, type=ClaimType.FOUNDER_BACKGROUND,
                  quote="Our co-founder and CEO Nishith Rastogi previously worked at Amazon.",
                  subject="Nishith Rastogi", metric="past_employer", value="Amazon")
    result = check(claim, ctx)
    assert result.observed["employer_found"] is True
    assert result.observed["positions"] == [{"employer": "Amazon", "title": "Software Developer",
                                             "start_date": "2012-07-01", "end_date": "2014-07-01"}]


# ---- D19: record_date from the matched role's own dates ----

def _role_record(*roles: dict[str, Any]) -> dict[str, Any]:
    return {"crustdata_person_id": "p-1", "basic_profile": {"name": "Priya Sharma"},
            "updated_at": "2026-11-20T00:00:00Z",
            "experience": {"employment_details": {"current": [], "past": list(roles)}}}


def _flipkart(start: str | None, end: str | None) -> dict[str, Any]:
    return {"name": "Flipkart", "title": "VP Engineering", "start_date": start, "end_date": end}


@pytest.mark.parametrize(("role", "expected"), [
    (_flipkart("2015-01-01T00:00:00+00:00", "2020-01-01T00:00:00+00:00"), "2020-01-01"),  # ended before deck
    (_flipkart("2018-03-01", None), "2018-03-01"),                  # current role: its start date
    (_flipkart("2015-01-01", "2025-01-01"), "2015-01-01"),          # ended after the deck: start date
    (_flipkart("2024-09-01", None), "2024-09-01"),                  # started after the deck: earliest start
    (_flipkart(None, None), None),                                  # no dates
])
def test_record_date_from_matched_role(role: dict[str, Any], expected: str | None) -> None:
    result = check(_employer_claim(), _ctx(_role_record(role)))  # deck date 2024-05-15
    assert result.observed["employer_found"] is True
    assert result.observed["record_date"] == expected
    assert result.evidence[0].record_date == expected
    assert result.observed["record_date"] != "2026-11-20"  # never updated_at


def test_record_date_none_without_employer_match() -> None:
    record = _role_record({"name": "Amazon", "title": "SDE", "start_date": "2012-01-01", "end_date": "2014-01-01"})
    result = check(_employer_claim(), _ctx(record))
    assert result.observed["employer_found"] is False
    assert result.observed["record_date"] is None and result.evidence[0].record_date is None


def test_role_after_deck_date_is_not_comparable(rules: dict) -> None:
    claim = _employer_claim()
    result = check(claim, _ctx(_role_record(_flipkart("2024-09-01", None))))
    v = decide(claim, result, rules)
    assert v.label == VerdictLabel.NOT_COMPARABLE and v.reason_code == "record_after_as_of"


def test_record_date_uses_latest_date_over_all_matched_roles() -> None:
    record = _role_record(_flipkart("2012-01-01", "2014-01-01"), _flipkart("2016-01-01", "2019-06-30"))
    result = check(_employer_claim(), _ctx(record))
    assert result.observed["record_date"] == "2019-06-30"


def test_locus_fixture_amazon_claim_is_supported_through_engine() -> None:
    """D19 end to end on the recorded live record: Amazon 2012-07-01 to 2014-07-01, deck 2026-11-15."""
    import json
    from pathlib import Path

    from sources.crust import _parse_people

    raw = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "crustdata"
                      / "person_enrich_locus.json").read_text(encoding="utf-8"))
    payload, _ = _parse_people(1)(raw)
    ctx = make_ctx(run_id="run_1", company=None, deck_date="2026-11-15")
    ctx.entities["founders"] = [_founder(person_id="44441", name="Nishith Rastogi", signals=3,
                                         profile_url="https://www.linkedin.com/in/nishithrastogi/")]
    PEOPLE["enrich"] = payload
    claim = Claim(id="c_f2", run_id="run_1", slide=2, type=ClaimType.FOUNDER_BACKGROUND,
                  quote="Our co-founder and CEO Nishith Rastogi previously worked at Amazon.",
                  subject="Nishith Rastogi", metric="past_employer", value="Amazon")
    result = check(claim, ctx)
    assert result.observed["record_date"] == "2014-07-01"
    v = decide(claim, result, load_rules())
    assert v.label == VerdictLabel.SUPPORTED and v.reason_code == "employer_listed"
