"""Extract structured claims from slide text and verify quotes against slides.

Who calls it: core/runner.py (STAGES["extract"]), cli.py.
What it calls: extract/pdf.py, core/limits.py (ensure_within), core/ledger.py (record),
core/log.py (log_step, log_error), core/models.py (Claim, ClaimType, ClaimState, Provider),
core/config.py (rule), core/store.py (update_run_input).
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core import store
from core.config import rule
from core.ledger import record
from core.limits import ensure_within
from core.log import log_error, log_step
from core.models import (
    Claim,
    ClaimState,
    ClaimType,
    Provider,
    RunContext,
)
from extract.pdf import extract_pdf_slides

EXTRACTION_SYSTEM_PROMPT = """You are an expert investment diligence analyst.
Your job is to extract all factual claims from pitch deck slides into structured JSON.
For each claim, identify:
- slide: 1-based integer slide number where the claim appears
- quote: EXACT verbatim substring from that slide containing the claim (do NOT paraphrase or invent quotes)
- type: one of "founder_background", "prior_exit", "team_size", "team_growth", "funding", "company_fact", "customer", "hiring", "traction", "market_size", "competition"
- subject: company name, founder name, or entity the claim is about
- metric: the specific metric (e.g. "headcount" for team_size; "total_raised", "round_amount", or "investor" for funding; "past_employer", "title", "tenure_years" for founder_background)
- value: the numeric value or string in absolute major units (e.g. 5000000 not "5M", 50 not "fifty")
- unit: ISO currency code ("USD", "INR") or "people" for headcount, or null
- as_of: date or time period mentioned (e.g. "2023", "2024-06-30") or null

