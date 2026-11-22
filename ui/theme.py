"""DeckCheck UI look: CSS, verdict colours and small HTML pieces (slide strip, verdict mark, quotes).

Called by: ui/app.py. Calls: nothing (pure strings).
Every piece of deck, LLM or web text that goes into HTML here passes through html.escape first,
because it comes from outside the app.
"""

from __future__ import annotations

import html
from typing import Any

# label -> (display name, colour). Display names are sentence case; the colour always repeats the words.
VERDICTS: dict[str, tuple[str, str]] = {
    "SUPPORTED": ("Supported", "#2E7D4F"),
    "CONTRADICTED": ("Contradicted", "#B3261E"),
    "HELD": ("Held", "#B7791F"),
    "NOT_COMPARABLE": ("Not comparable", "#7A8594"),
    "CANNOT_VERIFY": ("Cannot verify", "#7A8594"),
    "PENDING": ("Not decided yet", "#C4CAD3"),
}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap');

:root {
  --dc-paper: #F7F8FA;
  --dc-ink: #1A2433;
  --dc-ink-soft: #4A5566;
  --dc-rule: #DDE2E9;
  --dc-accent: #2D5B8A;
  --dc-red: #B3261E;
}
html, body, [class*="st-"], .stMarkdown, .stText, button, input, textarea, select {
  font-family: 'Public Sans', system-ui, -apple-system, 'Segoe UI', sans-serif;
  font-variant-numeric: tabular-nums;
}
.stApp { background: var(--dc-paper); color: var(--dc-ink); }
.block-container { padding-top: 2.2rem; max-width: 1180px; }
h1, h2, h3 { color: var(--dc-ink); letter-spacing: -0.01em; }
h1 { font-weight: 700; font-size: 2.1rem; }
h3 { font-weight: 600; font-size: 1.15rem; margin-top: 1.6rem; }
[data-testid="stSidebar"] { background: #EEF1F5; border-right: 1px solid var(--dc-rule); }
[data-testid="stMetricValue"] { font-weight: 600; color: var(--dc-ink); }
[data-testid="stExpander"] details { background: #FFFFFF; border-color: var(--dc-rule); }
[data-testid="stVerticalBlockBorderWrapper"] > div[style*="border"] { background: #FFFFFF; }
a { color: var(--dc-accent); }
.stMarkdown table { display: block; overflow-x: auto; font-size: 0.86rem; }
.stMarkdown td, .stMarkdown th { white-space: nowrap; }
.stMarkdown td:nth-child(3) { white-space: normal; min-width: 9rem; }
:focus-visible { outline: 2px solid var(--dc-accent); outline-offset: 2px; }

.dc-brand { font-weight: 700; font-size: 1.35rem; color: var(--dc-ink); margin: 0; }
.dc-brand-sub { color: var(--dc-ink-soft); font-size: 0.86rem; line-height: 1.4; margin: 0.2rem 0 0.8rem; }

.dc-company { font-size: 2.4rem; font-weight: 700; color: var(--dc-ink); line-height: 1.1; margin: 0; }
.dc-meta { color: var(--dc-ink-soft); font-size: 0.92rem; margin: 0.35rem 0 1.4rem; }

.dc-strip { display: flex; gap: 3px; margin: 0 0 0.6rem; }
.dc-seg { flex: 1 1 0; min-width: 36px; height: 54px; border-radius: 3px; position: relative;
          display: flex; align-items: flex-end; padding: 0 0 6px 8px; color: #FFFFFF;
          font-size: 0.78rem; font-weight: 600; text-decoration: none; }
.dc-seg.dc-pending { color: var(--dc-ink-soft); }
.dc-legend { display: flex; flex-wrap: wrap; gap: 1.2rem; font-size: 0.92rem; color: var(--dc-ink); margin-bottom: 1.6rem; }
.dc-legend b { font-weight: 700; }

.dc-mark { display: inline-flex; align-items: center; gap: 0.4rem; font-weight: 600; }
.dc-mark i { width: 0.7rem; height: 0.7rem; border-radius: 2px; display: inline-block; }

.dc-quote { font-family: 'Source Serif 4', Georgia, serif; font-size: 1.18rem; line-height: 1.5;
            color: var(--dc-ink); margin: 0.2rem 0 0.6rem; max-width: 62ch; }
.dc-quote::before { content: "\\201C"; }
.dc-quote::after { content: "\\201D"; }
.dc-slide { color: var(--dc-ink-soft); font-size: 0.85rem; }
.dc-found { font-size: 1rem; line-height: 1.55; max-width: 66ch; margin: 0.2rem 0 0.6rem; }
.dc-small { color: var(--dc-ink-soft); font-size: 0.85rem; }

.dc-step { display: flex; gap: 0; margin: 0.4rem 0 0.8rem; flex-wrap: wrap; }
.dc-step span { padding: 0.35rem 0.8rem; font-size: 0.86rem; border: 1px solid var(--dc-rule);
                margin-right: -1px; background: #FFFFFF; color: #8A94A3; }
.dc-step span.done { color: var(--dc-ink); }
.dc-step span.now { background: var(--dc-accent); color: #FFFFFF; border-color: var(--dc-accent); font-weight: 600; }
.dc-step span.failed { background: var(--dc-red); color: #FFFFFF; border-color: var(--dc-red); font-weight: 600; }

@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
</style>
"""


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def verdict_name(label: str | None) -> str:
    return VERDICTS.get(label or "PENDING", (label or "", "#7A8594"))[0]


def verdict_colour(label: str | None) -> str:
    return VERDICTS.get(label or "PENDING", ("", "#7A8594"))[1]


def mark(label: str | None) -> str:
    """Coloured square + the verdict's name (colour never carries the meaning alone)."""
    return (f'<span class="dc-mark"><i style="background:{verdict_colour(label)}"></i>'
            f'{esc(verdict_name(label))}</span>')


def strip(claims: list[dict[str, Any]]) -> str:
    """The deck as one line: a segment per claim in slide order, coloured by verdict."""
    segs = []
    for c in sorted(claims, key=lambda c: (c.get("slide") or 0, str(c.get("claim_id")))):
        label = c.get("label") or "PENDING"
        cls = "dc-seg dc-pending" if label == "PENDING" else "dc-seg"
        title = f"Slide {c.get('slide')}: {verdict_name(label)}, {c.get('type')}"
        segs.append(f'<div class="{cls}" style="background:{verdict_colour(label)}" title="{esc(title)}" '
                    f'aria-label="{esc(title)}">{esc(c.get("slide"))}</div>')
    return f'<div class="dc-strip" role="img" aria-label="Claims by slide">{"".join(segs)}</div>'


def legend(by_label: dict[str, int]) -> str:
    parts = [f'{mark(k)} <b>{by_label[k]}</b>' for k in VERDICTS if by_label.get(k)]
    parts.append('<span class="dc-small">One block per claim, in slide order.</span>')
    return f'<div class="dc-legend">{"".join(f"<span>{p}</span>" for p in parts)}</div>'


def quote(text: str | None, slide: Any = None) -> str:
    where = f'<div class="dc-slide">Slide {esc(slide)}</div>' if slide is not None else ""
    return f'{where}<div class="dc-quote">{esc(text)}</div>'


def stepper(order: list[str], index: int, failed: bool, finished: bool) -> str:
    out = []
    for i, name in enumerate(order):
        cls = "now" if i == index else "done" if finished or i < index else ""
        out.append(f'<span class="{cls}">{esc(name)}</span>')
    if failed:
        out.append('<span class="failed">failed</span>')
    return f'<div class="dc-step">{"".join(out)}</div>'
