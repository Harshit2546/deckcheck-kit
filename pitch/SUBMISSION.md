# Submission form: ready-to-paste answers

Form opens from 2:30 PM and closes at 6:00 PM. One person submits for the team; the latest
submission counts. Fields marked **[human]** must be filled by a team member. Never guess them.

## Team name
**[human]** Use the same name every time you submit.

## One line
DeckCheck checks every claim in a startup pitch deck against live data and returns sourced,
dated verdicts, with the founder email held for a person's approval.

## Theme
Investing, 2.2 The Diligence Desk ("every pitch-deck claim tested before the second meeting").

## GitHub repo
https://github.com/Harshit2546/deckcheck-kit
**The repo must be public before you submit.** At 17:34 it was PRIVATE. The owner (Harshit2546)
changes it: GitHub > the repo > Settings > General > Danger Zone > Change repository visibility >
Make public. Then open the link in a private window to check.

## Demo video
**[human]** One Loom, unlisted YouTube or Google Drive link, two minutes, set to "anyone with the
link". Files: `pitch/DeckCheck_launch_film.mp4` (silent animated film, about 1:40) and the script
in `pitch/LAUNCH_VIDEO.md`. Test the link in a private window before submitting.

## Diagram
https://github.com/Harshit2546/deckcheck-kit/blob/main/docs/ARCHITECTURE.md
(GitHub renders its Mermaid diagram once the repo is public.)

## How does your product work?

**What it does today.** You give DeckCheck a pitch deck PDF, the company's domain and the deck's
date. It extracts every factual claim with its exact quote (an LLM proposes claims; code drops any
quote that is not on its slide). It resolves the company and founders in Crustdata using a
two-signal identity rule, so a namesake ends "unclear" instead of getting a verdict. One checker
per claim type fetches live data (Crustdata company, person and web search/fetch APIs) and keeps
each fact's own date. A rule engine in Python, driven by config/rules.yaml, picks one of five
verdicts: Supported, Contradicted, Not comparable, Cannot verify, Held. Only facts dated on or
before the deck date count. It writes a report (red flags, founder questions, evidence to
request, a cost ledger) and drafts a founder email.

**Where it still needs a person.** A person approves or rejects the founder email; only then is
it sent, exactly once, into a local test inbox (no real email leaves the machine). Every
"Cannot verify" names what would settle it, for the analyst to request. A verdict is advice to a
human reviewer, not an automatic rejection.

**Approaches we considered, and the one we chose.**
- Letting the LLM judge each claim, versus code deciding from fixed tolerances. We chose code:
  repeatable, explainable, and safe against hidden test cases where a wrong answer costs more
  than "cannot verify". The LLM only extracts claims and picks one exact sentence from a page.
- Using a provider's "current" snapshot (for example total headcount), versus its dated history.
  The snapshot carries only a refresh date, so we use the latest dated point on or before the deck
  date (349 people on 2026-11-02 for Locus).
- Web claims with or without page dates. Search results carry no date, so code reads the
  publish date from the page's HTML. Undated pages are used only under a guard (low confidence,
  deck at most 90 days older than the fetch, flagged in the report).
- A timeout treated as missing data, versus held. A slow source makes the claim Held, never
  Cannot verify.

**What worked and what didn't.** Live run on a synthetic deck about Locus: 4 claims decided, 3 left
open with a reason, 6 of 6 scored claims match our answer key, about Rs 12 at placeholder rupee rates
(11 Crustdata credits, 75 s of calls). Kill-and-resume worked on a real failure (a rejected API
key; the run finished from its checkpoint). What did not: many web pages have no machine-readable
date, so customer and market claims often end "Cannot verify"; Crustdata's open-roles count has no
date, so hiring claims stay open. Full list: docs/INCIDENTS.md.

**Models and tools.** OpenAI gpt-4o-mini (claim extraction and web quote picking), Crustdata APIs
(company enrich, person enrich and search, web search and fetch), Python, SQLite (checkpoints,
ledger, inbox), pypdf, Streamlit (UI), pytest (about 480 tests). Built with Claude Code, Codex and
Gemini agents in separate lanes, coordinated through AGENTS.md, DECISIONS.md and HANDOFF.md.

**What we would build next.** A job queue and worker pool, a shared cache with expiry, per-client
ledgers and rules files, recorded evidence for more decks to widen the answer key, and dated
sources for hiring data. Not now: each needs real usage data we do not have yet.

## Anything written before 10:15 AM?
Planning documents only: AGENTS.md, PLAN.md, TASKS.md and the agent prompts in
docs/AGENT_PROMPTS.md. No code was written before 10:15 AM. The first commit is 11:08 IST.

## Every member [human]
One page per member: name exactly as on the registration form, BITS Pilani email (the one used
for credits), YC registration email if different, BITS student ID, personal email, GitHub username.

## Before you press submit
- [ ] Repo is public, and its history starts after 10:15 AM on 22 November (first commit 11:08 IST).
- [ ] README.md is in the repo.
- [ ] The video is one link (not a folder) and plays in a private window.
- [ ] The diagram link opens for anyone.
- [ ] Every member's name matches the registration form; everyone used their
      @pilani.bits-pilani.ac.in address for credits.

## Extra material
Pitch deck (private Claude artifact; the owner must share it before others can open it):
https://claude.ai/artifact/NKiaffjQ7rzzEWNmpRybPQ. Project explainer: pitch/PROJECT_EXPLAINED.md.