Return ONLY a JSON array of claim objects, with no markdown code fences or conversational text.
"""


def verify_claim_quote(quote: str, slide_text: str) -> bool:
    """Return True if quote appears verbatim (allowing normalized whitespace) in slide_text."""
    if not quote or not slide_text:
        return False
    if quote in slide_text:
        return True
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
            log_step(run_id, claim.id, "verify_quote", "ok", slide=claim.slide)
        else:
            log_step(
                run_id,
                claim.id,
                "verify_quote",
                "rejected",
                slide=claim.slide,
                quote=claim.quote,
                reason="quote_not_found_on_slide",
            )
    return verified


def _parse_numeric_value(raw_val: Any) -> float | str | None:
    """Parse absolute major units from numbers or strings like '5M', '100k', '$2.5M'."""
    if raw_val is None:
        return None
    if isinstance(raw_val, (int, float)):
        return float(raw_val)

    s = str(raw_val).strip().replace(",", "")
    s = re.sub(r"^[\$€£₹]\s*", "", s)

    multiplier = 1.0
    if re.search(r"bn?|billion", s, re.IGNORECASE):
        multiplier = 1e9
        s = re.sub(r"bn?|billion", "", s, flags=re.IGNORECASE).strip()
    elif re.search(r"m|million", s, re.IGNORECASE):
        multiplier = 1e6
        s = re.sub(r"m|million", "", s, flags=re.IGNORECASE).strip()
    elif re.search(r"k|thousand", s, re.IGNORECASE):
        multiplier = 1e3
        s = re.sub(r"k|thousand", "", s, flags=re.IGNORECASE).strip()
    elif re.search(r"cr|crore", s, re.IGNORECASE):
        multiplier = 1e7
        s = re.sub(r"cr|crore", "", s, flags=re.IGNORECASE).strip()
    elif re.search(r"l|lakh", s, re.IGNORECASE):
        multiplier = 1e5
        s = re.sub(r"l|lakh", "", s, flags=re.IGNORECASE).strip()

    try:
        return float(s) * multiplier
    except ValueError:
        return str(raw_val)


def _parse_claims_json(raw_json: str, run_id: str) -> list[Claim]:
    """Parse raw LLM JSON output into a list of Claim models."""
    cleaned = raw_json.strip()
    if cleaned.startswith("```"):
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
        raw_type = str(item.get("type", "")).lower().strip()
        if raw_type not in valid_types:
            log_step(run_id, None, "extract_claim", "dropped", reason="unknown_type", type=raw_type)
            continue
        claim_type = valid_types[raw_type]

        quote = str(item.get("quote", "")).strip()
        if not quote:
            continue

        raw_slide = item.get("slide")
        if not isinstance(raw_slide, int):
            try:
                slide_num = int(raw_slide)
            except (ValueError, TypeError):
                log_step(run_id, None, "extract_claim", "dropped", reason="invalid_slide", slide=raw_slide)
                continue
        else:
            slide_num = raw_slide

        subject = str(item.get("subject", "")).strip()
        metric = item.get("metric")
        if metric is not None:
            metric = str(metric).strip()
        elif claim_type == ClaimType.TEAM_SIZE:
            metric = "headcount"

        raw_val = item.get("value")
        parsed_val = _parse_numeric_value(raw_val)

        unit = item.get("unit")
        if unit is not None:
            unit = str(unit).strip()
        elif claim_type == ClaimType.TEAM_SIZE:
            unit = "people"

        as_of = item.get("as_of")
        if as_of is not None:
            as_of = str(as_of).strip()

        claim = Claim(
            id=f"tmp-{uuid.uuid4().hex[:8]}",
            run_id=run_id,
            slide=slide_num,
            quote=quote,
            type=claim_type,
            subject=subject,
            metric=metric,
            value=parsed_val,
            unit=unit,
            as_of=as_of,
            state=ClaimState.PENDING,
        )
        claims.append(claim)

    return claims


def _default_llm_call(prompt: str, model: str | None = None, timeout_s: float = 30.0) -> tuple[str, str, int, int]:
    """Execute live LLM call using available credentials (Gemini or OpenAI).

    Returns:
        tuple[content, model_used, tokens_in, tokens_out]
    """
    import requests

    # gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    # if gemini_key:
    #     model_name = model or "gemini-2.5-flash"
    #     # Key sent in header only, never in URL
    #     url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
    #     headers = {"x-goog-api-key": gemini_key, "Content-Type": "application/json"}
    #     payload = {
    #         "contents": [{"parts": [{"text": prompt}]}],
    #         "generationConfig": {"response_mime_type": "application/json"},
    #     }
    #     try:
    #         resp = requests.post(url, headers=headers, json=payload, timeout=timeout_s)
    #         resp.raise_for_status()
    #     except requests.exceptions.Timeout as exc:
    #         raise TimeoutError(f"Gemini API call timed out after {timeout_s}s") from exc
    #     except Exception as exc:
    #         # Strip any potential sensitive details from exception string
    #         clean_msg = re.sub(r"key=[^\s&]+", "key=REDACTED", str(exc))
    #         raise RuntimeError(f"Gemini API call failed: {clean_msg}") from exc

    #     res_data = resp.json()
    #     content = res_data["candidates"][0]["content"]["parts"][0]["text"]
    #     usage = res_data.get("usageMetadata", {})
    #     tokens_in = usage.get("promptTokenCount", len(prompt) // 4)
    #     tokens_out = usage.get("candidatesTokenCount", len(content) // 4)
    #     return content, model_name, tokens_in, tokens_out

    if openai_key:
        model_name = model or "gpt-4o-mini"
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout_s)
            resp.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise TimeoutError(f"OpenAI API call timed out after {timeout_s}s") from exc
        except Exception as exc:
            clean_msg = re.sub(r"Bearer\s+[^\s]+", "Bearer REDACTED", str(exc))
            raise RuntimeError(f"OpenAI API call failed: {clean_msg}") from exc

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
    ctx: RunContext,
    model: str | None = None,
    llm_caller: Callable[..., tuple[str, str, int, int]] | None = None,
) -> list[Claim]:
    """Extract structured claims from slides using an LLM, verify quotes, and record ledger rows."""
    run_id = ctx.run.id
    if not slides:
        log_step(run_id, None, "extract_claims", "empty_input", slide_count=0)
        return []

    slide_sections = []
    for s_num in sorted(slides.keys()):
        slide_sections.append(f"--- SLIDE {s_num} ---\n{slides[s_num]}")
    deck_text = "\n\n".join(slide_sections)

    prompt = (
        f"{EXTRACTION_SYSTEM_PROMPT}\n\n"
        f"Extract all factual claims from the following pitch deck slides:\n\n{deck_text}"
    )

    t0 = time.perf_counter()
    raw_content = ""
    model_name = model or "llm-extract"
    tokens_in = 0
    tokens_out = 0
    ok = False
    error: str | None = None

    # Call core.limits.ensure_within(ctx) right before external call
    ensure_within(ctx)

    timeout_s = 30.0
    try:
        timeout_s = float(rule(ctx.rules, "limits.per_call_timeout_s"))
    except Exception:
        pass

    try:
        if llm_caller:
            raw_content, model_name, tokens_in, tokens_out = llm_caller(prompt, model)
        else:
            raw_content, model_name, tokens_in, tokens_out = _default_llm_call(prompt, model, timeout_s=timeout_s)
        ok = True
    except Exception as exc:
        error = str(exc)
        log_error(run_id, None, "extract.claims", error)
        raise RuntimeError(f"LLM extraction failed: {exc}") from exc
    finally:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        record(
            ctx.conn,
            ctx.rules,
            run_id,
            Provider.LLM,
            model_name,
            duration_ms=duration_ms,
            ok=ok,
            error=error,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )

    candidate_claims = _parse_claims_json(raw_content, run_id=run_id)
    verified_claims = verify_claim_quotes(candidate_claims, slides=slides, run_id=run_id)

    log_step(
        run_id,
        None,
        "extract_claims_finished",
        "ok",
        candidate_count=len(candidate_claims),
        verified_count=len(verified_claims),
        dropped_count=len(candidate_claims) - len(verified_claims),
    )

    return verified_claims


def _extract_pdf_creation_date(pdf_path: Path) -> str | None:
    """Read creation date from PDF metadata if available."""
    try:
        import pypdf
        reader = pypdf.PdfReader(str(pdf_path))
        meta = reader.metadata
        if meta and meta.creation_date:
            return meta.creation_date.strftime("%Y-%m-%d")
    except Exception:
        pass
    return None


def run(
    ctx: RunContext,
    model: str | None = None,
    llm_caller: Callable[..., tuple[str, str, int, int]] | None = None,
) -> list[Claim]:
    """Runner stage entry point (D7): extract.claims:run(ctx: RunContext) -> list[Claim]."""
    deck_path = Path(ctx.run.input.deck_path)
    if not deck_path.is_file() or deck_path.stat().st_size < 100:
        from core.runner import StageMissing
        raise StageMissing("extract.claims is not built yet")

    # If deck_date was not given, fall back to PDF metadata (Item 14)
    if ctx.run.input.deck_date is None:
        meta_date = _extract_pdf_creation_date(deck_path)
        if meta_date:
            store.update_run_input(ctx.conn, ctx.run.id, meta_date, "pdf_metadata")
            ctx.run.input.deck_date = meta_date
            ctx.run.input.deck_date_source = "pdf_metadata"
        else:
            store.update_run_input(ctx.conn, ctx.run.id, None, "missing")
            ctx.run.input.deck_date_source = "missing"

    slides = extract_pdf_slides(deck_path, run_id=ctx.run.id)
    return extract_claims(slides, ctx, model=model, llm_caller=llm_caller)
