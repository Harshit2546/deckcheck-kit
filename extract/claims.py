"""Extract structured claims from slide text and verify quotes against slides.

Who calls it: core/runner.py, cli.py.
What it calls: requests (LLM API), core/models.py (Claim, LedgerEntry), core/config.py, core/log.py.
Extracts structured claims, drops any claim whose quote does not appear on its slide,
and writes a ledger row for every LLM call.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable
from typing import Any

from core.config import load_rules
from core.log import log_step
from core.models import (
    Claim,
    ClaimState,
    ClaimType,
    LedgerEntry,
    Provider,
    Rules,
    new_id,
)
from core.store import Store

EXTRACTION_SYSTEM_PROMPT = """You are an expert investment diligence analyst.
Your job is to extract all factual claims from pitch deck slides into structured JSON.
For each claim, identify:
- slide: 1-based integer slide number where the claim appears
- quote: EXACT verbatim substring from that slide containing the claim (do NOT paraphrase or invent quotes)
- type: one of "founder_background", "prior_exit", "team_size", "team_growth", "funding", "company_fact", "customer", "hiring", "traction", "market_size", "competition"
- subject: company name, founder name, or entity the claim is about
- metric: the specific metric (e.g. "headcount", "round_amount", "arr", "tam")
- value: the numeric value or string stated in the claim (e.g. 50, 5000000, "150%")
- unit: unit if applicable (e.g. "employees", "USD", "INR", "%")
- as_of: date or time period mentioned (e.g. "2023", "Q3 2024", "2024-06-30") or null

