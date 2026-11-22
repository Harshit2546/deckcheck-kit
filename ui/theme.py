"""DeckCheck UI look: CSS, verdict colours and small HTML pieces (slide strip, verdict mark, quotes, banner).

Called by: ui/app.py, ui/components (colours via ui/app.py). Calls: nothing (pure strings).
One theme mixed from the team's two design specs (netflix.com-design.md, apple.com-design.md):
the dark canvas from the first; Apple's own ink #1D1D1F as panels and #F5F5F7 as text; Apple blue for
everything you can act on; Netflix red only for the wordmark and Contradicted; Apple's pill buttons,
12px cards, type scale and centred hero. Every piece of deck, LLM or web text that goes into HTML here
passes through html.escape first, because it comes from outside the app.
"""

from __future__ import annotations

import html
from typing import Any

# label -> (display name, colour). Red is kept for Contradicted alone; blue never means a verdict.
VERDICTS: dict[str, tuple[str, str]] = {
    "SUPPORTED": ("Supported", "#2F8F5B"),
    "CONTRADICTED": ("Contradicted", "#E50914"),
    "HELD": ("Held", "#B8781A"),
    "NOT_COMPARABLE": ("Not comparable", "#636366"),
    "CANNOT_VERIFY": ("Cannot verify", "#636366"),
    "PENDING": ("Not decided yet", "#2C2C2E"),
}

# SF Pro (Apple spec) shows on Apple devices through the system names; Inter is the stand-in elsewhere.
# Bebas Neue (OFL) is the wordmark and report hero face from the dark spec. Netflix Sans and SF Pro are
# proprietary, so neither is shipped. Offline, the system stack is used.
FONT_STACK = ("-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'SF Pro Display', 'Inter', "
              "'Helvetica Neue', 'Segoe UI', Roboto, Arial, sans-serif")
DISPLAY_STACK = "'Bebas Neue', 'Arial Narrow', 'Helvetica Neue', Impact, sans-serif"
FONTS_URL = ("https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@400;500;600;700"
             "&display=swap")

