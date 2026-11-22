# ETHICS.md — Ethical Guidelines, Data Governance & Safety Guardrails

DeckCheck was designed from day one to operate with strict ethical guardrails,
data minimization, and human accountability. It is an algorithmic assistant
that advises human decision-makers; it is never an autonomous gatekeeper.

---

## 1. Data Minimization & Privacy Protection

- **Professional Information Only:**
  DeckCheck inspects and stores only verifiable, professional data attributes (past employers, public job titles, publicly stated tenure, and public company affiliations).
- **Zero Ingestion of Personal Identifiers:**
  Personal phone numbers, private emails, residential addresses, and raw personal data payloads are strictly dropped at ingestion. No private contact vectors are ever persisted in the SQLite store or passed to LLM prompts.
- **Payload Sanitization:**
  Third-party API responses (such as Crustdata person/company payloads) are sanitized before logging, stripping sensitive personal attributes.

---

## 2. Two-Signal Identity Rule (Mitigating Namesakes & False Accusations)

In emerging startup ecosystems, namesake confusion is common (different founders or distinct companies sharing identical names).
- **The Rule:** A company or individual is **only** resolved as confirmed if matched on at least **two independent signals** (e.g., domain match + registered legal name; or founder full name + verified corporate affiliation ID).
- **Fail-Safe Ambiguity Handling:**
  If only a single signal matches, the system refuses to speculate. The entity resolution outputs `identity_unclear`, preventing wrongful verification or false contradiction.

---

## 3. Verifiable Provenance: Zero Hallucinated Grounding

- **Every Fact Requires a Dated Source:**
  Every `Evidence` record permanently binds five mandatory provenance attributes:
  1. `source_type` (e.g., `CRUSTDATA_COMPANY`, `CRUSTDATA_PERSON`, `web_page`)
  2. `url_or_endpoint` (the exact URL or API endpoint retrieved)
  3. `field_or_quote` (the exact payload JSON path or verbatim sentence quote)
  4. `record_date` (the data point's own publication/event date, strictly on or before deck date)
  5. `retrieved_at` (the UTC ISO timestamp of retrieval)
- **Model Memory is Forbidden:**
  Verdicts are never generated from an LLM's pre-trained knowledge or weights. If external data cannot be retrieved, the claim remains unverified.

---

## 4. Code-Decided Verdicts (Eliminating Subjective Bias)

- **The LLM Never Decides:**
  The LLM is constrained strictly to mechanical tasks: parsing unstructured PDF text into candidate claims and extracting verbatim quotes from fetched web pages.
- **Deterministic Rules Engine:**
  All verdict transitions (*Supported*, *Contradicted*, *Not comparable*, *Cannot verify*, *Held*) are computed by deterministic Python code in `verdict/engine.py` using explicit numerical tolerances from `config/rules.yaml`. No probabilistic model ever renders a diligence verdict.

---

## 5. Human-in-the-Loop & Transactional Safeguards

- **Founder Communications are Held:**
  DeckCheck drafts contextual, neutral follow-up questions for founders on contradicted or unverified points, but saves them in `pending` status.
- **Mandatory Human Approval:**
  Emails cannot be dispatched autonomously. A human reviewer must explicitly inspect the draft, provide their reviewer identity, and approve the communication.
- **Transactional Exactly-Once Dispatch to Local Inbox:**
  All outbound messages are routed through compare-and-set state transitions (`approved -> sending -> sent`) enforced by database uniqueness triggers (`UNIQUE(idempotency_key)`).
- **No Real-World Spam:**
  Emails are routed exclusively to a localized mock inbox table (`inbox`), completely preventing accidental real-world email delivery.

---

## 6. Advice, Not Automatic Rejection

- **Neutral, Constructive Tone:**
  DeckCheck is framed as an objective diligence partner. A status of `CANNOT_VERIFY` or `NOT_COMPARABLE` indicates an absence of public records, never a negative judgment or red flag.
- **Actionable Clarification:**
  Instead of rejecting a pitch, DeckCheck specifies the exact missing documentation (e.g., term sheet summary, audit certificate) that would settle the claim.

---

## 7. Responsible Web Sourcing & Fair Use

- **Single-Sentence Quotation:**
  When querying external third-party market reports or news publications, DeckCheck extracts at most one verbatim sentence supporting the factual check, attributing and linking the full source URL.
- **Self-Reported Separation:**
  Customer claims verified only on a company's own domain are never marked as independently supported; they receive `CANNOT_VERIFY` (`self_reported_only`) to maintain diligence integrity.
