# plan.md — Samaritan

> **To the coding agent:** this file is the single source of truth for the project. Read all of it before writing any code. Build **phase by phase** (Phase 0 → 1 → 2 → 3 → 4). Do not start a phase until the previous phase's acceptance criteria pass and the user has approved it. Follow the conventions in Section 0 exactly.

**Contents:** 0 How to use this file · 1 What we are building · 2 Locked decisions · 3 Design direction · 4 Pages · 5 Violation checklist · 6 Detection engine · 7 Gnani Prisma integration · 8 Architecture, environment, demo mode · 9 Test dataset and evaluation · 10 API contract · 11 Data model · 12 Build phases · 13 Rules for the coding agent · Appendices A–C

---

## 0. How to use this file

**Tags you will see**
- **[ASK USER]** — you need something only the user has (API keys, files, accounts, a decision). At the **start of each phase**, ask for everything that phase needs in **one message**. While waiting, keep working on anything that doesn't depend on the answers (use mocks and fakes).
- **[VERIFY]** — a fact that may be outdated or was not confirmed. Check the official source (links in Section 7) before relying on it, and tell the user if reality differs from this file.
- **[DECIDE]** — choose using the criteria given, then record the choice and reason in `docs/decisions.md`.

**Conventions**
1. **Official docs beat this file.** If they conflict, follow the docs, note it in `docs/decisions.md`, and tell the user.
2. **Secrets never go in chat, code, logs, screenshots or commits.** Keys live in `.env` files the user edits. If the user pastes a key in chat, tell them to put it in `.env` instead and do not repeat it.
3. **Git:** run `git init` in Phase 0. Commit after each logical step with an imperative message. Never commit `.env*`, `data/audio/`, `*.db`, `node_modules/`, `.venv/`.
4. **"Done" for a phase** = every acceptance criterion passes, and you have told the user (a) what now exists, (b) how to run it, (c) what is mocked or unverified. Then stop and wait for approval.
5. **Quality bar:** TypeScript strict mode, ESLint clean, `ruff` clean, tests passing, no `TODO` or placeholder text on any user-visible path, every page has empty / loading / error states. The project must run from the README on a fresh clone.
6. **Data is synthetic only.** Never add real names, phone numbers, account numbers, Aadhaar, PAN or real call recordings.
7. **Credits and quotas are scarce** (Gnani: 5,000 credits; Groq free tier is tight). Cache everything, mock external APIs in tests, and **ask before any bulk run**.

**Facts in this file were checked on 2026-10-31** against docs.gnani.ai (STT Batch pages), Groq and Gemini public pages, and news coverage of RBI's 2026 recovery directions. Items that could not be confirmed are tagged **[VERIFY]**.

---

## 1. What we are building

**Samaritan** (product name; in descriptions you may call it "a recovery-call auditor") is a web application that audits loan-recovery (debt-collection) phone calls for Indian lenders. A compliance team uploads call recordings. The system transcribes them with **Gnani AI's Prisma speech-to-text** (Batch API, speaker-separated), then runs our own **two-layer detection engine** that flags violations of RBI's fair-practice rules for recovery agents. Every flag shows the **exact quote, timestamp, speaker, rule broken, RBI reference and severity**. The app scores each call and each agent, lets a reviewer confirm or dismiss flags, produces a printable evidence summary, and publishes its **own measured accuracy** on a labelled test set of 30 fake calls.

### 1.1 The problem
- Banks and NBFCs in India are legally responsible for how their recovery agents behave. RBI forbids harassment, threats, abusive language, public shaming, disclosing a debt to third parties, and calls outside permitted hours.
- RBI fines lenders for this. Examples: Bajaj Finance ₹2.5 crore; RBL Bank about ₹2.27 crore (March 2023); Krazybee ₹42.48 lakh (February 2023) — all citing recovery-agent harassment.
- Collection centres make thousands of calls a day. Compliance teams can only listen to a small sample, so most violations surface only after a borrower complains.

### 1.2 Who uses it
- **Primary user:** the compliance / quality-assurance team at a bank, NBFC or collection agency.
- Calls come from the **lender's own dialer recordings**. The product never runs on a borrower's personal phone, so no personal calls are ever heard.

### 1.3 Why it is not "just an AI wrapper"
Gnani only converts speech to text. Everything else is our own work, and the demo must make that obvious:
1. A **violation checklist** with precise flag / do-not-flag definitions, mapped to RBI rules (Section 5).
2. A **two-layer detection engine**: deterministic rules plus an LLM judge that must return **verifiable evidence** (Section 6).
3. **Evidence verification:** an LLM flag is accepted only if its quote really appears in the transcript.
4. **PII masking** before storage and before any text reaches an LLM.
5. Our **own labelled test set** of 30 fake calls and an **evaluation harness** reporting precision and recall per rule, with a held-out split (Section 9).
6. A real compliance-team product: scores, agent scorecards, reviewer workflow, evidence page.

### 1.4 One-line pitch
"Lenders are legally responsible for every recovery call but can check only a sliver of them. Samaritan checks 100% of calls in Hinglish and Marathi and gives compliance teams audit-ready evidence before a complaint becomes a ₹2 crore fine."

### 1.5 Hackathon constraints (hard rules)
- Built for **Gnani AI's Great Indian AI Internship Challenge**. Builder: **solo**.
- **Final submission deadline: November 10, 2026, 11:59 PM IST. No extensions.** (There is no day-by-day schedule in this file; the user will pace the work.)
- Must use at least one Gnani model/API → **Prisma STT**.
- **Synthetic data only.** All calls are acted out by the user and a friend from scripts.
- Submission needs: a working demo video posted publicly on LinkedIn and/or X with **#GnaniAI** and **#GreatIndianAIInternshipChallenge** (tagging Gnani AI), a written project explanation, the Gnani models used, and the post links.
- The user has **5,000 Gnani programme credits**.

### 1.6 What a judge should experience (demo narrative)
Open the live link → Overview with realistic data → Calls → open a flagged call → play audio, click a highlighted line, see the rule, quote and RBI reference → print the evidence page → Agents scorecard → Accuracy page with real precision/recall → (with the demo passcode) upload a new recording and watch it become Queued → Transcribing → Analysing → Done in a minute or two.

### 1.7 Project success criteria
- Live URL works end to end and looks like professional software in light and dark themes.
- All 30 test calls processed; the Accuracy page shows real, honestly reported numbers.
- No secrets in the repository; README lets a stranger run everything locally.
- Submission assets (demo script, explanation, post drafts) are ready and approved by the user.

---

## 2. Locked decisions

| Area | Decision |
|---|---|
| Team | Solo |
| Call input | Upload pre-recorded calls (single or bulk). **No live/real-time monitoring.** |
| Languages | Hinglish (primary) and Marathi |
| Speech-to-text | Gnani Prisma via the **Batch STT API** with speaker separation (Section 7) |
| Reasoning LLM | **Groq** (free tier) primary; **Google Gemini Flash** (free tier) fallback, switchable by env var |
| Frontend | Next.js (App Router, current stable — 16.x at time of writing **[VERIFY]**), React, TypeScript strict, Tailwind CSS v4, shadcn/ui (CLI v4). Node 20.9+ (22 LTS recommended). Package manager: **npm** |
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, httpx, ffmpeg |
| Database and storage | SQLite + local files in Phase 2; **Supabase** (Postgres + Storage) from Phase 3. **One SQLAlchemy codebase for both** (only `DATABASE_URL` and the storage backend change) |
| Hosting | Vercel (web), Render or Railway via Docker (API) |
| Access | **No login.** The app opens into a demo workspace for a fictional lender, "Sahyog Finance" |
| Public-demo safety | In `DEMO_MODE`, actions that spend credits (upload, retry, swap roles, eval run) require a passcode (Section 8.4) |
| Theme | Light and dark, with a toggle |
| Structure | Multi-page app (Section 4) |

**Out of scope** (name them as "future work" in the pitch; do not build): live call monitoring; login, multi-tenant, roles; dialer/telephony integration; borrower-facing app; regulator (RBI/ombudsman) version; languages other than Hinglish and Marathi; recording-notice and grievance-officer disclosure checks (reported in the 2026 directions — **[VERIFY]** before adding).

---

## 3. Design direction (mandatory — the user hates "vibe-coded" UI)

The UI must look like professional software a bank's compliance team already trusts. If a choice would make someone say "an AI generated this", don't make it.

**References to emulate:** Linear, Stripe Dashboard, Vercel dashboard, Mercury. Calm, dense, information-first.

