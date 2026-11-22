"""Tests for resolve/entities.py and resolve/names.py: two-signal rule, namesakes, URLs, JSON safety (T10).

Called by: pytest. Calls: resolve.entities with a fake sources.crust and recorded-style payloads (tests only).
"""

import json

import pytest

from core.limits import LimitExceeded
from core.models import Claim, ClaimType, HeldReason
from resolve.entities import run
from resolve.names import (company_names_match, find_founder, normalize_domain, normalize_url,
                           person_names_match)
from resolve_fakes import company, company_payload, make_ctx, people_payload, person, search_payload

CT = ClaimType


def claim(ctype, subject, n=1):
    return Claim(id=f"c{n}", run_id="run_1", slide=1, quote="q", type=ctype, subject=subject)


DECK = [claim(CT.TEAM_SIZE, "Acme Technologies", 1), claim(CT.FOUNDER_BACKGROUND, "Priya Sharma", 2)]
ACME = company(founders=[("p-1", "Priya Sharma")])


# ------------------------------------------------------------------ names

def test_name_helpers():
    assert company_names_match("Acme Technologies Pvt. Ltd.", "ACME technologies")
    assert not company_names_match("Acme Labs", "Acme Technologies")
    assert not company_names_match("", "")
    assert person_names_match("Sharma, Priya", "priya SHARMA")
    assert person_names_match("José Álvarez", "Jose Alvarez")
    assert not person_names_match("Priya K Sharma", "Priya Sharma")   # near miss is not a signal
    assert not person_names_match("Priya", "Priya")                    # one token is too weak
    assert normalize_domain("https://www.Acme.example/about?x=1") == "acme.example"
    assert normalize_url("https://www.linkedin.com/in/priya/?utm=1") == "linkedin.com/in/priya"


# ------------------------------------------------------------------ company

def test_company_confirmed_on_domain_plus_name(rules, crust):
    crust.company_result = company_payload(company())
    out = run(make_ctx(rules), [claim(CT.TEAM_SIZE, "Acme Technologies")])
    c = out["company"]
    assert (c["id"], c["identity"], c["identity_signals"], c["signals"]) == ("co-1", "confirmed", 2, ["domain", "name"])
    assert c["confidence"] == "medium" and c["call_id"] == "call-company"      # 2 signals = min_signals


def test_company_three_signals_is_high_confidence(rules, crust):
    crust.company_result = company_payload(ACME)
    c = run(make_ctx(rules), DECK)["company"]
    assert (c["identity"], c["identity_signals"], c["confidence"]) == ("confirmed", 3, "high")


def test_company_domain_plus_founder_is_enough(rules, crust):
    crust.company_result = company_payload(company(name="Totally Different Name", founders=[("p-1", "Priya Sharma")]))
    c = run(make_ctx(rules), DECK)["company"]
    assert (c["identity"], c["signals"]) == ("confirmed", ["domain", "founder"])


def test_company_domain_only_is_unclear(rules, crust):
    crust.company_result = company_payload(company(name="Unrelated Co"))
    c = run(make_ctx(rules), DECK)["company"]
    assert (c["identity"], c["identity_signals"], c["confidence"], c["reason"]) == ("unclear", 1, "low", "too_few_signals")


def test_company_not_found_cases(rules, crust):
    for payload, reason in [(None, "no_match"), ({"matches": []}, "no_match"),
                            (company_payload(company(domain="other.example")), "domain_mismatch")]:
        crust.company_result = payload
        c = run(make_ctx(rules), DECK)["company"]
        assert (c["identity"], c["identity_signals"], c["reason"]) == ("not_found", 0, reason)


def test_company_two_candidates_is_unclear(rules, crust):
    crust.company_result = company_payload(company("co-1"), company("co-2"))
    c = run(make_ctx(rules), DECK)["company"]
    assert (c["identity"], c["id"], c["reason"]) == ("unclear", None, "multiple_candidates")


def test_company_without_id_is_unclear(rules, crust):
    rec = company(); del rec["crustdata_company_id"]
    crust.company_result = company_payload(rec)
    assert run(make_ctx(rules), DECK)["company"]["reason"] == "no_company_id"


def test_min_signals_comes_from_rules_yaml(rules, crust):
    crust.company_result = company_payload(company())
    rules["identity"]["min_signals"] = 3
    c = run(make_ctx(rules), [claim(CT.TEAM_SIZE, "Acme Technologies")])["company"]
    assert (c["identity"], c["identity_signals"]) == ("unclear", 2)