Return ONLY a JSON array of claim objects, with no markdown code fences or conversational text.
"""


def verify_claim_quote(quote: str, slide_text: str) -> bool:
    """Return True if quote appears verbatim (allowing normalized whitespace) in slide_text."""
    if not quote or not slide_text:
        return False
    if quote in slide_text:
        return True
    # Normalize internal whitespace/newlines
    norm_quote = " ".join(quote.split())
    norm_text = " ".join(slide_text.split())
    return norm_quote in norm_text


def verify_claim_quotes(
    claims: list[Claim],
    slides: dict[int, str],
    run_id: str | None = None,
) -> list[Claim]:
    """Filter claims to only those whose quote appears on their designated slide.

    Any claim with an invented or missing quote is dropped and logged.
    """
    verified: list[Claim] = []
    for claim in claims:
        slide_text = slides.get(claim.slide, "")
        if verify_claim_quote(claim.quote, slide_text):
            verified.append(claim)
            log_step(run_id, "verify_quote", "ok", claim_id=claim.id, slide=claim.slide)
        else:
            log_step(
                run_id,
                "verify_quote",
                "rejected",
                claim_id=claim.id,
                slide=claim.slide,
                quote=claim.quote,
                reason="quote_not_found_on_slide",
            )
    return verified


def _parse_claims_json(raw_json: str, run_id: str) -> list[Claim]:
    """Parse raw LLM JSON output into a list of Claim models."""
    cleaned = raw_json.strip()
    if cleaned.startswith("```"):
        # Strip markdown fences if present
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        data = json.loads(cleaned)
    except Exception as exc:
        raise ValueError(f"Failed to parse LLM JSON response: {exc}\nRaw: {raw_json[:200]}") from exc

    if isinstance(data, dict) and "claims" in data:
        data = data["claims"]

    if not isinstance(data, list):
        raise ValueError(f"Expected list of claims from LLM, got {type(data).__name__}")

    claims: list[Claim] = []
    valid_types = {t.value: t for t in ClaimType}

    for item in data:
        if not isinstance(item, dict):
            continue
        raw_type = str(item.get("type", "company_fact")).lower().strip()
        claim_type = valid_types.get(raw_type, ClaimType.COMPANY_FACT)

        quote = str(item.get("quote", "")).strip()
        if not quote:
            continue

        slide_num = int(item.get("slide", 1))
        subject = str(item.get("subject", "")).strip()
        metric = item.get("metric")
        if metric is not None:
            metric = str(metric).strip()
        value = item.get("value")
        unit = item.get("unit")
        if unit is not None:
            unit = str(unit).strip()
        as_of = item.get("as_of")
        if as_of is not None:
            as_of = str(as_of).strip()

        claim = Claim(
            run_id=run_id,
            slide=slide_num,
            quote=quote,
            type=claim_type,
            subject=subject,
            metric=metric,
            value=value,
            unit=unit,
            as_of=as_of,
            state=ClaimState.PENDING,
        )
        claims.append(claim)

    return claims


def _default_llm_call(prompt: str, model: str | None = None) -> tuple[str, str, int, int]:
    """Execute live LLM call using available credentials (Gemini or OpenAI).

    Returns:
        tuple[content, model_used, tokens_in, tokens_out]
    """
    import requests

    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if gemini_key:
        model_name = model or "gemini-2.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json"},
        }
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        res_data = resp.json()
        content = res_data["candidates"][0]["content"]["parts"][0]["text"]
        usage = res_data.get("usageMetadata", {})
        tokens_in = usage.get("promptTokenCount", len(prompt) // 4)
        tokens_out = usage.get("candidatesTokenCount", len(content) // 4)
        return content, model_name, tokens_in, tokens_out

    if openai_key:
        model_name = model or "gpt-4o-mini"
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {openai_key}"}
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        res_data = resp.json()
        content = res_data["choices"][0]["message"]["content"]
        usage = res_data.get("usage", {})
        tokens_in = usage.get("prompt_tokens", len(prompt) // 4)
        tokens_out = usage.get("completion_tokens", len(content) // 4)
        return content, model_name, tokens_in, tokens_out

    raise RuntimeError(
        "No LLM credentials configured. Set GEMINI_API_KEY or OPENAI_API_KEY in environment."
    )


def extract_claims(
    slides: dict[int, str],
    run_id: str,
    store: Store | None = None,
    rules: Rules | None = None,
    model: str | None = None,
    llm_caller: Callable[[str, str | None], tuple[str, str, int, int]] | None = None,
) -> list[Claim]:
    """Extract structured claims from slides using an LLM, verify quotes, and record ledger rows.

    Args:
        slides: Dict mapping 1-based slide numbers to slide text.
        run_id: Active run ID.
        store: SQLite Store instance to record ledger rows (and optionally save claims).
        rules: Active configuration rules for calculating token pricing.
        model: Optional model identifier override.
        llm_caller: Optional custom caller function returning (content, model_name, tokens_in, tokens_out).
                    Defaults to live API call (_default_llm_call).

    Returns:
        list[Claim]: Verified claims whose quotes strictly match their respective slides.
    """
    if not slides:
        log_step(run_id, "extract_claims", "empty_input", slide_count=0)
        return []

    if rules is None:
        try:
            rules = load_rules()
        except Exception:
            rules = None

    pricing_in = rules.pricing.inr_per_1k_tokens_in if rules else 0.25
    pricing_out = rules.pricing.inr_per_1k_tokens_out if rules else 1.25

    # Prepare prompt with slides text
    slide_sections = []
    for s_num in sorted(slides.keys()):
        slide_sections.append(f"--- SLIDE {s_num} ---\n{slides[s_num]}")
    deck_text = "\n\n".join(slide_sections)

    prompt = (
        f"{EXTRACTION_SYSTEM_PROMPT}\n\n"
        f"Extract all factual claims from the following pitch deck slides:\n\n{deck_text}"
    )

    caller = llm_caller or _default_llm_call
    t0 = time.perf_counter()
    raw_content = ""
    model_name = model or "llm-extract"
    tokens_in = 0
    tokens_out = 0
    call_ok = True
    error_msg: str | None = None

    try:
        raw_content, model_name, tokens_in, tokens_out = caller(prompt, model)
    except Exception as exc:
        call_ok = False
        error_msg = str(exc)
        log_step(run_id, "llm_extract_claims", "error", error=error_msg, model=model_name)
    finally:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        cost_inr = round(
            (tokens_in / 1000.0) * pricing_in + (tokens_out / 1000.0) * pricing_out, 4
        )

        entry = LedgerEntry(
            id=new_id(),
            run_id=run_id,
            provider=Provider.LLM,
            endpoint_or_model=model_name,
            credits=0.0,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_inr=cost_inr,
            duration_ms=duration_ms,
            ok=call_ok,
            error=error_msg,
        )

        if store is not None:
            store.add_ledger(entry)

        log_step(
            run_id,
            "llm_extract_claims",
            "ok" if call_ok else "error",
            model=model_name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_inr=cost_inr,
            duration_ms=duration_ms,
        )

    if not call_ok:
        raise RuntimeError(f"LLM extraction failed: {error_msg}")

    # Parse JSON into candidate claims
    candidate_claims = _parse_claims_json(raw_content, run_id=run_id)

    # Verify that every quote appears on its slide (drop any that do not)
    verified_claims = verify_claim_quotes(candidate_claims, slides=slides, run_id=run_id)

    log_step(
        run_id,
        "extract_claims_finished",
        "ok",
        candidate_count=len(candidate_claims),
        verified_count=len(verified_claims),
        dropped_count=len(candidate_claims) - len(verified_claims),
    )

    return verified_claims