### 3.1 Hard rules
- **Typography:** Geist for text and Geist Mono for IDs/timestamps (via `next/font`; `create-next-app` already sets this up). `font-variant-numeric: tabular-nums` on all numbers in tables and stats. Only **four sizes**: 12, 14, 16, 24 px. Weights 400 / 500 / 600 only. Headings never huge.
- **Colour:** neutral greys + **one accent (deep blue)**. Red / amber / green are used **only** for severity and status, never decoration.
- **Forbidden:** gradients, glows, glassmorphism, neon, emoji in the UI, 3D illustrations, "AI sparkle" icons, oversized hero sections, marketing copy inside the app, decorative blobs, rainbow charts, bouncy or page-load animations, centred "feature card" grids, drop shadows on cards.
- **Layout:** 8 px spacing grid. 1 px borders. Corner radius 6 px (8 px for dialogs). Shadows only on popovers and dialogs.
- **Data display:** tables for anything compared across rows. Cards only for the 4–5 KPI numbers on Overview.
- **Icons:** lucide-react, 16 px, used sparingly where they aid scanning.
- **Motion:** 150 ms transitions on hover/focus/open only.
- **Copy:** short, specific, professional. Every number has a label and unit. Every flag links to its evidence. Good: "Flagged moments", "Critical flags (7 days)". Bad: "AI-powered insights ✨", "Supercharge your compliance".
- **Seeded data must be realistic:** believable Indian agent names, durations like `2m 14s`, loan refs like `SF-PL-204871`, amounts like `₹12,500`. Never "Lorem ipsum", "John Doe", "Test 1". Use `en-IN` number formatting and IST times in 24-hour form (`21:40`) so after-hours calls are obvious.
- **States:** empty, loading (skeleton rows, not spinners everywhere) and error states for every page.
- **Responsive:** primary target 1280–1600 px desktop; must not break at 1280; mobile only needs to be readable.
- **Accessibility:** keyboard navigable, visible focus rings, WCAG AA contrast in both themes, `aria-label` on icon-only buttons.

### 3.2 Design tokens (implement as CSS variables / shadcn theme tokens; both themes must look designed, not inverted)

| Token | Light | Dark |
|---|---|---|
| background | `#FFFFFF` | `#0A0A0A` |
| surface (sidebar, table header) | `#FAFAFA` | `#111111` |
| border | `#E5E5E5` | `#262626` |
| text | `#171717` | `#EDEDED` |
| text-muted | `#737373` | `#A3A3A3` |
| accent | `#1D4ED8` | `#3B82F6` |
| accent-subtle (selected row, focus) | `#EFF6FF` | `#172554` |

**Severity / status badges** are small pills (12 px, weight 500, 1 px border, muted tinted background — never solid saturated fills):

| Meaning | Light (text on background) | Dark (text on background) |
|---|---|---|
| Critical | `#B91C1C` on `#FEF2F2` | `#FCA5A5` on `#2A1215` |
| High | `#C2410C` on `#FFF7ED` | `#FDBA74` on `#2A1A0E` |
| Medium | `#A16207` on `#FEFCE8` | `#FDE047` on `#262008` |
| Compliant / done | `#15803D` on `#F0FDF4` | `#86EFAC` on `#0F1F14` |

Score badges: ≥ 85 compliant, 60–84 medium, < 60 critical colours. Charts use the severity text colours; no other hues.

### 3.3 App shell
- Fixed left sidebar, 232 px, collapsible: the product wordmark "Samaritan" at the top (plain text in the UI font, weight 600, no logo art), then the workspace name "Sahyog Finance · Collections QA"; nav (Overview, Calls, Agents, Rules, Accuracy); at the bottom a theme toggle, an "About" link, and a small "Demo workspace · synthetic data" label.
- Top bar 56 px per page: title, one-line description, primary action on the right (e.g. "Upload calls").
- Content: max width 1280 px, 32 px padding. Table rows 44 px.
- **About** opens a dialog with four short paragraphs (what it is, who it is for, how it uses Gnani Prisma, data is synthetic). No marketing language.

---

## 4. Pages (functional spec)

There is **no marketing landing page**; `/` is the Overview.

### 4.1 Overview (`/`)
- KPI row: Calls audited · Calls with violations (count and %) · Critical flags · Average compliance score · Calls pending.
- Chart (Recharts): violations per day, last 14 days, stacked by severity.
- Tables: Most frequent violations (rule, count, % of calls) · Agents needing review (lowest 5 scores) · Recent critical flags (time, agent, rule, quote snippet → links to the call at that timestamp).

### 4.2 Calls (`/calls`)
- Table: Call ID, Agent, Called at (IST), Duration, Language, Status, Score, Violations (count + highest severity). Row click → call detail.
- Filters: date range, agent, language, status, severity, rule. Search by loan ref / call ID. Sort by any column. 25 rows per page.
- **Upload drawer** (right side): drag-and-drop multiple audio files (wav, mp3, m4a, ogg, flac; up to **25 MB each**; the API converts). Per file: agent (select or create), call date and time, language (Hinglish / Marathi), fake loan ref, and a checkbox "Borrower asked for this call time" (default off). Optional CSV to fill fields in bulk (`filename, agent_name, called_at, language, loan_ref, borrower_requested_time`). In demo mode the drawer first asks for the passcode. On submit, rows appear immediately as Queued; the list refetches every 5 s while any call is non-terminal.

### 4.3 Call detail (`/calls/[id]`)
- Header: call ID, agent, called at, duration, language, status, score badge.
- **Audio player** (wavesurfer.js) with waveform; flagged moments as coloured markers.
- **Transcript** (main column): one row per segment — timestamp, speaker ("Agent"/"Borrower"), text (masked). Flagged segments get a left border in the severity colour. Clicking a row seeks the audio; the playing row is subtly highlighted.
- **Violations panel** (right column): per flag — rule code and name, severity, quote, timestamp (click to seek), detected by (Rules / LLM / Both / Call metadata), confidence, and **Confirm / Dismiss** buttons. Flags without a quote show "Call metadata" (V1) or "First 60 seconds" (V8) instead.
- **Speaker roles:** if `roles_look_correct` is false show a banner "Speaker roles may be swapped" with a **Swap roles** button (re-runs detection, no re-transcription). The button is always available in a menu.
- **Evidence summary** button → `/calls/[id]/evidence`: clean printable page (lender, call metadata, each violation with quote, timestamp, rule, RBI reference, reviewer status, and the note "Automated findings are decision support and require human review"). Uses `@media print` CSS.
- Processing state with progress; failed state with the error and a **Retry** button.

### 4.4 Agents (`/agents`, `/agents/[id]`)
- List: agent, team, calls audited, average score, violation rate, critical flags, most common violation.
- Detail: score trend (line), violations by rule (horizontal bar), table of their calls (worst first).

### 4.5 Rules (`/rules`)
- Table of the 9 rules: code, name, description, RBI reference, severity, detection method, **enabled** toggle.
- Behaviour: disabling a rule (a) skips it in future analysis, (b) hides its existing flags, and (c) **recomputes every call and agent score immediately** ignoring that rule. Existing flags are not deleted.

### 4.6 Accuracy (`/accuracy`)
The "not a wrapper" proof page. Shows the latest evaluation run:
- Summary: calls evaluated, precision, recall, F1, clean calls wrongly flagged (x of 12).
- Per-rule table: precision, recall, F1, TP / FP / FN.
- **Rules only vs Rules + LLM** side by side (grouped bar chart plus table).
- Slice toggle: All 30 · Held-out test (20) · Hinglish · Marathi · Noisy audio.
- Timestamp accuracy: share of correctly detected flags that are within ±5 s of the labelled moment.
- "Known failure cases": short list generated by the eval run.
- A 3–4 sentence methodology note (not marketing) and the sentence "Flags are decision support, not legal findings."

---

## 5. Violation checklist (the domain core)

| Code | Violation | Detected by | Severity |
|---|---|---|---|
| V1 | Call outside permitted hours | Call metadata | High |
| V2 | Abusive or insulting language | Rules + LLM | Critical |
| V3 | Threat of physical harm or force | Rules + LLM | Critical |
| V4 | False legal threats (arrest, police, jail, FIR) | Rules + LLM | Critical |
| V5 | Public shaming / threatening to inform others | Rules + LLM | High |
| V6 | Disclosing the debt to a third party | LLM (weak keyword hints only) | High |
| V7 | Impersonation / false claim of authority | Rules + LLM | Critical |
| V8 | Agent fails to identify self and lender | Rules + LLM | Medium |
| V9 | Undue pressure / intimidation | Rules + LLM | Medium |

### 5.1 Precise definitions (these go into the LLM prompt and the rules table)
Judge **agent speech only**; borrower speech is context. When unsure, do not flag (precision matters), but report a confidence.

| Code | Flag when | Do NOT flag when |
|---|---|---|
| V1 | Call **start time** (IST) is before 08:00 or after 19:00 and `borrower_requested_time` is false. 08:00 and 19:00 themselves are allowed. | Inside the window; or the borrower asked for that time. |
| V2 | Profanity, slurs, name-calling or demeaning remarks directed at the borrower or their family (e.g. calling them a thief, useless, fraud). | Agent quoting the borrower; firm but civil language; stating lawful consequences. |
| V3 | Threat to harm, to send "recovery boys" or muscle, to seize property by force, or menacing "we'll see you at home". | A courteous notice that an executive may visit during permitted hours; mention of lawful recovery processes. |
| V4 | Claiming arrest, jail, FIR, warrant or police action as an imminent consequence of an ordinary loan default; unrealistic legal deadlines ("police will be at your door tomorrow"). | Neutral mention that the lender may send a legal notice or pursue recovery through due legal process; mention of credit-bureau reporting. |
| V5 | Threatening to tell the borrower's employer, colleagues, neighbours, relatives, society or social media about the debt, or to publish their name or photo. | Asking the borrower to confirm their own contact details. |
| V6 | Revealing loan, amount or default details to someone who is not the borrower (e.g. a relative or colleague who answered the phone). | Asking a third party to pass on a call-back request **without** disclosing the debt; speaking with a co-borrower or guarantor. |
| V7 | Claiming to be police, court, advocate, government, RBI or CBI; falsely claiming a legal notice or case already exists; materially false statements about the loan or its consequences. | Truthfully stating the agent's own role and the lender's name. |
| V8 | Within the first 60 seconds the agent does not state **both** their own name (or agent ID) **and** the lender's name. | Both are stated at any point in the first 60 seconds. |
| V9 | Ultimatums with menace ("pay right now or else"), manufactured urgency, guilt-tripping through family, ignoring a clearly stated inability to pay with repeated insistence. | Firm but polite reminders, asking for a payment date, offering options, stating due date and fees per the agreement. |

