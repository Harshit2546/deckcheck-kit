"""DeckCheck UI look: CSS, verdict colours and small HTML pieces (slide strip, verdict mark, quotes, banner).

Called by: ui/app.py, ui/components (colours via ui/app.py). Calls: nothing (pure strings).
Design tokens follow the dark design spec the team chose (black canvas, #111111 surfaces, #374151 borders,
white text, red #E50914 only for primary actions, brand moments and Contradicted). Every piece of deck,
LLM or web text that goes into HTML here passes through html.escape first, because it comes from outside.
"""

from __future__ import annotations

import html
from typing import Any

# label -> (display name, colour). Red is the spec's primary/error red, so Contradicted is the one loud
# verdict; the others are muted so they never compete with it. The colour always repeats the words.
VERDICTS: dict[str, tuple[str, str]] = {
    "SUPPORTED": ("Supported", "#2F8F5B"),
    "CONTRADICTED": ("Contradicted", "#E50914"),
    "HELD": ("Held", "#B8781A"),
    "NOT_COMPARABLE": ("Not comparable", "#5F5F5F"),
    "CANNOT_VERIFY": ("Cannot verify", "#5F5F5F"),
    "PENDING": ("Not decided yet", "#2A2A2A"),
}

# Netflix Sans is proprietary, so: Inter (OFL) for text, Bebas Neue (OFL) for the wordmark and the report hero.
# Both from Google Fonts; offline the spec's own fallback stack is used.
FONT_STACK = "'Inter', 'Helvetica Neue', 'Segoe UI', Roboto, Ubuntu, Arial, sans-serif"
DISPLAY_STACK = "'Bebas Neue', 'Arial Narrow', 'Helvetica Neue', Impact, sans-serif"
FONTS_URL = ("https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@400;500;600;700;800"
             "&display=swap")

