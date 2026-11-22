# DeckCheck launch video: concept, script, how to record

Format: two minutes, one video link (Loom, unlisted YouTube or Drive), due by 18:00 with the
submission form. The handbook's advice: open with the request going in, end with the finished
work coming out, show where each fact came from, keep the introduction to one sentence.

## The concept

Big-brand launch films do three things: a one-line problem that everyone recognises, a product
reveal with a short name, then the product doing its job while one line of narration explains
each step. DeckCheck's version:

- **The hook** is a deck full of confident claims ("350 people", "$50M Series C", "Trusted by Acme").
- **The reveal** is the name and a four-word promise: *Every claim. Checked. Sourced. Dated.*
- **The workflow** is six stages lighting up in order, ending at a human approval.
- **The proof** is three claims turning into three honest verdicts, including one "cannot verify".
- **The line to remember** is *"Cannot verify" is an answer.*

## Two ways to make it

**Version A, all animation (2:00).** Play `pitch/launch_film.html` full screen and record it.
Good for a safe, polished video. Weakness: it does not show the real product taking a real
request. The handbook asks for that, so prefer Version B.

**Version B, hybrid (recommended).** Film for the opening and close, real screen recording of the
live run in the middle. Judges pick finalists from this video, so real footage is worth more
than extra polish.

| Time | What is on screen | Voiceover |
|---|---|---|
| 0:00 to 0:09 | Film scene 1 (three claims rise in) | "Every pitch deck is full of claims." |
| 0:09 to 0:17 | Film scene 3 (DeckCheck logo, tagline) | "DeckCheck checks every one of them against live data, and shows its sources." |
| 0:17 to 0:30 | **Live.** UI Run page. Choose `tests/decks/deck_a_request.json` and start. Show the request text. | "Here is a real request: check every claim in this deck before our second meeting." |
| 0:30 to 0:50 | **Live.** Terminal or UI progress through extract, identify, check. Press Ctrl+C during checking, then `python cli.py resume <run_id> --out out/result.json`. | "Kill it mid-run. It resumes from its last saved step, without repeating a call." |
| 0:50 to 1:20 | **Live.** Claims page. Open slide 2 (350 people, SUPPORTED, 349 on 2026-11-02), slide 5 (700, CONTRADICTED), slide 6 (customer, CANNOT VERIFY). Click a source to show field, value and record date. | "Code decides every verdict, not the AI. 349 people on the second of November supports 350. It contradicts 700. And when no dated source names this customer, we say so." |
| 1:20 to 1:35 | **Live.** Approvals page, type a name, click approve. Inbox page shows one email. | "The founder email waits for a person. Approved, it is sent exactly once, to a local test inbox." |
| 1:35 to 1:45 | **Live.** Ledger page (calls, credits, rupees, seconds). | "Every call is in the ledger. A full check costs about twelve rupees at placeholder rates, against hours by hand." |
| 1:45 to 1:58 | Film scene 9 ("Cannot verify" is an answer.) | "Cannot verify is an answer." |

Cut points in the film: press the right arrow to jump scenes. Scenes are numbered 1 to 9 in
the order below.

## Version A script (the film as built, 2:00)

| # | Seconds | On screen | Voiceover (also shown as captions, press C to hide) |
|---|---|---|---|
| 1 | 9 | Three claims rise in, one by one | "Every pitch deck is full of claims." |
| 2 | 8 | "3 to 8 h" counts in | "Checking them by hand takes an analyst three to eight hours." |
| 3 | 8 | DeckCheck wordmark, tagline | "This is DeckCheck. Every claim, checked, sourced and dated." |
| 4 | 14 | Six stage cards light up along a progress line | "It reads the deck, finds the real company, fetches live data, decides with code, writes the report, and asks a person before anything is sent." |
| 5 | 14 | Three verdict cards flip: SUPPORTED, CONTRADICTED, CANNOT VERIFY | "Every claim gets one of five verdicts, with its source and the record's own date. When no source settles it, we say so." |
| 6 | 14 | Terminal: run, Ctrl+C, resume | "Kill it mid-run and it resumes from its last saved step, without repeating a single call." |
| 7 | 12 | Founder email: pending, Approve, sent once | "The founder email waits for a human. When approved, it is sent exactly once, into a local test inbox." |
| 8 | 11 | Four numbers: ₹11.96, 11 credits, 75 s, 6 of 6 | "One full check cost about twelve rupees at placeholder rates, in under two minutes. By hand, it is hours." |
| 9 | 8 | "Cannot verify is an answer." on blue | "Cannot verify is an answer." |

Every number in the film is real: 349 on 2026-11-02, ₹11.96, 11 credits, 74.8 seconds, 6 of 6
scored claims (run `run-20261122-104047-1b295e`). The terminal lines in scene 6 are a stylised
replay of what `cli.py` prints; for the submitted video, use the real terminal in Version B.

## How to record (10 minutes)

1. Open `pitch/launch_film.html` in Chrome. Press F11 for full screen.
2. Start a screen recorder (Loom, OBS or the Windows Game Bar with Win+Alt+R).
3. Click "Play launch film". Space pauses; left and right arrows jump scenes; R restarts; C hides captions.
4. For Version B, record the live part separately (laptop with `.env` loaded, `streamlit run ui/app.py`
   open on `http://localhost:8501`), then join the three pieces in any editor.
5. Voiceover: record it as you play, or read the captions over the finished recording. Keep a flat,
   calm voice. No music is needed. If you add some, use royalty-free only.
6. Export as MP4, upload, set "anyone with the link", and **open the link in a private window**
   before you submit.

## Things not to say in the video

- Do not call the rupee figures final prices: the rates in `config/rules.yaml` are placeholders.
- Do not say it checks "every kind of claim": hiring has no dated field yet, and competition
  claims are never judged by design.
- Do not say it emails founders: it writes to a local test inbox.
- Say the deck is synthetic (written by us about Locus), and that the data it was checked against is live.

## Before you record: fix the UI icon bug

The 17:05 handoff notes that the sidebar and expander icons show as raw text
("keyboard_double_..."). That would appear on screen. Fix it or avoid those screens, then do a
dry run of the live segment once.