**Flags with no quote:** V1 has no segment (evidence = call metadata); V8 has no quote (evidence = the first 60 seconds; set `start_s = 0`).

### 5.2 RBI references
- Reported background (secondary sources, **[VERIFY]** on rbi.org.in): RBI issued its amendment directions on loan recovery conduct on 6 August 2026 (a set of circulars for banks, NBFCs and others); calls and visits only between 8:00 and 19:00 unless the borrower asks for another time; effective date reported as 1 January 2027. Earlier directions already prohibited harassment, intimidation, threatening or anonymous calls, and calls outside 8:00–19:00.
- Seed each rule's `rbi_reference` as a short text such as `RBI Responsible Business Conduct Directions — recovery conduct: <topic>. Clause: [to verify]`. **[ASK USER]** whether they want you to draft clause references from public RBI circulars; if yes, mark each "to verify" until the user confirms.
- Call frequency (too many calls a day) is excluded because a single recording cannot show it.

### 5.3 Scoring
Each call starts at 100. Deduct per **non-dismissed** violation of an **enabled** rule: **Critical −30, High −15, Medium −5**; floor 0. Agent score = mean of their call scores. Weights live in `api/app/config/scoring.yaml`.

---

## 6. Detection engine (backend spec)

Input: Gnani transcript segments + call metadata. Output: a list of violations plus call-level flags (`roles_look_correct`).

### 6.0 Normalisation (used by every later step)
Unicode NFC; remove zero-width characters; casefold; collapse whitespace; strip punctuation for matching only (keep original text for display). Gnani's Hinglish output may be **Devanagari for Hindi words and Latin for English words** (see Section 7), so **every lexicon must cover both scripts**, plus common romanised spellings.

### 6.1 Pre-processing (in this order)
1. **Speaker roles.** Gnani returns `speaker_id` as an **integer** (typically 1 and 2). Map to Agent/Borrower by scoring each speaker: count hits against an *agent lexicon* (self-introduction, lender name, "EMI", "overdue", "payment", "loan number", …) minus hits against a *borrower lexicon* ("mere paas paisa nahi", "agle hafte", …). Highest agent score is the Agent; ties → the speaker who speaks first. If diarization produced one speaker or none, set all segments to `unknown`. Store `calls.agent_speaker_id`.
2. **PII masking — applied before anything is stored or sent to an LLM.** Replace with `[PHONE]`, `[ACCOUNT]`, `[AADHAAR]`, `[PAN]`: 10-digit mobile numbers (`[6-9]\d{9}`, with optional +91/spaces/dashes), 12-digit Aadhaar-like runs, PAN pattern `[A-Z]{5}\d{4}[A-Z]`, digit runs of 9+ (account), **and runs of 6+ consecutive spoken digit words** in English, Hindi (Latin and Devanagari) and Marathi (e.g. "nau aath saat…"). Do **not** mask ordinary amounts ("do hazaar paanch sau", "₹12,500").
3. **Store only masked text** in `segments.text`. Everything downstream (Layer 1, the LLM, the UI) uses the masked text. The raw Gnani JSON is cached server-side only (`calls.raw_transcript`) and is never returned by the API.

### 6.2 Layer 1 — deterministic rules (fast, free)
- **V1:** convert `called_at` to IST; flag if start time is before 08:00:00 or after 19:00:00 and `borrower_requested_time` is false. Final — the LLM never touches V1.
- **V8:** in agent segments with `start_s < 60`, look for a self-introduction pattern (e.g. "main … bol raha/rahi", "mera naam", "मेरा नाम", "calling from", "से बोल रहा/रही") **and** a lender alias from `api/app/config/workspace.yaml` (`lender_name`, `lender_aliases` in Latin and Devanagari). Both present → pass.
- **V2–V7, V9:** lexicon matching on Agent segments. Lexicons are YAML files in `api/app/detection/lexicons/` (one per rule), editable without code changes:
```yaml
rule: V4
patterns:
  - { text: "police", lang: both, strength: weak }
  - { text: "पुलिस", lang: both, strength: weak }
  - { regex: "kal\\s+police\\s+(aa|aayegi|aa jayegi)", lang: hinglish, strength: strong }
```
  `strength: strong` = almost always a violation; `weak` = a candidate the LLM must judge. Starter seeds are in Appendix B; **expand them from the call scripts, but do not tune against the held-out test split** (Section 9).
- Output: candidate flags (`rule_code`, `segment_index`, `matched_text`, `strength`).

### 6.3 Layer 2 — LLM judge (one request per call)
**Why one request per call:** Groq's free tier is tight (reported for `openai/gpt-oss-120b`: about 30 requests/min, 1,000/day, **8,000 tokens/min, 200,000 tokens/day** — **[VERIFY]** on the user's Groq limits page). Devanagari text costs many tokens. A 3-minute call is roughly 4,000 tokens including the prompt, so budget about 1–2 calls per minute and about 45 calls per day. Therefore:
- Send **one request per call** containing the rules, the full masked transcript, and the Layer-1 candidates as *hints*. If the transcript exceeds ~3,500 tokens, split into windows of ~60 segments with 5 overlapping segments and dedupe by (rule, segment).
- **Cache every LLM response** in the `llm_cache` table keyed by `sha256(provider, model, PROMPT_VERSION, system, user)`. Cache hits cost nothing and never count against limits.
- Use Gemini for rapid prompt iteration; use Groq for the final evaluation runs.

**Input format to the LLM:** the rule definitions from Section 5.1; the transcript as lines `[idx] AGENT|BORROWER (mm:ss): text`; the candidates as `[{"candidate_id":"c1","rule_code":"V4","segment_index":14,"matched":"police"}]`.

**Required output (strict JSON, validate with Pydantic; one retry on invalid JSON, stripping code fences if present):**
```json
{
  "roles_look_correct": true,
  "violations": [
    {
      "rule_code": "V5",
      "segment_index": 14,
      "quote": "office mein sabko bata denge",
      "explanation": "Agent threatens to tell the borrower's colleagues about the debt.",
      "confidence": 0.86
    }
  ]
}
```
For V8 (absence), return `"segment_index": null, "quote": null`. The LLM must **not** return V1.

**Prompt requirements:** include all nine definitions with their do/don't columns; 4 short few-shot examples (one V5, one V4-lawful-notice that is *not* flagged, one clean strict-but-polite call returning `[]`, one V6); say that text may be Devanagari, Latin or mixed Hinglish or Marathi; say to quote **verbatim** from the line; set `temperature: 0`; define `roles_look_correct` as false when the "Agent" lines read like a borrower's speech or vice versa. Keep a `PROMPT_VERSION` constant (e.g. `v1`) and bump it on every prompt change.

**Evidence verification (critical):** accept an LLM flag only if its `quote` is found in the referenced segment (or ±1 segment) of the masked, normalised text using fuzzy matching (`rapidfuzz.partial_ratio ≥ 85`). Otherwise discard it and log it. Drop flags with `confidence < 0.6`. Cap `quote` at 200 characters.

### 6.4 Merge (the `rules_plus_llm` configuration)
- A Layer-1 candidate **confirmed** by an LLM flag on the same rule and the same or an adjacent segment → one violation, `detected_by = "both"`.
- LLM-only flag → `detected_by = "llm"`.
- A Layer-1 candidate (strong or weak) that the LLM did **not** return → **dropped** (the LLM has the final say).
- V1 → `detected_by = "metadata"`. V8 → the LLM's decision if available, else Layer 1.
- If the LLM is unavailable after fallback, keep the Layer-1 results, set `analysis_meta.llm_failed = true`, and show a "Analysed without LLM" notice on the call.
- The **`rules_only` configuration** (used for the baseline on the Accuracy page) = all Layer-1 hits, strong and weak, with no LLM.