CSS = """
<style>
@import url('FONTS_URL');
:root {
  --dc-black: #000000;
  --dc-surface: #111111;
  --dc-border: #374151;
  --dc-ink: #FFFFFF;
  --dc-ink-soft: #B3B3B3;
  --dc-faint: #808080;
  --dc-red: #E50914;
  --dc-red-hover: #F6121D;
}
html, body, [class*="st-"], .stMarkdown, .stText, button, input, textarea, select {
  font-family: FONT_STACK;
  font-variant-numeric: tabular-nums;
}
.stApp { background: var(--dc-black); color: var(--dc-ink); }
.block-container { padding-top: 2.5rem; padding-bottom: 100px; max-width: 1200px; }
p, li { font-size: 16px; line-height: 1.4; }

/* type scale: headline-lg for page titles, headline-sm for sections */
h1 { font-size: 48px !important; line-height: 58px !important; font-weight: 800 !important; letter-spacing: -0.02em; color: var(--dc-ink); }
h2 { font-size: 36px !important; line-height: 43px !important; font-weight: 400 !important; }
h3 { font-size: 27px !important; line-height: 32px !important; font-weight: 400 !important; margin-top: 32px !important; color: var(--dc-ink); }
[data-testid="stCaptionContainer"], .stCaption { color: var(--dc-ink-soft) !important; font-size: 14px; }

/* sidebar: elevated surface */
[data-testid="stSidebar"] { background: var(--dc-surface); border-right: 1px solid var(--dc-border); }
[data-testid="stSidebar"] [role="radiogroup"] label { padding: 6px 0; font-size: 16px; font-weight: 500; }

/* buttons: 40px, 4px corners; primary red, secondary transparent with white outline */
.stButton button, .stDownloadButton button {
  min-height: 40px; padding: 6px 16px; border-radius: 4px; font-size: 16px; font-weight: 500;
  transition: background-color 120ms ease, border-color 120ms ease, transform 120ms ease;
}
.stButton button[kind="primary"] { background: var(--dc-red); border: 1px solid var(--dc-red); color: #FFFFFF; }
.stButton button[kind="primary"]:hover { background: var(--dc-red-hover); border-color: var(--dc-red-hover); }
.stButton button[kind="secondary"], .stDownloadButton button {
  background: transparent; border: 1px solid rgba(255, 255, 255, 0.7); color: #FFFFFF;
}
.stButton button[kind="secondary"]:hover, .stDownloadButton button:hover { border-color: #FFFFFF; background: rgba(255, 255, 255, 0.08); color: #FFFFFF; }
.stButton button:active, .stDownloadButton button:active { transform: translateY(1px) scale(0.985); }

/* inputs: dark inset fields, 40px, clear borders */
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"], [data-testid="stFileUploaderDropzone"] {
  background: var(--dc-black) !important; border: 1px solid var(--dc-border) !important; border-radius: 4px !important;
}
[data-baseweb="input"] input, [data-baseweb="textarea"] textarea { color: var(--dc-ink) !important; }
[data-baseweb="input"], [data-baseweb="select"] > div { min-height: 40px; }
[data-baseweb="tag"] { border-radius: 4px !important; background: #2A2A2A !important; color: #FFFFFF !important; }
[data-baseweb="tag"] span[role="presentation"] svg { fill: #B3B3B3; }

/* cards: black with a 1px charcoal border and 8px corners; no shadows */
[data-testid="stVerticalBlockBorderWrapper"] > div[style*="border"] {
  background: var(--dc-black); border: 1px solid var(--dc-border) !important; border-radius: 8px !important;
}
[data-testid="stExpander"] details { background: var(--dc-surface); border: 1px solid var(--dc-border); border-radius: 8px; }
[data-testid="stExpander"] summary { transition: background-color 150ms ease; border-radius: 8px; }
[data-testid="stExpander"] summary:hover { background: #1A1A1A; }
[data-testid="stExpander"] details[open] > div { animation: dc-open 160ms ease-out; }
@keyframes dc-open { from { opacity: 0; transform: translateY(-3px); } to { opacity: 1; transform: none; } }
[data-testid="stMetricValue"] { font-weight: 700; color: var(--dc-ink); }
[data-testid="stMetricLabel"] { color: var(--dc-ink-soft); }
hr { border-color: var(--dc-border) !important; }
a { color: var(--dc-ink); text-decoration: underline; text-underline-offset: 3px; }
:focus-visible { outline: 2px solid #FFFFFF !important; outline-offset: 2px; }

.stMarkdown table { display: block; overflow-x: auto; font-size: 14px; border-collapse: collapse; }
.stMarkdown th { color: var(--dc-ink-soft); font-weight: 500; border-color: var(--dc-border) !important; }
.stMarkdown td { border-color: var(--dc-border) !important; }
.stMarkdown td, .stMarkdown th { white-space: nowrap; }
.stMarkdown td:nth-child(3) { white-space: normal; min-width: 9rem; }

/* brand */
.dc-brand { font-family: DISPLAY_STACK; font-weight: 400; font-size: 40px; line-height: 1; color: var(--dc-red); margin: 0; letter-spacing: 0.02em; }
.dc-brand-sub { color: var(--dc-ink-soft); font-size: 14px; line-height: 1.4; margin: 8px 0 16px; }

/* report hero: headline-display */
.dc-company { font-family: DISPLAY_STACK; font-size: 80px; line-height: 80px; font-weight: 400; letter-spacing: 0.02em;
               color: var(--dc-ink); margin: 0; }
.dc-meta { color: var(--dc-ink-soft); font-size: 20px; line-height: 1.4; margin: 6px 0 32px; max-width: 60ch; }

/* pill banner for run-level notes */
.dc-banner { display: flex; align-items: center; gap: 16px; background: var(--dc-surface); border: 1px solid var(--dc-border);
             border-radius: 9999px; padding: 12px 24px; margin: 6px 0 16px; font-size: 16px; color: var(--dc-ink); }
.dc-banner b { color: var(--dc-red); font-weight: 700; }

/* static slide strip (fallback when motion components are off) */
.dc-strip { display: flex; gap: 4px; margin: 0 0 10px; }
.dc-seg { flex: 1 1 0; min-width: 36px; height: 58px; border-radius: 4px; position: relative;
          display: flex; align-items: flex-end; padding: 0 0 6px 8px; color: #FFFFFF;
          font-size: 12px; font-weight: 700; text-decoration: none; }
.dc-seg.dc-pending { color: var(--dc-ink-soft); border: 1px solid var(--dc-border); }
.dc-legend { display: flex; flex-wrap: wrap; gap: 20px; font-size: 16px; color: var(--dc-ink); margin-bottom: 32px; }
.dc-legend b { font-weight: 700; }

.dc-mark { display: inline-flex; align-items: center; gap: 8px; font-weight: 700; font-size: 16px; }
.dc-mark i { width: 12px; height: 12px; border-radius: 2px; display: inline-block; }

.dc-quote { font-size: 20px; line-height: 1.4; color: var(--dc-ink); margin: 4px 0 10px; max-width: 60ch; font-weight: 500; }
.dc-quote::before { content: "\\201C"; color: var(--dc-faint); }
.dc-quote::after { content: "\\201D"; color: var(--dc-faint); }
.dc-slide { color: var(--dc-faint); font-size: 14px; font-weight: 500; }
.dc-found { font-size: 16px; line-height: 1.4; max-width: 64ch; margin: 6px 0 10px; color: var(--dc-ink); }
.dc-small { color: var(--dc-ink-soft); font-size: 14px; font-weight: 400; }

.dc-step { display: flex; gap: 0; margin: 6px 0 12px; flex-wrap: wrap; }
.dc-step span { padding: 6px 16px; font-size: 14px; border: 1px solid var(--dc-border); margin-right: -1px;
                background: var(--dc-black); color: var(--dc-faint); }
.dc-step span:first-child { border-radius: 4px 0 0 4px; }
.dc-step span:last-child { border-radius: 0 4px 4px 0; }
.dc-step span.done { color: var(--dc-ink); }
.dc-step span.now { background: var(--dc-red); color: #FFFFFF; border-color: var(--dc-red); font-weight: 700; }
.dc-step span.failed { background: #5C0A0E; color: #FFFFFF; border-color: var(--dc-red); font-weight: 700; }

/* print the Report as a clean light document */
@media print {
  [data-testid="stSidebar"], header, [data-testid="stToolbar"], .stButton, .stDownloadButton,
  [data-testid="stDecoration"], [data-testid="stStatusWidget"] { display: none !important; }
  .stApp, .stApp * { background: #FFFFFF !important; color: #000000 !important; }
  .block-container { max-width: 100% !important; padding: 0 !important; }
  .dc-seg, .dc-mark i { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}

@media (max-width: 640px) {
  .dc-company { font-size: 52px; line-height: 54px; }
  .dc-meta { font-size: 16px; }
  h1 { font-size: 36px !important; line-height: 43px !important; }
  .dc-banner { border-radius: 8px; }
  .block-container { padding-left: 16px; padding-right: 16px; }
}

@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
</style>
""".replace("FONTS_URL", FONTS_URL).replace("DISPLAY_STACK", DISPLAY_STACK).replace("FONT_STACK", FONT_STACK)


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def verdict_name(label: str | None) -> str:
    return VERDICTS.get(label or "PENDING", (label or "", "#5F5F5F"))[0]


def verdict_colour(label: str | None) -> str:
    return VERDICTS.get(label or "PENDING", ("", "#5F5F5F"))[1]


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


def banner(text: str, lead: str | None = None) -> str:
    """Pill banner for a run-level note (deck date source, held claims, pending claims)."""
    head = f"<b>{esc(lead)}</b>" if lead else ""
    return f'<div class="dc-banner" role="note">{head}<span>{esc(text)}</span></div>'


def stepper(order: list[str], index: int, failed: bool, finished: bool) -> str:
    out = []
    for i, name in enumerate(order):
        cls = "now" if i == index else "done" if finished or i < index else ""
        out.append(f'<span class="{cls}">{esc(name)}</span>')
    if failed:
        out.append('<span class="failed">failed</span>')
    return f'<div class="dc-step">{"".join(out)}</div>'
