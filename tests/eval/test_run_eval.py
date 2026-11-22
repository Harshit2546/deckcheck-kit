"""Tests for tests/eval/run_eval.py: the comparison rules, the report, and the offline replay of Deck A.

Called by: pytest. Calls: run_eval (offline mode only; --live is never run in tests because it spends credits).
"""

import run_eval
from run_eval import compare, evaluate, main, match_actual, render

KEY = {"slide": 2, "quote": "Locus has a team of 350 people.", "expected_verdict": "SUPPORTED",
       "expected_reason_code": "within_tolerance"}


def actual(verdict="SUPPORTED", reason="within_tolerance", slide=2, quote="Locus has a team of 350 people."):
    return {"slide": slide, "quote": quote, "verdict": verdict, "reason_code": reason, "confidence": "high"}


def test_compare_needs_both_verdict_and_reason():
    assert compare(KEY, actual()) == "PASS"
    assert compare(KEY, actual(reason="other")) == "FAIL"
    assert compare(KEY, actual(verdict="CONTRADICTED")) == "FAIL"
    assert compare(KEY, None) == "FAIL"


def test_compare_tbd_is_skip_even_without_a_verdict():
    tbd = {**KEY, "expected_verdict": "TBD", "expected_reason_code": None}
    assert compare(tbd, None) == "SKIP" and compare(tbd, actual()) == "SKIP"


def test_compare_null_expected_reason_accepts_any_reason():
    assert compare({**KEY, "expected_reason_code": None}, actual(reason="whatever")) == "PASS"


def test_match_actual_uses_slide_and_whitespace_insensitive_quote():
    a = actual(quote="Locus has a  team of\n350 people.")
    assert match_actual(KEY, [a]) is a
    assert match_actual(KEY, [actual(slide=3)]) is None
    assert match_actual(KEY, [actual(quote="different")]) is None


def test_render_counts_and_accuracy_exclude_skips():
    rows = [{**KEY, "actual": actual(), "status": "PASS"},
            {**KEY, "slide": 3, "actual": None, "status": "FAIL"},
            {**KEY, "slide": 8, "expected_verdict": "TBD", "actual": None, "status": "SKIP"}]
    text = render("a", rows, {"state": "done", "error": None, "problems": []}, live=False)
    assert "Summary: 1 PASS, 1 FAIL, 1 SKIP; accuracy 50% of 2 scored claims" in text
    assert "no verdict" in text and "offline replay" in text


def test_offline_replay_of_deck_a_has_one_row_per_key_row_and_real_quotes():
    rows, info = evaluate("a")
    assert [r["slide"] for r in rows] == [2, 3, 4, 5, 6, 7, 8]
    assert info["problems"] == [] and info["state"] == "done"


def test_offline_replay_regression_guard_for_slides_2_and_5():
    rows, _ = evaluate("a")
    by_slide = {r["slide"]: r for r in rows}
    assert by_slide[2]["status"] == "PASS" and by_slide[5]["status"] == "PASS"
    assert by_slide[8]["status"] == "SKIP"


def test_main_exit_code_is_one_when_a_claim_fails(capsys):
    code = main(["--deck", "a"])
    out = capsys.readouterr().out
    assert code in (0, 1) and "Summary:" in out
    assert code == (1 if "FAIL" in out.split("Summary:")[1].split("\n")[0].replace("0 FAIL", "") else 0)


def test_missing_deck_is_a_harness_error(capsys):
    assert main(["--deck", "zz"]) == 2
    assert "eval harness error" in capsys.readouterr().err


def test_offline_replay_never_calls_the_live_web(monkeypatch):
    # A key in the environment must not turn the offline eval into a paid run.
    import requests
    monkeypatch.setenv("CRUSTDATA_API_KEY", "test-key-not-real")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")

    def no_network(*_a, **_k):
        raise AssertionError("offline eval made a network call")
    monkeypatch.setattr(requests, "post", no_network)
    monkeypatch.setattr(requests, "get", no_network)
    monkeypatch.setattr(requests.Session, "request", no_network)
    rows, info = run_eval.run_offline("a")
    assert len(info["blocked_web_calls"]) == 2           # slides 6 and 7 reached the block, nothing else
    held = {r["slide"]: r["reason_code"] for r in rows if r["verdict"] == "HELD"}
    assert held == {6: "error", 7: "error"}


def test_web_functions_are_restored_after_the_replay():
    import extract.quotes as quotes
    import sources.web as web
    before = (web.search, web.fetch, quotes.pick_quote)
    evaluate("a")
    assert (web.search, web.fetch, quotes.pick_quote) == before


def test_get_company_is_restored_after_the_replay():
    import sources.crust as crust
    before = crust.get_company
    evaluate("a")
    assert crust.get_company is before