### 6.5 LLM provider abstraction
- One interface `complete_json(system, user, schema) -> dict`. `LLM_PROVIDER=groq|gemini`, `LLM_FALLBACK_PROVIDER`. Model names come from env vars, never hard-coded.
- **Groq:** use an open model available on the user's free tier (the sources above reference `openai/gpt-oss-120b`; **[ASK USER]** which models their console lists). Request JSON output where the model supports it **[VERIFY]**; always validate with Pydantic.
- **Gemini:** a Flash or Flash-Lite model from Google AI Studio via the `google-genai` SDK. **[ASK USER]** for the model name shown in their AI Studio. The Gemini free tier may use inputs for training — acceptable because only masked synthetic text is sent.
- **Rate limiting:** token-aware limiter using `LLM_RPM_LIMIT` and `LLM_TPM_LIMIT` (estimate tokens from character count, correct with the response's usage field). On 429: honour `retry-after` if present, else exponential backoff (1 s, 2 s, 4 s). After 3 failures or 2 invalid-JSON responses → switch to the fallback provider for that call and record `analysis_meta.llm_provider_used`.

### 6.6 Pipeline and robustness
Statuses: `queued → transcribing → analysing → done` (or `failed` with `error`). The worker runs in-process, processes **one call at a time** (Gnani may enforce a single active request), and a failing call must never stop the queue.
- **Idempotent:** save `gnani_job_id` immediately after the job is created. If a call already has `raw_transcript`, skip Gnani. If it has a `gnani_job_id` but no transcript (e.g. the server restarted), **resume polling** that job instead of creating a new one.
- **Resume on startup:** re-enqueue calls left in `queued`, `transcribing` or `analysing`. (Free hosting tiers sleep and restart.)
- Run order after transcription: speaker roles → masking → Layer 1 → Layer 2 → merge → score → save.

---

## 7. Gnani Prisma integration (verified 2026-10-31 from docs.gnani.ai — re-check before coding)

**Docs:** index https://docs.gnani.ai/llms.txt · Batch create https://docs.gnani.ai/api/STT/batch/create-job.md · start https://docs.gnani.ai/api/STT/batch/start-job.md · status https://docs.gnani.ai/api/STT/batch/get-job.md · files https://docs.gnani.ai/api/STT/batch/get-files.md · models https://docs.gnani.ai/api/STT/models/overview.md and https://docs.gnani.ai/api/STT/models/prisma-v3.md · languages https://docs.gnani.ai/api/STT/languages.md · limits https://docs.gnani.ai/api/STT/limits.md · errors https://docs.gnani.ai/api/introduction/errors.md · call-analytics example https://docs.gnani.ai/api/use-cases/call-analytics.md · Python SDK https://docs.gnani.ai/python-sdk/speech-to-text-batch.md

### 7.1 Why Batch
The synchronous REST endpoint (`POST https://api.vachana.ai/stt/v3`) accepts clips of **30 seconds at most** (one doc page says 60 s in prose, its OpenAPI spec says 30 s; either way far too short). Our calls are 1–3 minutes. Use the **Batch API**. Call it directly with `httpx` (full control, easy to fake in tests). The official Python SDK (`gnani-vachana>=0.8.1`, import `gnani.stt`, class `GnaniSTTBatchClient`) is an optional alternative; its `diarization` / `speakers` options map to the config below.

### 7.2 Authentication
Header **`X-API-Key-ID: <GNANI_API_KEY>`** on every request. Optional `X-API-Request-ID` (a UUID) for correlation — log it.

### 7.3 Flow (one job per call)
1. **Create job** — `POST https://api.vachana.ai/stt/v3/batch/jobs`, multipart: a `config` field holding a **JSON string** (content type `application/json`) and a `files` field with the audio. Returns `201 {job_id, status:"CREATED", total_files_accepted, created_at, message}`. The returned `message` mentions `/v1/jobs/...` — **ignore it**; use the paths in this section.
```python
files = [
  ("config", (None, json.dumps(config), "application/json")),
  ("files", (f"{call_id}.wav", audio_fh, "audio/wav")),
]
httpx.post(f"{base}/stt/v3/batch/jobs", headers={"X-API-Key-ID": key}, files=files, timeout=120)
```
2. **Start job** — `POST /stt/v3/batch/jobs/{job_id}/start` (no body). Creating a job does **not** start it. Returns `202 {status:"STARTING"}`. A second call returns `409 JOB_ALREADY_STARTED`.
3. **Poll** — `GET /stt/v3/batch/jobs/{job_id}` **no more often than every 10 s**. Terminal statuses: `COMPLETED`, `PARTIAL_FAILURE`, `FAILED`, `START_FAILED` (read `cancel_reason`), `CANCELLED`. Anything else (`CREATED`, `STARTING`, `QUEUED`, `IN_PROGRESS`) means keep waiting. The response has `progress` counters, not transcript text.
4. **List files** — `GET /stt/v3/batch/jobs/{job_id}/files?status=COMPLETED` → `{job_id, data:[{file_id, original_path, status, duration_seconds (a STRING here), transcript_url, error_message, ...}], pagination}`. The array key is **`data`**. `transcript_url` is a pre-signed URL that needs **no API key** and expires in **1 hour** (call this endpoint again for a fresh one).
5. **Download** `transcript_url` → JSON:
```json
{
  "file_id": "…", "job_id": "…", "original_path": "….wav",
  "language_code": "en-IN", "duration_seconds": 6.01,
  "model": "gnani-prisma-v2.5", "mode": "transcribe",
  "segments": [ { "segment_id": 0, "start_time": 0.0, "end_time": 0.71, "text": "hello", "speaker_id": 1 } ],
  "full_transcript": "…"
}
```
`speaker_id` is an **integer**. Times are seconds (inferred from the examples). **There is no word-level timestamp** — only segment-level; build everything on segments. Cache the whole JSON in `calls.raw_transcript`.

### 7.4 Config (`config` JSON)
Required: `model`, `language_code`. Accepted `model` values in the Batch config: **`prisma-v2.5`** and **`prisma-v3.0`** (the transcript's output `model` field reads `gnani-prisma-v2.5` — that is output, not input). The older batch intro page https://docs.gnani.ai/api/STTBatch/Introduction.md still shows `gnani-prisma-v2.5` as the only input value because it predates v3.0; the current reference pages say `prisma-v2.5` / `prisma-v3.0`. **Rule:** send `prisma-v3.0` by default. When using v2.5 send `prisma-v2.5`; if Gnani answers `400` about the model or config, retry once with `gnani-prisma-v2.5` and record which form worked in `docs/gnani-findings.md`.

| Field | Notes |
|---|---|
| `mode` | `"transcribe"` (default) |
| `with_diarization` | Set `true`. On v3.0 speaker labels are produced regardless; the flag decides whether a diarization failure fails the file |
| `num_speakers` | Integer 1–8, an upper limit (speakers are counted automatically). Set `2`. (An older doc claim of "max 2 speakers" is superseded by the reference page) |
| `is_multi_channel` | `true` only for genuine multi-channel files (each speaker on their own channel). **[VERIFY]** with a real stereo file how `speaker_id` is assigned (the docs do not say). If it is unclear or wrong, do it ourselves: split the channels with ffmpeg, transcribe each as its own mono file, and merge by timestamp with speaker = channel. This bills the audio twice, so use it only if mono diarization is poor |
| `with_denoise` | `true` runs speech enhancement first — useful for noisy call-centre audio. We evaluate it on the noisy subset |
| `format` | **v3.0 only** (`verbatim`, `transcribe`, `codemix`); sending it with v2.5 → `400 INVALID_CONFIG` |
| `keyterms` | **v3.0 only**, up to 200 words/phrases (e.g. "EMI", "overdue", "Sahyog Finance"). Cannot be combined with `speaker_names` |
| `topic` | **v3.0 only**, 30–1,600 characters. Can be combined with `keyterms`. Docs warn that context can reduce accuracy — compare with and without |

**Language settings**
- Hinglish → `model: "prisma-v3.0"`, `language_code: "hi-IN,en-IN"` (v3.0 accepts 1–4 comma-separated codes, or `indic-auto`).
- Marathi → `model: "prisma-v3.0"`, `language_code: "mr-IN,en-IN"`.
- v3.0 output scripts: `transcribe` → Hindi words in Devanagari, English words in **Latin**, numbers as **digits**; `codemix` → same scripts but numbers spelled as words; `verbatim` → everything in Devanagari. **Default to `format: "transcribe"`** (readable, digits make masking easy).
- Fallback (v2.5): Hinglish `en-IN` ("accepts English–Hindi mixed audio", Latin output); Marathi `mr-IN`.
- Supported languages (both models): bn-IN, en-IN, gu-IN, hi-IN, kn-IN, ml-IN, mr-IN, pa-IN, ta-IN, te-IN.

**Do not hard-code the final configuration. Choose it with the spike in Phase 2 step 2.2**, then store the chosen config in env vars and in `calls.transcription_config`.

### 7.5 Limits
10 MB per file; 100 files per job (we send 1); audio length up to 4 hours; poll ≥ 10 s apart. Per-request rate limits and credit cost per minute are **not published numerically** — they appear in the user's dashboard at app.gnani.ai. **[ASK USER]** for both.

### 7.6 Audio preparation (ffmpeg)
Convert to **16 kHz mono 16-bit WAV** (~1.9 MB per minute). If the result exceeds 9.5 MB, re-encode as **FLAC**; if it is still over 9.5 MB, fail the call with a clear message. **MVP call-length limit: 8 minutes** (`MAX_CALL_MINUTES`). Always send a `.wav` or `.flac` extension (batch validates the extension). Keep stereo only when `is_multi_channel` is used. Probe uploads with `ffprobe` and reject non-audio files.

### 7.7 Errors — normalise three shapes into one `GnaniError(code, message, http_status, retryable)`
- Batch: `{"error": "...", "message": "..."}` (e.g. `UNSUPPORTED_LANGUAGE`, `INVALID_CONFIG`, `NO_FILES_PROVIDED`, `FILE_TOO_LARGE`, `JOB_NOT_FOUND`, `JOB_ALREADY_STARTED`, `JOB_CANCELLED`).
- Auth and rate limits: `{"detail": {"error_code": "...", "message": "...", "status_code": N}}` (`MISSING_API_KEY`, `INVALID_API_KEY`, `SCOPE_NOT_ALLOWED`, `RATE_LIMITED`).
- Validation (422): `{"detail": [ ... ]}`.
- **Retry** (backoff 0.5 s, 1 s, 2 s; 3 attempts): connection errors, 429, 500, 503, 504. **Never retry** other 4xx. **Out of credits or key problems:** the docs show no body for insufficient credit. The synchronous API documents a `403 FORBIDDEN` whose message says to check the API key, organisation status or available credits, and a `402` may also exist (unverified). Treat **402, and 403 with a credit/organisation/forbidden message,** as non-retryable: stop the whole queue, mark the call `failed` with "Gnani credits exhausted or key not permitted", and tell the user.
- A `config` that is not valid JSON causes a 500 — always build it with `json.dumps`.
- Per-file failures appear in the files list with `error_message` (codes such as `INVALID_RECOGNITION_OPTIONS`, `UNSUPPORTED_LANGUAGE`).
- Keep **one active Gnani request at a time** (`GNANI_MAX_CONCURRENT=1`) until the dashboard shows a higher limit.

### 7.8 Caching and credits
Never re-submit a call that already has a `raw_transcript` unless the user clicks "Re-transcribe" (`?retranscribe=true`). Tests must use the fake Gnani server (Phase 2), never the real API.

---

## 8. Architecture, environment, demo mode

### 8.1 Repository layout
```
samaritan/
├── plan.md                    ← this file
├── README.md                  ← written in Phase 4
├── docs/
│   ├── decisions.md           ← every [DECIDE] and doc-conflict note
│   └── gnani-findings.md      ← spike results (Phase 2)
├── web/                       ← Next.js app (Phase 1)
│   └── src/
│       ├── app/               ← routes: /, /calls, /calls/[id], /calls/[id]/evidence, /agents, /agents/[id], /rules, /accuracy
│       ├── components/        ← ui/ (shadcn), app-shell, data-table, charts, transcript, audio-player, upload-drawer, badges
│       └── lib/
│           ├── types.ts       ← shared types (Section 10)
│           ├── api/           ← client interface + mockClient (Phase 1) + httpClient (Phase 4)
│           ├── mock/          ← realistic mock data
│           └── format.ts      ← IST dates, en-IN numbers, durations
├── api/                       ← FastAPI service (Phase 2)
│   ├── app/
│   │   ├── main.py, config.py, schemas.py, models.py (SQLAlchemy), db.py
│   │   ├── config/            ← scoring.yaml, workspace.yaml
│   │   ├── routers/           ← calls, agents, rules, stats, eval
│   │   ├── services/          ← gnani_client.py, audio.py, masking.py, roles.py, pipeline.py, scoring.py, llm/ (base, groq, gemini, limiter, cache)
│   │   ├── detection/         ← normalise.py, rules_engine.py, llm_judge.py, merge.py, lexicons/*.yaml, prompts/
│   │   ├── storage/           ← base.py, local.py, supabase.py (Phase 3)
│   │   └── worker.py
│   ├── alembic/               ← migrations (both SQLite and Postgres)
│   ├── tests/                 ← including tests/fakes/gnani_fake.py
│   ├── Dockerfile             ← python:3.11-slim + ffmpeg
│   └── pyproject.toml
├── supabase/                  ← rls_and_storage.sql (Phase 3)
├── eval/                      ← run_eval.py, metrics.py, label_times.py, reports/
├── scripts/                   ← seed.py, reset_demo.py, migrate_local_to_supabase.py
├── submission/                ← demo_script.md, project_explanation.md, social_post.md (Phase 4)
└── data/
    ├── scripts/               ← call_01.md … call_30.md
    ├── answer_keys/           ← call_01.json … call_30.json
    ├── RECORDING_GUIDE.md
    └── audio/                 ← recordings (git-ignored)
```
Flow: Upload (browser → API directly) → API validates, converts audio, stores it, creates the call → worker → Gnani Batch STT → roles → masking → Layer 1 → Layer 2 → merge → score → save → web polls.
The **web app never calls Gnani, Groq, Gemini or Supabase.** All secrets live in the API only. **Do not proxy uploads through Next.js route handlers** (serverless request-size limits); the browser posts straight to the API.

### 8.2 Environment variables
`api/.env` (commit only `api/.env.example`):
```
# Gnani
GNANI_API_KEY=
GNANI_BASE_URL=https://api.vachana.ai
GNANI_MODEL=prisma-v3.0
GNANI_LANG_HINGLISH=hi-IN,en-IN
GNANI_LANG_MARATHI=mr-IN,en-IN
GNANI_FORMAT=transcribe
GNANI_WITH_DENOISE=false
GNANI_POLL_SECONDS=10
GNANI_MAX_CONCURRENT=1
# LLM
LLM_PROVIDER=groq
LLM_FALLBACK_PROVIDER=gemini
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-120b
GEMINI_API_KEY=
GEMINI_MODEL=
LLM_RPM_LIMIT=30
LLM_TPM_LIMIT=8000
LLM_CACHE=on
# Storage and database
STORAGE_BACKEND=local            # local (Phase 2) | supabase (Phase 3+)
DATABASE_URL=sqlite:///./local.db
LOCAL_AUDIO_DIR=./.data/audio
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_BUCKET=call-audio
# Limits and safety
MAX_UPLOAD_MB=25
MAX_CALL_MINUTES=8
DEMO_MODE=false
UPLOAD_PASSCODE=
ADMIN_TOKEN=
CORS_ORIGINS=http://localhost:3000
```
`web/.env.local`:
```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_DATA_SOURCE=mock     # mock (Phase 1) | api (Phase 4)
```
`.env*` must be git-ignored. Never print keys.

### 8.3 Next.js gotchas to respect
In current Next.js App Router, `params` and `searchParams` in pages are **Promises** (`await` them). Components using wavesurfer.js or Recharts must be **client components** (`"use client"`); load wavesurfer inside `useEffect` or with `dynamic(..., { ssr: false })`. **[VERIFY]** any other breaking changes against the official docs for the installed version.

### 8.4 Demo mode (the public site has no login)
Anyone with the link could otherwise burn the user's Gnani credits and LLM quota. When `DEMO_MODE=true`:
- `POST /calls/upload`, `POST /calls/{id}/retry`, `POST /calls/{id}/swap-roles`, `POST /eval/run` require header `X-Upload-Passcode` equal to `UPLOAD_PASSCODE` (else `403`). The upload drawer shows a passcode field; keep the entered passcode in `sessionStorage`. The passcode is **not** in the JS bundle.
- Add a per-IP rate limit (e.g. 10 requests/hour) on those endpoints, `MAX_UPLOAD_MB`, and an allow-list of file types checked with `ffprobe`.
- Confirm/Dismiss and rule toggles stay public so judges can try them; `scripts/reset_demo.py` restores the seeded state.
- Seeded calls are pre-processed, so the site works fully without any passcode.

---

## 9. Test dataset and evaluation

### 9.1 The 30 fake calls
Acted out by the user (agent) and a friend (borrower) over a real phone call. 1–3 minutes each.

| Slice | Calls |
|---|---|
| With ≥ 1 violation | 18 |
| Fully compliant | 12 (**at least 4 are "hard negatives"**: firm, strict, mentions a lawful legal notice or credit-bureau reporting, but breaks no rule) |
| Hinglish / Marathi | 22 / 8 |
| Recorded with background noise (traffic, fan, office; noise may be mixed in digitally with ffmpeg) | 8 |
| Logged outside 08:00–19:00 (V1) | 4 |
| `dev` split / `test` split (held out) | 10 / 20, stratified so every rule has at least 1 positive in `dev` and at least 2 in `test` |

**Minimum positives per rule across the 30 calls: 3** (V1: 4). Target distribution: V1 4 · V2 3 · V3 3 · V4 3 · V5 3 · V6 3 · V7 3 · V8 3 · V9 3 = 28 instances in 18 calls (the 4 V1 calls may have no other violation). Marathi calls must include at least one positive for V2, V4 and V5. Include hard cases (`difficulty: "hard"`): indirect threats, sarcasm, a polite agent who still discloses the debt to a relative, a "legal department" agent who is truthful.

### 9.2 Answer key format (`data/answer_keys/call_07.json`)
```json
{
  "test_key": "call_07",
  "split": "test",
  "language": "hinglish",
  "called_time_ist": "21:40",
  "borrower_requested_time": false,
  "noisy": false,
  "is_clean": false,
  "expected_violations": [
    {"rule_code": "V1", "approx_time_s": null, "quote_hint": null, "difficulty": "easy"},
    {"rule_code": "V5", "approx_time_s": null, "quote_hint": "office mein sabko bata denge", "difficulty": "hard"}
  ]
}
```
- Keys store a **time of day only**, not a date. At seed/upload time assign a date inside the last 14 days **preserving the time of day** (V1 depends on it), so the Overview chart looks alive.
- `approx_time_s` is `null` when the key is written (timing is unknown before recording). After recording, the user fills it with `eval/label_times.py`, a small CLI that prints each call's cached transcript with segment numbers and asks which segment contains each expected violation. **[ASK USER]** to run it.

### 9.3 Evaluation harness (`eval/run_eval.py`)
Runs the pipeline on cached transcripts (never re-transcribe), compares with answer keys, and writes `eval_runs` rows (one per configuration: `rules_only`, `rules_plus_llm`) plus `eval/reports/<timestamp>.md`. It records `PROMPT_VERSION` and model names.
- **Matching:** for each call and rule, greedily pair each expected violation with an unmatched predicted one of the same `rule_code`. V1 and V8 match on rule only. For other rules a pair is a **strict TP** only if `|predicted.start_s − approx_time_s| ≤ 5`; if `approx_time_s` is still `null`, match on rule only and note "timestamp unlabelled". Unmatched expected = FN; unmatched predicted = FP. Evaluation ignores `reviewer_status`.
- **Metrics:** strict precision / recall / F1 overall and per rule; `rule_level_recall` (ignoring time); `timestamp_accuracy = strict TP ÷ rule-level TP`; `clean_calls_flagged` (of 12); speaker-role mapping accuracy; and per-slice metrics: all, `dev`, `test`, language, noisy vs not, and (if run) denoise on vs off for the noisy calls.
- **Tuning discipline:** tune lexicons, prompt and thresholds **using `dev` calls only**. Report `test` (held-out) numbers prominently. Never edit answer keys to improve scores.
- **Targets:** overall precision ≥ 85%, recall ≥ 80%, at most 1 of 12 clean calls wrongly flagged. Report real numbers honestly, including failures.
- **Credit budget:** 30 calls × ~2 min ≈ 60 minutes of audio, plus the Phase 2 spike (~16 minutes). **[ASK USER]** to confirm this fits in their 5,000 credits after reading the per-minute cost on their dashboard.

---

## 10. API contract

FastAPI, JSON, **snake_case everywhere** (API and TypeScript types). Times are ISO-8601 with `+05:30` (stored UTC, shown IST). Errors always use `{"error": {"code": "...", "message": "..."}}`. Lists use `Paginated<T> = {items: T[], page: number, page_size: number, total: number}`.

### 10.1 Endpoints

| Method | Path | Purpose / response |
|---|---|---|
| GET | `/health` | `{status:"ok"}` (the web app also uses it to show a "waking up" state) |
| GET | `/stats/overview` | `OverviewStats` |
| GET | `/calls` | `Paginated<Call>`. Query: `page, page_size, q, agent_id, language, status, severity, rule_code, date_from, date_to, sort, order` |
| POST | `/calls/upload` | Multipart `files[]` + `metadata` (JSON array of `UploadMetadata`, same order). Returns `Call[]` (status `queued`) |
| GET | `/calls/{id}` | `CallDetail` |
| GET | `/calls/{id}/audio` | `{url: string, expires_at: string}` (signed URL, or an API file URL for the local backend) |
| POST | `/calls/{id}/retry` | Re-run analysis (reuses cached transcript unless `?retranscribe=true`). Returns `Call` |
| POST | `/calls/{id}/swap-roles` | Swap Agent/Borrower, re-run detection only. Returns `CallDetail` |
| PATCH | `/violations/{id}` | Body `{reviewer_status}`; recomputes scores. Returns `{violation: Violation, call_score: number}` |
| GET | `/agents` | `Agent[]` |
| POST | `/agents` | `{name, team}` → `Agent` |
| GET | `/agents/{id}` | `AgentDetail` |
| GET | `/rules` | `Rule[]` |
| PATCH | `/rules/{code}` | `{enabled: boolean}`; recomputes all scores. Returns `Rule` |
| GET | `/eval/latest` | `{rules_only: EvalRun or null, rules_plus_llm: EvalRun or null}` |
| POST | `/eval/run` | Dev only; header `X-Admin-Token` must equal `ADMIN_TOKEN` |

### 10.2 Shared types (mirror in `web/src/lib/types.ts` and `api/app/schemas.py`)
```ts
type Severity = "critical" | "high" | "medium";
type CallStatus = "queued" | "transcribing" | "analysing" | "done" | "failed";
type Language = "hinglish" | "marathi";
type ReviewerStatus = "open" | "confirmed" | "dismissed";
type DetectedBy = "rules" | "llm" | "both" | "metadata";

interface Agent { id: string; name: string; team: string; calls_count: number; avg_score: number | null;
  critical_count: number; violation_rate: number /* 0..1 */; top_rule_code: string | null; }
interface Call { id: string; test_key: string | null; agent_id: string; agent_name: string; loan_ref: string;
  called_at: string; duration_s: number | null; language: Language; status: CallStatus; score: number | null;
  violations_count: number; max_severity: Severity | null; error: string | null; borrower_requested_time: boolean; }
interface Segment { id: string; index: number; speaker: "agent" | "borrower" | "unknown"; start_s: number; end_s: number; text: string /* masked */; }
interface Violation { id: string; call_id: string; rule_code: string; rule_name: string; severity: Severity;
  segment_id: string | null; quote: string | null; start_s: number | null; explanation: string;
  confidence: number; detected_by: DetectedBy; reviewer_status: ReviewerStatus; }
interface Rule { code: string; name: string; description: string; rbi_reference: string; severity: Severity;
  detection: string; enabled: boolean; }
interface CallDetail extends Call { segments: Segment[]; violations: Violation[]; roles_look_correct: boolean;
  analysis_notice: string | null; transcription: { model: string; language_code: string; format: string | null } | null; }
interface UploadMetadata { filename: string; agent_id?: string; agent_name?: string; called_at: string;
  language: Language; loan_ref: string; borrower_requested_time?: boolean; }
interface OverviewStats { as_of: string; calls_audited: number; calls_with_violations: number; calls_with_violations_pct: number;
  critical_flags: number; avg_score: number | null; calls_pending: number;
  violations_per_day: { date: string; critical: number; high: number; medium: number }[]; /* last 14 days, oldest first */
  top_rules: { rule_code: string; rule_name: string; count: number; pct_of_calls: number }[];
  agents_needing_review: { agent_id: string; agent_name: string; calls: number; avg_score: number; critical_flags: number }[];
  recent_critical: { violation_id: string; call_id: string; agent_name: string; called_at: string; rule_code: string;
    rule_name: string; quote: string | null; start_s: number | null }[]; }
interface AgentDetail extends Agent { score_trend: { date: string; avg_score: number; calls: number }[];
  violations_by_rule: { rule_code: string; rule_name: string; count: number }[]; calls: Call[]; }
interface PRF { precision: number; recall: number; f1: number; }
interface EvalRun { id: string; run_at: string; config: "rules_only" | "rules_plus_llm"; prompt_version: string;
  models: { stt: string; llm: string }; n_calls: number; overall: PRF; rule_level_recall: number; timestamp_accuracy: number;
  clean_calls_flagged: number; clean_calls_total: number; role_mapping_accuracy: number;
  per_rule: Record<string, PRF & { tp: number; fp: number; fn: number }>;
  per_slice: Record<string, PRF & { n_calls: number }>; /* keys: all, dev, test, hinglish, marathi, noisy, not_noisy */
  failures: { test_key: string; rule_code: string; kind: "fp" | "fn"; note: string }[]; }
```
The Phase 1 `mockClient` **must return exactly these shapes**, so Phase 4 is a swap, not a rewrite.

---

## 11. Data model

Defined once with **SQLAlchemy 2.0 models + Alembic migrations** (SQLite locally, Postgres on Supabase). The models must produce a schema equivalent to this reference SQL. Use generic types (`Uuid`, `JSON`, `DateTime(timezone=True)`) so both databases work.

```sql
create table agents (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  team text not null default 'Collections',
  created_at timestamptz not null default now()
);

create table rules (
  code text primary key,                       -- 'V1'..'V9'
  name text not null,
  description text not null,
  rbi_reference text not null,
  severity text not null check (severity in ('critical','high','medium')),
  detection text not null,                     -- 'metadata' | 'rules+llm' | 'llm'
  enabled boolean not null default true
);

create table calls (
  id uuid primary key default gen_random_uuid(),
  test_key text unique,                        -- 'call_07' for the labelled test set, else null
  agent_id uuid not null references agents(id),
  loan_ref text not null,
  called_at timestamptz not null,
  borrower_requested_time boolean not null default false,
  duration_s numeric,
  language text not null check (language in ('hinglish','marathi')),
  audio_path text not null,
  status text not null default 'queued' check (status in ('queued','transcribing','analysing','done','failed')),
  error text,
  score numeric,
  gnani_job_id text,
  transcription_config jsonb,                  -- exact config sent to Gnani
  raw_transcript jsonb,                        -- cached Gnani output; SERVER-ONLY, never returned by the API
  agent_speaker_id int,
  roles_look_correct boolean not null default true,
  analysis_meta jsonb not null default '{}',   -- llm_provider_used, llm_failed, prompt_version, timings
  is_test_set boolean not null default false,
  created_at timestamptz not null default now(),
  processed_at timestamptz
);

create table segments (
  id uuid primary key default gen_random_uuid(),
  call_id uuid not null references calls(id) on delete cascade,
  idx int not null,
  speaker text not null check (speaker in ('agent','borrower','unknown')),
  start_s numeric not null,
  end_s numeric not null,
  text text not null                           -- MASKED text only
);

create table violations (
  id uuid primary key default gen_random_uuid(),
  call_id uuid not null references calls(id) on delete cascade,
  rule_code text not null references rules(code),
  segment_id uuid references segments(id),
  quote text,
  start_s numeric,
  explanation text not null default '',
  confidence numeric not null default 1.0,
  detected_by text not null check (detected_by in ('rules','llm','both','metadata')),
  reviewer_status text not null default 'open' check (reviewer_status in ('open','confirmed','dismissed')),
  created_at timestamptz not null default now()
);

create table eval_runs (
  id uuid primary key default gen_random_uuid(),
  run_at timestamptz not null default now(),
  config text not null check (config in ('rules_only','rules_plus_llm')),
  prompt_version text not null,
  models jsonb not null,
  n_calls int not null,
  overall jsonb not null,                      -- {precision, recall, f1}
  rule_level_recall numeric,
  timestamp_accuracy numeric,
  clean_calls_flagged int,
  clean_calls_total int,
  role_mapping_accuracy numeric,
  per_rule jsonb not null,
  per_slice jsonb not null,
  failures jsonb not null default '[]'
);

create table llm_cache (
  key text primary key,                        -- sha256(provider, model, prompt_version, system, user)
  response jsonb not null,
  created_at timestamptz not null default now()
);

create index on calls (agent_id);
create index on calls (called_at desc);
create index on calls (status);
create index on violations (call_id);
create index on violations (rule_code);
create index on segments (call_id, idx);
```
- Storage bucket `call-audio` is **private**; the API issues signed URLs (~1 hour).
- **RLS:** enable RLS on every table with **no public policies**. Only the API connects (service role / direct connection). The web app never talks to Supabase.
- Timestamps are stored in UTC; V1 is computed in IST.

---

## 12. Build phases

> Work in this exact order. At the **start** of each phase send one message listing everything you need from the user (the **[ASK USER]** list). At the **end**, run every acceptance check, summarise, and wait for approval.

### Phase 0 — Setup and test material
**Goal:** repo skeleton and the 30 scripts with answer keys, so the user can record while you build.

Tasks
1. Create the structure in Section 8.1, `.gitignore`, `.env.example` files, root README stub, `docs/decisions.md`. Run `git init` and make the first commit.
2. Write **`data/scripts/call_01.md … call_30.md`** per Section 9: fake lender "Sahyog Finance"; fake agent and borrower names; fake loan ref (`SF-PL-######`); language; intended call time; noise instruction; dialogue with the violations embedded naturally. Each script is 250–450 spoken words (1.5–3 minutes), with fillers, interruptions and realistic borrower excuses. Hinglish in Latin script; Marathi in Devanagari with a Latin transliteration beneath. See Appendix A for the expected quality. Violation lines must be unambiguous enough that a human reader would agree they break the rule.
3. Write the matching **`data/answer_keys/call_XX.json`** (Section 9.2) with `approx_time_s: null`. Check the totals against the Section 9.1 table and print a coverage report (`data/COVERAGE.md`).
4. Write **`data/RECORDING_GUIDE.md`**: how to record (a real phone call on speaker or a call-recorder app; or each person records their own side so a stereo/multi-channel file can be tested), file naming `call_01.m4a`, keep under 25 MB, how to add noise with ffmpeg, where files go, how to run `eval/label_times.py` later.

**[ASK USER]:** operating system and whether Node 20.9+, Python 3.11+, ffmpeg and git are installed; GitHub repo to use (if any); whether the friend playing the borrower speaks Marathi; whether separate-channel recording is possible.

**Acceptance:** structure exists; 30 scripts and 30 keys exist and agree with each other; the coverage report matches Section 9.1 (≥ 3 positives per rule, dev/test split stratified); user confirms the scripts are actable.

### Phase 1 — Frontend (Next.js, mock data only)
**Goal:** the complete, polished UI for every page in Section 4, running on realistic mock data with no backend.

Requirements
1. Scaffold with `npx create-next-app@latest web --typescript --tailwind --eslint --app --src-dir`, then `npx shadcn@latest init`. Add: next-themes, lucide-react, Recharts, wavesurfer.js, TanStack Table, date-fns (IST formatting). Respect Section 8.3.
2. Build the **design system first**: theme tokens (Section 3.2), typography, badge components (severity, status, score), table styles, skeleton/empty/error components, app shell (Section 3.3). Follow Section 3 strictly.
3. **Data layer:** `lib/api/client.ts` exports one interface (`getOverview, listCalls, getCall, getAudioUrl, uploadCalls, retryCall, swapRoles, updateViolation, listAgents, createAgent, getAgent, listRules, updateRule, getLatestEval`) returning the Section 10 types. Implement `mockClient` with small artificial latency so loading states are visible. Pick the client via `NEXT_PUBLIC_DATA_SOURCE`. **Pages and components import only from `lib/api`** — never from `lib/mock`.
4. **Mock data (`lib/mock/`):** 6 agents (e.g. Rohit Patil, Sneha Kulkarni, Imran Shaikh, Pooja Yadav, Aakash Verma, Kavita Joshi), ~60 calls over the last 14 days with believable times (some after-hours), ~6 calls with full transcripts (5 Hinglish, 1 Marathi) and violations at real timestamps, all 9 rules, and an `EvalRun` for both configurations with plausible numbers and failure cases. Generate 2–3 placeholder audio files with ffmpeg (a tone or silence of the right length) so the player works.
5. Build all pages and states from Section 4. The upload drawer works against the mock (rows go Queued → Transcribing → Analysing → Done over ~15 s; passcode field shown when a mock flag is on). Evidence page has print CSS.
6. QA: keyboard navigation, focus rings, contrast in both themes, `aria-label`s on icon buttons.

**[ASK USER]:** after finishing, show screenshots (Overview, Calls, Call detail, Accuracy in light and dark; use a headless browser if available, otherwise ask the user to run `npm run dev`) and ask for design feedback. Ask whether they want a different accent colour. (The product name is fixed: **Samaritan**.)

**Acceptance**
- `npm run build` and `npm run lint` pass with zero errors; TypeScript strict.
- Every route renders in both themes with no layout breaks at 1280 px.
- Clicking a transcript line seeks the audio; clicking a violation seeks to its timestamp.
- Nothing from Section 3's forbidden list appears.
- No page or component imports `lib/mock` directly.

### Phase 2 — Backend & APIs (FastAPI, Gnani, LLM, detection, evaluation)
**Goal:** a working API implementing Section 10, the full processing pipeline (Sections 6–7) and the evaluation harness, on **SQLite and local file storage**.

Work in these steps:
- **2.1 Skeleton.** FastAPI app, config loading, structured logging (no secrets), CORS, the error envelope, SQLAlchemy models + Alembic migration for Section 11, seed the 9 rules, local storage backend, Pydantic schemas mirroring Section 10.
- **2.2 Gnani client + feasibility spike.** Implement `gnani_client.py` per Section 7 (httpx, retries, error normalisation, caching) and a CLI: `python -m app.cli transcribe data/audio/call_01.m4a --language hinglish --config A`. Build `tests/fakes/gnani_fake.py`, a tiny fake server implementing create/start/status/files/transcript, and use it in all tests. **Then run the spike** (with the user's approval and key): take **2 Hinglish and 1 Marathi** real recordings (include one noisy one) and run a few configurations — A: v3.0 `hi-IN,en-IN` `transcribe`; B: v3.0 `codemix`; C: v2.5 `en-IN` (Marathi: `mr-IN`); D: A + `with_denoise` on the noisy file; optionally E: A + `keyterms`. Inspect: transcript quality on a few lines (ask the user to judge), which script each word comes out in, whether speakers are separated correctly, and the multi-channel behaviour if a stereo file exists. Write `docs/gnani-findings.md`, **[DECIDE]** the default configuration, and set the env vars.
- **2.3 Audio prep** (Section 7.6) with tests.
- **2.4 Detection Layer 1.** Normalisation, role mapping, PII masking, lexicons (from Appendix B), V1 and V8 logic, with unit tests in both scripts.
- **2.5 Detection Layer 2.** LLM providers, limiter, cache, judge, evidence verification, merge, scoring, tests using canned LLM responses. Then one real smoke test on a single transcript. **Measure the real token usage** and adjust `LLM_*` limits.
- **2.6 Pipeline, worker and endpoints.** Section 6.6 (idempotent, resume on startup), every endpoint in Section 10, demo-mode guards (Section 8.4), swap-roles, recomputing scores on reviewer actions and rule toggles.
- **2.7 Evaluation harness.** `eval/run_eval.py`, `metrics.py`, `label_times.py` per Section 9.3, with unit tests for the metric maths on hand-made examples.
- **2.8 First real evaluation** on the calls available so far, after the user approves the credit spend.

**[ASK USER]** (at phase start): Gnani API key (they put it in `api/.env`); a screenshot or notes from the Gnani dashboard: credits per audio minute, rate limits, and whether Batch accepts `prisma-v3.0` on their account; Groq API key and the list of models their console shows; Gemini API key and model name; **permission before the first real Gnani call and before transcribing the full test set**; the recordings in `data/audio/` (at least 5 to start, all 30 before the final run); whether to draft RBI references; time-labelling session for `eval/label_times.py`.

**Acceptance**
- `pytest` and `ruff` pass. Tests never touch real Gnani or LLM endpoints.
- `uvicorn app.main:app` runs; every endpoint matches the contract (check `/docs`).
- One real recording goes Queued → Done with separated speakers, masked text and sensible violations.
- Killing the server mid-job and restarting resumes the call without creating a second Gnani job.
- The eval harness produces metrics for both configurations on the available calls.
- `docs/gnani-findings.md` exists. No secret appears in logs, API responses or git history.

### Phase 3 — Database (Supabase)
**Goal:** move persistence and audio to Supabase with proper migrations, security and seed data. The API code should not change except through `DATABASE_URL` and `STORAGE_BACKEND`.

Requirements
1. Apply the Alembic migrations to the Supabase Postgres. For hosts that only support IPv4 (e.g. Render free tier) use Supabase's **pooler connection string**, not the direct one **[VERIFY]** in the project's Connect dialog.
2. `supabase/rls_and_storage.sql`: enable RLS on all tables with no public policies; create the private `call-audio` bucket.
3. `storage/supabase.py` implementing the storage interface with signed URLs (~1 hour).
4. `scripts/seed.py`: the 9 rules; the 6 agents; the processed test-set calls with their audio uploaded to the bucket (`is_test_set = true`, dates assigned inside the last 14 days preserving time of day); the latest eval runs. **[ASK USER]** before inserting anything that was not actually processed by the pipeline.
5. `scripts/migrate_local_to_supabase.py` copies local data without re-transcribing (reuse `raw_transcript` and `llm_cache`). `scripts/reset_demo.py` restores the seeded state.
6. Aggregations for `/stats/overview` and the agent pages may be SQL or Python — the dataset is small; choose the simpler.

**[ASK USER]** (at phase start): create a Supabase project (free plan; prefer region Mumbai `ap-south-1`); put `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` and `DATABASE_URL` (pooler string) in `api/.env`; permission before running migrations and seeds.

**Acceptance**
- Migrations apply cleanly on a fresh project and the Phase 2 tests still pass.
- With `STORAGE_BACKEND=supabase` and the Postgres `DATABASE_URL`, every endpoint returns the same shapes as before.
- Audio lands in the private bucket and plays through a signed URL.
- The anon key cannot read any table; the public cannot list the bucket.

### Phase 4 — Integration, deployment, submission
**Goal:** the real app end to end, deployed, with real accuracy numbers and submission material.

Requirements
1. Implement `httpClient` in `web/src/lib/api/` against the real API and set `NEXT_PUBLIC_DATA_SOURCE=api` for production (keep `mockClient` for offline development).
2. Real upload flow: multipart upload with per-file progress, passcode handling in demo mode, polling every 5 s until terminal status, success/failure toasts.
3. Real audio via signed URLs; waveform markers from real violations; Confirm/Dismiss and rule toggles update scores live.
4. Run the full pipeline on all 30 test calls, then the evaluation in both configurations (and the denoise comparison on the noisy calls). Tune using **dev calls only**, re-run after each change, keep the best run, and write "Known failure cases" honestly. The Accuracy page shows the real numbers.
5. Show a friendly "API is waking up…" state when `/health` is slow (free hosts sleep).
6. Deploy: the API from `api/Dockerfile` (python:3.11-slim + ffmpeg) to Render or Railway; the web app to Vercel. Set env vars in each dashboard (`DEMO_MODE=true`, `UPLOAD_PASSCODE`, `CORS_ORIGINS` = the Vercel domain). Verify the live site end to end, including a real upload with the passcode.
7. A short end-to-end smoke test (`scripts/smoke.py` or Playwright): health, list calls, open a call, fetch the Accuracy data, upload with passcode.
8. Write `README.md`: what it is, a Mermaid architecture diagram, local run steps for web and API, env vars, how evaluation works, the results table, limitations, future work.
9. Create `submission/`:
   - `demo_script.md` — a 60-second video script: hook with the ₹ fine stat → upload a call → a flagged moment with quote and RBI rule → agent scorecard → Accuracy page → the one-line pitch.
   - `project_explanation.md` — problem, users, how it works, Gnani models used (Prisma STT, Batch API with speaker separation), what we built ourselves, results, limitations, future work.
   - `social_post.md` — LinkedIn and X drafts with **#GnaniAI**, **#GreatIndianAIInternshipChallenge** and a tag to Gnani AI.

**[ASK USER]** (at phase start): Vercel and Render/Railway accounts (the user sets env vars in the dashboards themselves); the demo passcode they want; the submission form fields Gnani emailed them so the explanation matches; review of the demo script, explanation and post drafts before they record and post (post early so it can gather engagement).

**Acceptance**
- Live URL: upload a new recording with the passcode and see correct flags within a few minutes.
- The Accuracy page shows the latest real evaluation (both configurations, held-out split visible).
- `npm run build`, `npm run lint`, `pytest`, `ruff` pass; no secrets in the repository or history.
- README, demo script, explanation and post drafts exist and the user has approved them.

---

## 13. Rules for the coding agent
1. Follow the phases in order; ask for everything you need at the start of each phase; stop for review at the end.
2. Ask the user instead of guessing keys, credentials, account settings or undocumented API behaviour. Re-check docs.gnani.ai before writing the Gnani client.
3. Never put secrets in code, logs, commits, screenshots or chat.
4. Synthetic data only.
5. Protect credits and quotas: cache transcripts and LLM responses, use the fake Gnani server in tests, ask before any bulk run.
6. Keep the design rules in Section 3 at all times; when unsure, choose the plainer option.
7. Keep `web/src/lib/types.ts` and `api/app/schemas.py` in sync with Section 10.
8. Prefer small, well-named modules and readable code. Comment only where the logic isn't obvious.
9. Report honestly. If accuracy targets are missed, show the real numbers and explain the failures. Never tune on the held-out split and never edit answer keys to raise scores.
10. If something in this file is wrong or impossible, say so, propose the fix, record it in `docs/decisions.md`, and continue.

---

## Appendix A — Example script quality (Hinglish; fictional people)
A compliant opening and a V5 violation. Real scripts should be longer, with fillers and interruptions.
```
[Agent: Rohit Patil | Borrower: Anil Kumar | Loan: SF-PL-204871 | Time: 11:20 | Quiet]
AGENT: Namaste, main Rohit Patil bol raha hoon Sahyog Finance se. Kya meri baat Anil Kumar ji se ho rahi hai?
BORROWER: Haan ji, boliye.
AGENT: Sir, aapke personal loan ki EMI das din se pending hai, paanch hazaar paanch sau rupaye. Kab tak ho payega?
BORROWER: Is mahine thoda tight hai yaar, agle hafte tak kar dunga.
AGENT: Agle hafte kaunsa din pakka rahega?
BORROWER: Shukrawar tak.
AGENT: Theek hai sir, Shukrawar tak ho jaye toh aage koi dikkat nahi. Main note kar leta hoon.

--- V5 variant (violating lines, same call otherwise) ---
AGENT: Dekhiye sir, kal tak payment nahi aaya toh main aapke office mein HR ko call karke sabko bata dunga ki aap defaulter ho.
```
Expected key entry: `{"rule_code":"V5","quote_hint":"office mein HR ko call karke sabko bata dunga","difficulty":"easy"}`.

## Appendix B — Starter lexicon seeds (expand; cover Devanagari, Latin and common spellings)
Mark each entry `strong` or `weak`. These are seeds, not a finished list.
- **V2 (abusive):** strong — common Hindi/Marathi profanity and slurs (build from a standard list, both scripts); weak — "chor", "चोर", "bewakoof", "नालायक", "nalayak", "dhokhebaaz", "fraud", "haramkhor", "kamina".
- **V3 (force):** weak — "ghar aake", "घर आकर", "ghar pe aa", "dekh lenge", "देख लेंगे", "todenge", "तोड़", "goonde", "गुंडे", "recovery wale bhej", "घरी येऊन", "बघून घेऊ"; strong — regexes combining a visit with a menace verb.
- **V4 (false legal threat):** weak — "police", "पुलिस", "पोलीस", "FIR", "एफआईआर", "jail", "जेल", "तुरुंग", "arrest", "giraftar", "गिरफ्तार", "अटक", "warrant", "वारंट", "thana", "थाना"; strong — "kal police aa", "jail bhej denge", "arrest kara denge".
- **V5 (shaming):** weak — "office", "ऑफिस", "boss", "HR", "rishtedar", "रिश्तेदार", "padosi", "पड़ोसी", "society", "WhatsApp group", "badnaam", "बदनाम", "ऑफिसमध्ये"; strong — "sabko bata denge", "सबको बता देंगे", "सगळ्यांना सांगू".
- **V6 (third party):** weak only — phrases like "unka loan", "aapke bete ka loan", "unhe bata dena ki loan"; mostly judged by the LLM.
- **V7 (impersonation):** weak — "court se", "कोर्ट से", "advocate", "वकील", "CBI", "RBI se", "legal department se"; strong — "police se bol raha", "main court se".
- **V8 (introduction):** patterns — "main … bol raha/rahi hoon", "mera naam", "मेरा नाम", "calling from", "से बोल रहा", "से बोल रही"; lender aliases from `workspace.yaml`.
- **V9 (pressure):** weak — "abhi ke abhi", "अभी के अभी", "warna", "वरना", "last warning", "aakhri mauka", "dekh lena", "नाहीतर".

## Appendix C — Known risks and fallbacks

| Risk | What to do |
|---|---|
| Gnani gives no usable speaker separation for a file | Use `is_multi_channel` with per-speaker channels, or label by turn order and rely on the "Swap roles" button |
| Marathi transcription is weak | Report Marathi accuracy separately and honestly; keep Hinglish as the headline demo |
| Hindi comes out in Devanagari and lexicons miss it | Add Devanagari variants; make the LLM judge the final authority |
| Groq daily token cap reached | Switch to Gemini for the rest of the day; rely on the response cache |
| Credits run low | Stop bulk runs, ask the user, reuse cached transcripts |
| Free hosting sleeps and loses an in-flight job | Resume-on-startup (Section 6.6) and the "waking up" UI state |
| Strangers abuse the public upload | Demo mode passcode and rate limits (Section 8.4) |
| Recording all 30 calls takes longer than planned | 20 calls is the minimum viable set; keep ≥ 3 positives for the rules that matter most (V2, V4, V5) |
| The idea resembles existing compliance products | Lead with Hinglish/Marathi implied-threat detection, RBI rule mapping, and our published accuracy numbers |