def test_alias_domain_counts(rules, crust):
    crust.company_result = company_payload(company(domain="acme.com", all_domains=["acme.com", "acme.example"]))
    assert run(make_ctx(rules), DECK)["company"]["identity"] == "confirmed"


# ------------------------------------------------------------------ founders by name + company

def test_founder_by_search_confirmed(rules, crust):
    crust.company_result = company_payload(ACME)
    crust.search_results["Priya Sharma"] = search_payload(person("p-1", "Priya Sharma", companies=[("co-1", "Acme")]))
    f = run(make_ctx(rules), DECK)["founders"][0]
    assert (f["name"], f["id"], f["identity"]) == ("Priya Sharma", "p-1", "confirmed")
    assert f["signals"] == ["name", "employer", "company_founder_list"] and f["confidence"] == "high"
    assert ("search_people", ("Priya Sharma", "co-1")) in crust.calls


def test_namesake_at_another_company_is_unclear(rules, crust):
    crust.company_result = company_payload(company())
    crust.search_results["Priya Sharma"] = search_payload(
        person("p-9", "Priya Sharma", companies=[("co-77", "Other Corp")]))
    f = run(make_ctx(rules), DECK)["founders"][0]
    assert (f["identity"], f["id"], f["identity_signals"], f["reason"]) == ("unclear", None, 1, "namesake_or_weak_match")


def test_namesake_is_ignored_when_the_right_person_is_present(rules, crust):
    crust.company_result = company_payload(company())
    crust.search_results["Priya Sharma"] = search_payload(
        person("p-9", "Priya Sharma", companies=[("co-77", "Other Corp")]),
        person("p-1", "Priya Sharma", companies=[("co-1", "Acme")]))
    f = run(make_ctx(rules), DECK)["founders"][0]
    assert (f["identity"], f["id"]) == ("confirmed", "p-1")


def test_two_qualifying_namesakes_is_unclear(rules, crust):
    crust.company_result = company_payload(company())
    crust.search_results["Priya Sharma"] = search_payload(
        person("p-1", "Priya Sharma", companies=[("co-1", "Acme")]),
        person("p-2", "Priya Sharma", companies=[("co-1", "Acme")]))
    f = run(make_ctx(rules), DECK)["founders"][0]
    assert (f["identity"], f["id"], f["reason"]) == ("unclear", None, "multiple_candidates")


def test_search_returns_nothing_relevant(rules, crust):
    crust.company_result = company_payload(company())
    for payload, reason in [(None, "no_candidates"), (search_payload(person("p-5", "Someone Else")), "no_name_match")]:
        crust.search_results["Priya Sharma"] = payload
        f = run(make_ctx(rules), DECK)["founders"][0]
        assert (f["identity"], f["identity_signals"], f["reason"]) == ("not_found", 0, reason)


def test_unconfirmed_company_means_no_founder_search(rules, crust):
    crust.company_result = company_payload(company(name="Unrelated Co"))
    f = run(make_ctx(rules), DECK)["founders"][0]
    assert (f["identity"], f["reason"]) == ("unclear", "company_unresolved")
    assert crust.names() == ["get_company"]


def test_incomplete_founder_name_is_not_searched(rules, crust):
    crust.company_result = company_payload(ACME)
    out = run(make_ctx(rules), [claim(CT.TEAM_SIZE, "Acme Technologies"), claim(CT.FOUNDER_BACKGROUND, "Priya", 2)])
    assert out["founders"][0]["reason"] == "name_incomplete" and crust.names() == ["get_company"]


def test_no_founders_no_people_calls(rules, crust):
    crust.company_result = company_payload(company())
    out = run(make_ctx(rules), [claim(CT.TEAM_SIZE, "Acme Technologies")])
    assert out["founders"] == [] and crust.names() == ["get_company"]


def test_each_deck_founder_once(rules, crust):
    crust.company_result = company_payload(company())
    claims = [claim(CT.FOUNDER_BACKGROUND, "Priya Sharma", 1), claim(CT.PRIOR_EXIT, "Priya Sharma", 2),
              claim(CT.FOUNDER_BACKGROUND, "Rahul Mehta", 3)]
    out = run(make_ctx(rules), claims)
    assert [f["name"] for f in out["founders"]] == ["Priya Sharma", "Rahul Mehta"]


# ------------------------------------------------------------------ founders by profile URL

URL = "https://www.linkedin.com/in/priya-sharma/"