CSS = """
<style>
@import url('FONTS_URL');
:root {
  --dc-canvas: #000000;
  --dc-panel: #1D1D1F;
  --dc-raised: #2C2C2E;
  --dc-line: #3A3A3C;
  --dc-ink: #F5F5F7;
  --dc-muted: #86868B;
  --dc-soft: #A1A1A6;
  --dc-blue: #0071E3;
  --dc-blue-deep: #0066CC;
  --dc-link: #2997FF;
  --dc-red: #E50914;
}
html, body, [class*="st-"], .stMarkdown, .stText, button, input, textarea, select,
h1, h2, h3, h4, [data-testid="stHeading"] * {
  font-family: FONT_STACK;
}
/* fixed-width digits only where columns must line up */
table, [data-testid="stMetricValue"], [data-testid="stDataFrame"] { font-variant-numeric: tabular-nums; }
.stApp { background: var(--dc-canvas); color: var(--dc-ink); }
.block-container { padding-top: 54px; padding-bottom: 70px; max-width: 1120px; }
p, li { font-size: 16px; line-height: 1.55; letter-spacing: 0.01em; }

/* Apple type scale */
h1 { font-size: 40px !important; line-height: 48px !important; font-weight: 700 !important; letter-spacing: -0.01em; color: var(--dc-ink); }
h2 { font-size: 32px !important; line-height: 37.5px !important; font-weight: 600 !important; letter-spacing: -0.374px; }
h3 { font-size: 25px !important; line-height: 32px !important; font-weight: 600 !important; margin-top: 54px !important; color: var(--dc-ink); }
[data-testid="stCaptionContainer"], .stCaption { color: var(--dc-muted) !important; font-size: 14px; line-height: 20px; }

/* sidebar: quiet navigation */
[data-testid="stSidebar"] { background: var(--dc-panel); border-right: 1px solid var(--dc-raised); }
[data-testid="stSidebar"] [role="radiogroup"] label { padding: 5px 0; font-size: 15px; }

/* buttons: Apple pills, 44px. Primary filled blue; secondary panel fill with blue text */
.stButton button, .stDownloadButton button {
  min-height: 44px; padding: 11px 21px; border-radius: 980px; font-size: 17px; font-weight: 400; line-height: 1;
  transition: background-color 150ms ease, color 150ms ease, transform 120ms ease;
}
.stButton button[kind="primary"] { background: var(--dc-blue); border: none; color: #FFFFFF; }
.stButton button[kind="primary"]:hover { background: var(--dc-blue-deep); color: #FFFFFF; }
.stButton button[kind="secondary"], .stDownloadButton button {
  background: var(--dc-panel); border: 1px solid var(--dc-raised); color: var(--dc-link);
}
.stButton button[kind="secondary"]:hover, .stDownloadButton button:hover { background: var(--dc-raised); color: var(--dc-link); border-color: var(--dc-raised); }
.stButton button:active, .stDownloadButton button:active { transform: scale(0.98); }

/* inputs: quiet, 8px corners, blue focus */
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"], [data-testid="stFileUploaderDropzone"] {
  background: var(--dc-panel) !important; border: 1px solid var(--dc-raised) !important; border-radius: 8px !important;
}
[data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within, [data-baseweb="textarea"]:focus-within {
  border-color: var(--dc-blue) !important; box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.35) !important;
}
[data-baseweb="input"] input, [data-baseweb="textarea"] textarea { color: var(--dc-ink) !important; }
[data-baseweb="input"], [data-baseweb="select"] > div { min-height: 44px; }

/* chips: pill, low contrast */
[data-baseweb="tag"] { border-radius: 980px !important; background: var(--dc-raised) !important; color: var(--dc-ink) !important;
                       font-size: 12px !important; padding: 0 4px 0 10px !important; }
[data-baseweb="tag"] span[role="presentation"] svg { fill: var(--dc-muted); }

/* cards: panel fill, thin line, 12px, no shadow */
[data-testid="stVerticalBlockBorderWrapper"] > div[style*="border"] {
  background: var(--dc-panel); border: 1px solid var(--dc-raised) !important; border-radius: 12px !important;
}
[data-testid="stExpander"] details { background: var(--dc-panel); border: 1px solid var(--dc-raised); border-radius: 12px; }
[data-testid="stExpander"] summary { transition: background-color 150ms ease; border-radius: 12px; }
[data-testid="stExpander"] summary:hover { background: var(--dc-raised); }
[data-testid="stExpander"] details[open] > div { animation: dc-open 160ms ease-out; }
@keyframes dc-open { from { opacity: 0; transform: translateY(-3px); } to { opacity: 1; transform: none; } }
[data-testid="stMetricValue"] { font-weight: 600; color: var(--dc-ink); }
[data-testid="stMetricLabel"] { color: var(--dc-muted); }
[data-testid="stProgress"] [role="progressbar"] > div > div { background: var(--dc-blue) !important; }
hr { border-color: var(--dc-raised) !important; }
a { color: var(--dc-link); text-decoration: none; }
a:hover { text-decoration: underline; text-underline-offset: 3px; }
:focus-visible { outline: 2px solid var(--dc-link) !important; outline-offset: 2px; }

/* inline code is neutral: Streamlit's default green would read as "Supported" */
.stMarkdown code, .dc-small code { color: var(--dc-soft) !important; background: var(--dc-raised) !important;
                                   border-radius: 6px; padding: 1px 6px; font-size: 0.85em; }
.stMarkdown table { display: block; overflow-x: auto; font-size: 14px; border-collapse: collapse; }
.stMarkdown th { color: var(--dc-muted); font-weight: 500; border-color: var(--dc-raised) !important; }
.stMarkdown td { border-color: var(--dc-raised) !important; }
.stMarkdown td, .stMarkdown th { white-space: nowrap; }
.stMarkdown td:nth-child(3) { white-space: normal; min-width: 9rem; }

/* brand: the one Netflix-red moment besides Contradicted */
.dc-brand { font-family: DISPLAY_STACK; font-weight: 400; font-size: 40px; line-height: 1; color: var(--dc-red); margin: 0; letter-spacing: 0.02em; }
.dc-brand-sub { color: var(--dc-soft); font-size: 14px; line-height: 20px; margin: 8px 0 20px; }

/* report hero: centred, editorial (Apple), display face (dark spec) */
.dc-hero { text-align: center; padding: 20px 0 12px; }
.dc-company { font-family: DISPLAY_STACK; font-size: 88px; line-height: 88px; font-weight: 400; letter-spacing: 0.02em;
              color: var(--dc-ink); margin: 0; }
.dc-meta { color: var(--dc-soft); font-size: 20px; line-height: 32px; letter-spacing: 0.196px; margin: 12px auto 20px; max-width: 46ch; }

/* pill banner for run-level notes */
.dc-banner { display: flex; align-items: center; gap: 12px; background: var(--dc-panel); border: 1px solid var(--dc-raised);
             border-radius: 980px; padding: 12px 22px; margin: 4px 0 12px; font-size: 15px; color: var(--dc-ink); }
.dc-banner b { color: var(--dc-ink); font-weight: 600; }

/* static slide strip (fallback when motion components are off) */
.dc-strip { display: flex; gap: 4px; margin: 0 0 12px; }
.dc-seg { flex: 1 1 0; min-width: 36px; height: 58px; border-radius: 8px; position: relative;
          display: flex; align-items: flex-end; padding: 0 0 6px 10px; color: #FFFFFF;
          font-size: 12px; font-weight: 600; text-decoration: none; }
.dc-seg.dc-pending { color: var(--dc-soft); border: 1px solid var(--dc-line); }
.dc-legend { display: flex; flex-wrap: wrap; gap: 20px; font-size: 15px; color: var(--dc-ink); margin-bottom: 54px; }
.dc-legend b { font-weight: 600; }

.dc-mark { display: inline-flex; align-items: center; gap: 8px; font-weight: 600; font-size: 16px; }
.dc-mark i { width: 11px; height: 11px; border-radius: 3px; display: inline-block; }

.dc-quote { font-size: 20px; line-height: 30px; color: var(--dc-ink); margin: 4px 0 10px; max-width: 60ch; font-weight: 500; }
.dc-quote::before { content: "\\201C"; color: var(--dc-muted); }
.dc-quote::after { content: "\\201D"; color: var(--dc-muted); }
.dc-slide { color: var(--dc-muted); font-size: 14px; }
.dc-found { font-size: 16px; line-height: 1.55; max-width: 64ch; margin: 6px 0 10px; color: var(--dc-ink); }
.dc-small { color: var(--dc-soft); font-size: 14px; font-weight: 400; }

.dc-step { display: flex; gap: 6px; margin: 6px 0 12px; flex-wrap: wrap; }
.dc-step span { padding: 6px 14px; font-size: 13px; border-radius: 980px; background: var(--dc-panel); color: var(--dc-muted); }
.dc-step span.done { color: var(--dc-ink); }
.dc-step span.now { background: var(--dc-blue); color: #FFFFFF; font-weight: 600; }
.dc-step span.failed { background: var(--dc-red); color: #FFFFFF; font-weight: 600; }

/* print the Report as a clean light document */
@media print {
  [data-testid="stSidebar"], header, [data-testid="stToolbar"], .stButton, .stDownloadButton,
  [data-testid="stDecoration"], [data-testid="stStatusWidget"] { display: none !important; }
  .stApp, .stApp * { background: #FFFFFF !important; color: #1D1D1F !important; }
  .block-container { max-width: 100% !important; padding: 0 !important; }
  .dc-seg, .dc-mark i { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}

@media (max-width: 640px) {
  .dc-company { font-size: 56px; line-height: 58px; }
  .dc-meta { font-size: 16px; line-height: 24px; }
  h1 { font-size: 32px !important; line-height: 37.5px !important; }
  .dc-banner { border-radius: 12px; }
  .block-container { padding-left: 16px; padding-right: 16px; padding-top: 32px; }
}

@media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
</style>
""".replace("FONTS_URL", FONTS_URL).replace("DISPLAY_STACK", DISPLAY_STACK).replace("FONT_STACK", FONT_STACK)


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def verdict_name(label: str | None) -> str:
    return VERDICTS.get(label or "PENDING", (label or "", "#636366"))[0]


def verdict_colour(label: str | None) -> str:
    return VERDICTS.get(label or "PENDING", ("", "#636366"))[1]


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