def test_founder_by_url_with_deck_name(rules, crust):
    crust.company_result = company_payload(ACME)
    crust.people_result = people_payload(person("p-1", "Priya Sharma", url=URL, companies=[("co-1", "Acme")]))
    out = run(make_ctx(rules, founder_urls=[URL]), DECK)
    f = out["founders"][0]
    assert (f["identity"], f["id"], f["name"], f["profile_url"]) == ("confirmed", "p-1", "Priya Sharma", URL)
    assert f["signals"][0] == "profile_url" and len(out["founders"]) == 1      # not searched a second time
    assert "search_people" not in crust.names()


def test_founder_url_only_needs_employer_link(rules, crust):
    crust.company_result = company_payload(company())
    crust.people_result = people_payload(person("p-1", "Priya Sharma", url=URL, companies=[("co-1", "Acme")]))
    f = run(make_ctx(rules, founder_urls=[URL]), [claim(CT.TEAM_SIZE, "Acme Technologies")])["founders"][0]
    assert (f["identity"], f["name"], f["signals"]) == ("confirmed", None, ["profile_url", "employer"])


def test_founder_url_alone_is_one_signal(rules, crust):
    crust.company_result = company_payload(company())
    crust.people_result = people_payload(person("p-9", "Priya Sharma", url=URL, companies=[("co-77", "Other")]))
    f = run(make_ctx(rules, founder_urls=[URL]), [claim(CT.TEAM_SIZE, "Acme Technologies")])["founders"][0]
    assert (f["identity"], f["identity_signals"], f["reason"]) == ("unclear", 1, "too_few_signals")


def test_founder_url_not_returned(rules, crust):
    crust.company_result = company_payload(company())
    crust.people_result = people_payload()
    f = run(make_ctx(rules, founder_urls=[URL]), [claim(CT.TEAM_SIZE, "Acme Technologies")])["founders"][0]
    assert (f["identity"], f["reason"]) == ("not_found", "url_not_returned")


def test_urls_are_fetched_in_one_call(rules, crust):
    crust.company_result = company_payload(company())
    crust.people_result = people_payload()
    run(make_ctx(rules, founder_urls=[URL, URL, "https://linkedin.com/in/other"]), [])
    assert crust.calls[1] == ("get_people", [URL, "https://linkedin.com/in/other"])


# ------------------------------------------------------------------ output safety and runner contract

def test_output_is_json_safe_and_has_no_payload_or_contact_fields(rules, crust):
    crust.company_result = company_payload(ACME)
    crust.search_results["Priya Sharma"] = search_payload(
        person("p-1", "Priya Sharma", companies=[("co-1", "Acme")], email="priya@secret.example"))
    out = run(make_ctx(rules), DECK)
    text = json.dumps(out)
    assert "secret.example" not in text and "email" not in text and "contact" not in text
    assert set(out) == {"company", "founders"}
    assert set(out["company"]) == {"id", "identity", "identity_signals", "confidence", "signals", "reason", "call_id"}


def test_source_errors_propagate_not_unclear(rules, crust):
    crust.raise_on["get_company"] = LimitExceeded(HeldReason.BUDGET, "cost")
    with pytest.raises(LimitExceeded):
        run(make_ctx(rules), DECK)
    crust.raise_on["get_company"] = TimeoutError("slow")
    with pytest.raises(TimeoutError):
        run(make_ctx(rules), DECK)


def test_missing_sources_module_raises(rules, monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "sources.crust", None)       # import fails like a module that is not built yet
    with pytest.raises(ImportError):
        run(make_ctx(rules), DECK)


def test_checker_helper_reads_exactly_these_keys(rules, crust):
    from checkers._common import company_identity
    crust.company_result = company_payload(ACME)
    out = run(make_ctx(rules), DECK)
    ctx = make_ctx(rules)
    ctx.entities = out
    assert company_identity(ctx) == {"identity": "confirmed", "identity_signals": 3}


def test_find_founder_helper(rules, crust):
    crust.company_result = company_payload(company())
    crust.search_results["Priya Sharma"] = search_payload(person("p-1", "Priya Sharma", companies=[("co-1", "Acme")]))
    out = run(make_ctx(rules), DECK)
    assert find_founder(out, "Sharma, Priya")["id"] == "p-1"
    assert find_founder(out, "Nobody Here") is None and find_founder({}, "Priya Sharma") is None


def test_placeholder_founder_urls_are_never_sent(rules, crust):
    """'NA', '-' or 'none' typed into the founder URL box are not URLs: the person lookup is
    not called (Crustdata answered HTTP 400 and the run stopped at extracted)."""
    crust.company_result = company_payload(company())
    out = run(make_ctx(rules, founder_urls=["NA", "-", "none", ""]), [claim(CT.TEAM_SIZE, "Acme Technologies")])
    assert "get_people" not in crust.names()
    assert out["founders"] == []
