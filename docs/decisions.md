# Decisions

Every [DECIDE] choice and every conflict between plan.md and reality is recorded here, newest last.

## D-001 — The `Gnani/` folder is the repository root
- **Context:** plan.md Section 8.1 draws the tree under `samaritan/`. The working folder is `Gnani/` and already holds plan.md and architecture.md at its top level.
- **Decision:** `Gnani/` is the root; no extra `samaritan/` folder. Layout inside it follows Section 8.1 exactly.

## D-002 — Extra fields in answer keys
- **Context:** Section 9.2 fixes the key format, but the coverage report must count hard negatives and the checker must know which script lines carry each violation.
- **Decision:** keys keep every field in Section 9.2 and add two optional ones: `hard_negative` (bool, for clean calls that are deliberately tricky) and `notes` (short text, for humans). The eval harness may ignore both.

## D-003 — Script markers for violating lines
- **Context:** Section 9 requires scripts and keys to agree. A human can't verify that by eye across 30 files.
- **Decision:** in each script, a spoken line that breaks a rule ends with a marker like `<<V5>>`. `scripts/check_testset.py` verifies that the markers match `expected_violations` and that each `quote_hint` is a substring of its marked line. V1 (call time) and V8 (missing introduction) have no quote: V1 comes from the header time, V8 is marked on the agent's opening line. The markers are annotations for the person acting; they are never spoken. See `data/RECORDING_GUIDE.md`.

## D-004 — Marathi quote hints are in Devanagari
- **Context:** Gnani returns Marathi in Devanagari; scripts also carry a Latin transliteration for the actors.
- **Decision:** `quote_hint` for Marathi calls is the Devanagari phrase from the script, since that is what the transcript will contain.

## D-005 — Toolchain gaps found on 2026-11-01
- macOS system `python3` is 3.9.6; the API needs 3.11+. `ffmpeg`/`ffprobe` are not installed. Homebrew is available. Neither blocks Phase 0 or Phase 1; both must be fixed before Phase 2.

## D-006 — How the 30 calls are allocated
- **Context:** Section 9.1 fixes the totals but not which call is which.
- **Decision:** the allocation lives in the answer keys and is summarised in `data/COVERAGE.md`. Dev split = calls 01, 02, 05, 06, 09, 11, 16, 20, 22, 26 (6 with violations, 4 clean). Every rule has exactly 3 positives (V1 has 4), 1 in dev and 2 or 3 in test. Seven of the 12 clean calls are hard negatives (minimum was 4): lawful legal-notice language, a truthful legal-desk agent, an after-hours call the borrower requested, a call at exactly 19:00, a third-party call-back message, a co-borrower conversation, and firm repeated date requests. Four violation instances are tagged `hard` (sarcasm, indirect threats, a polite disclosure). Call 07 is the Section 9.2 example (V1 + hard V5).
- **Rule for scripts:** each marked line is the single violating moment for its key entry. Other lines were kept deliberately benign so the evaluation does not penalise correct detections as false positives.

## D-007 — Marathi word counts
- **Context:** Section 9 asks for 250-450 spoken words per script. Marathi packs more meaning per word than Hinglish, so a 1.5-3 minute Marathi call is fewer words.
- **Decision:** the 250-word minimum is applied to spoken Devanagari words only (Latin transliteration lines are excluded). The Marathi scripts are 255-273 words, which likely lands near 1.5 minutes. If recordings come out shorter than 1.5 minutes, lengthen the scripts rather than lowering the minimum.

## D-008 — next-themes replaced by a small theme provider
- **Context:** plan.md Section 12 lists next-themes. It renders an inline `<script>` from a Client Component, which React 19 reports as a console error on every load.
- **Decision:** `web/src/components/theme-provider.tsx` provides `useTheme` (light, dark, system; kept in localStorage), and the no-flash script is rendered from the root layout, a Server Component, as the Next.js "preventing flash before hydration" guide describes. `next-themes` was uninstalled. Behaviour is the same: a toggle in the sidebar, system preference by default.

## D-009 — Accent text and filled buttons in dark mode
- **Context:** plan.md Section 3.2 gives the dark accent as `#3B82F6`. White text on it is 3.7:1 and the accent on `#172554` (selected row) is 4.0:1, both below WCAG AA for 12-14 px text, which Section 3.1 requires.
- **Decision:** `#3B82F6` stays the accent for lines, focus rings, waveform progress and icons. Filled buttons use `#2563EB` in dark (white on it is 5.2:1). Accent-coloured text on the subtle background uses a new token `--brand-text` (`#93C5FD` in dark, 8.2:1; same as the accent in light). All other pairs were measured at 4.5:1 or better.

## D-010 — Next.js 16 with Cache Components
- **Context:** the installed Next.js (16.4.3) scaffolds with `cacheComponents` and `partialPrefetching` on, and its docs warn that APIs differ from earlier versions.
- **Decision:** kept the scaffold defaults. List pages are static shells that fetch in the browser. Pages with a dynamic id (`/calls/[id]`, `/calls/[id]/evidence`, `/agents/[id]`) read `params` inside `<Suspense>` and export `instant = false`, because the sidebar's `usePathname()` cannot be resolved at build time for unknown ids. Views using `useSearchParams` sit inside `<Suspense>`. The sidebar's active link is styled from `aria-current` so its class string is the same on server and client.

## D-011 — UI library notes
- shadcn's current CLI generates the `base-nova` style, built on Base UI rather than Radix (triggers take a `render` prop, not `asChild`), and imports `cn` from shadcn's own `cn` package. Both were accepted as generated.
- TanStack Table is v9 (`useTable`, `tableFeatures`). Only the core row model is used for rendering; sorting and paging are API parameters, as in plan.md Section 10, so the table never re-sorts data itself.
- Generated shadcn components were edited to follow Section 3: the off-scale 13 px size became 12 px, and the backdrop blur on dialog and sheet overlays was removed.

## D-012 — Semantics fixed by the Phase 1 mock (the real API must match)
- `OverviewStats.calls_with_violations_pct` is a percentage from 0 to 100; `Agent.violation_rate` is a fraction from 0 to 1 (as plan.md states).
- `OverviewStats.critical_flags` counts non-dismissed critical flags on finished calls in the last 14 days. `calls_audited` counts finished calls; `calls_pending` counts queued, transcribing and analysing calls.
- A call's score, `violations_count` and `max_severity` count only non-dismissed violations of enabled rules. `CallDetail.violations` includes dismissed ones (shown greyed) but hides violations of disabled rules.
- V8 violations have `start_s = 0` and no quote; V1 violations have `start_s = null`.
- Mock demo mode: upload, retry and swap-roles need a passcode (`demo123`, shown in the UI only when the client is the mock). Set `NEXT_PUBLIC_MOCK_DEMO_MODE=false` to turn it off.
- The mock's evaluation figures are illustrative and internally consistent (slices sum to the totals); the Accuracy page says so while the mock client is active. Real figures come in Phase 4.
- Mock state lives in memory and resets on a full page reload.

## D-013 — Placeholder audio
- ffmpeg is not installed, so `scripts/make_placeholder_audio.py` writes three synthetic speech-shaped tone files (105, 140 and 180 s, 8 kHz 8-bit WAV, 3.4 MB in total) to `web/public/audio/`. They contain no speech. The six featured mock calls use durations that match these files exactly.

## D-014 — RBI references are drafted but unverified
- **Context:** plan.md Section 5.2 asks whether to draft clause references; the user said yes. RBI's site blocks automated access behind a CAPTCHA, which was not bypassed, and the secondary sources disagree on some points (see `docs/rbi-references.md`).
- **Decision:** the nine `rbi_reference` strings now name the likely RBI documents and the topic instead of a bare placeholder, but contain no invented paragraph numbers and keep the `Clause: [to verify]` marker. The user can save the primary PDFs into `docs/rbi-sources/` or paste paragraphs to close the gap.

## D-015 — Toolchain installed
- On the user's approval, Homebrew installed `python@3.11` (3.11.18, at `/opt/homebrew/bin/python3.11`) and `ffmpeg` (9.0.2, with ffprobe). The API venv must be created with `python3.11`. This resolves D-005.

## D-016 — Credit budget is not a constraint
- **Context:** plan.md Section 9.3 asks to confirm the 5,000 credits cover the run.
- **Decision:** the dashboard shows STT at ₹20 per hour and 1 credit = ₹1, so the whole plan costs about 25 credits. The rule "ask before any bulk run" (Section 0, rule 7) still applies, but the spike can try several configurations freely. `GNANI_MAX_CONCURRENT` stays 1 because Gnani allows one active request at a time. See `docs/gnani-findings.md`.

## D-017 — Gemini model is gemini-3.5-flash
- **Context:** I first recommended `gemini-2.5-flash` because it was in the key's model list. Calling it returned 404 (retired for new accounts). See `docs/llm-findings.md`.
- **Decision:** `GEMINI_MODEL=gemini-3.5-flash`, tested through the real provider code. The corrected recommendation was passed to the user.

## D-018 — LLM layer choices
- Groq runs with `reasoning_effort: low` (completion tokens fell from 1,257 to 429); if a model rejects that option or `response_format` the provider drops it once and carries on.
- The env limits (`LLM_RPM_LIMIT`, `LLM_TPM_LIMIT`) apply to the primary provider; the fallback gets Gemini-sized defaults (10 requests and 200,000 tokens a minute).
- The merge step collapses the same rule flagged on neighbouring segments into one violation (highest confidence, preferring `both`). plan.md does not say this; it avoids counting one threat twice as a false positive.
- Layer 1 lexicons were seeded from plan Appendix B and the dev-split scripts only. The author of the lexicons had also written the held-out test scripts and had seen them, so some unconscious leakage is possible; the held-out numbers must be read with that in mind.

## D-019 — Original upload is stored; conversion happens in the pipeline
- **Context:** plan.md does not say whether the stored audio is the upload or the converted file Gnani receives.
- **Decision:** the upload is validated at the endpoint and stored unchanged (the browser plays it back); `prepare_for_gnani` converts a temporary copy inside the pipeline, so a conversion bug never costs the original.

## D-020 — Swap roles is a stored override, re-run without Gnani
- `POST /calls/{id}/swap-roles` writes `agent_speaker_override` into `calls.analysis_meta` and re-runs `analyse_call` on the cached transcript. The override survives re-analysis. Reviewer decisions are kept across re-analysis by matching rule and segment index.

## D-021 — No write transaction across an LLM call
- **Context:** the LLM cache writes through its own session. The pipeline held an open write transaction (the agent speaker id) when the judge ran, so on SQLite the cache insert waited 30 s and failed with "database is locked".
- **Decision:** `analyse_call` commits before the judge runs. A test (`test_pipeline.py`) exercises this path with the real cache.

## D-022 — Demo guard and rate limit
- The passcode and per-IP limit (10 requests an hour, in memory) protect upload, retry and swap-roles. With `DEMO_MODE=true` and no passcode configured every protected call is refused. The limiter resets on restart, which is acceptable for one small instance.

## D-023 — Evaluation code lives in the API package
- **Context:** plan.md puts `metrics.py`, `run_eval.py` and `label_times.py` in a top-level `eval/` folder, but `POST /eval/run` must call the same code.
- **Decision:** the logic is in `api/app/evaluation/` (keys, metrics, runner, report, labelling, ingest, cli). `eval/run_eval.py` and `eval/label_times.py` are thin wrappers that put `api/` on the path; reports go to `eval/reports/`. Run them with the API's virtualenv.
- **Details:** `rules_only` and `rules_plus_llm` use the same cached transcripts and always have all nine rules enabled, whatever a reviewer toggled. V1 is judged from the answer key's time of day on the call's own date. If the LLM is unreachable for any call, `rules_plus_llm` is not recorded (a half rules-only run would flatter or punish it falsely) and the report says so. Undefined ratios (nothing predicted, nothing expected) are 0.0 and the report prints "n/a".
- **Role-mapping truth:** answer keys have no speaker labels. `label_times.py` can add `agent_speaker_id` to a key (optional field, like D-002). Until labelled, the truth is "the first speaker is the agent", because every script opens with the agent; the report states which basis was used. This is partly the same signal the heuristic uses, so treat unlabelled role accuracy as optimistic.
- **Ingest:** `python eval/run_eval.py ingest` registers `data/audio/call_NN.*` as test calls (agent and loan reference from the script header, dated yesterday at the key's time) and asks before sending anything to Gnani, showing minutes and the credit estimate.

## D-024 — Web talks to the API through `httpClient`; demo mode is a build flag
- **Context:** the ApiClient interface needs `demoMode` synchronously, and plan.md keeps `/health` as `{status:"ok"}`.
- **Decision:** `NEXT_PUBLIC_DATA_SOURCE=api` selects `lib/api/httpClient.ts` (`mock` stays the default for offline work). `NEXT_PUBLIC_DEMO_MODE=true` (set in the Vercel dashboard together with the API's `DEMO_MODE=true`) shows the passcode fields; the passcode itself is never in the bundle. If the two flags disagree the API still answers 403 with a clear message. Uploads use XMLHttpRequest because `fetch` cannot report upload progress; progress per file is derived from bytes sent. `ApiStatus` shows "The server is waking up" when `/health` is slow and reloads the page once the API answers.

## D-025 — Dev server on fakes
- `python -m app.devserver` (or the `api-dev` launch entry) runs the real API with the fake Gnani and a canned LLM, in `api/.data/dev/`. It lets the web app be developed and demonstrated without keys or credits. Every upload "transcribes" the same short conversation containing one threat. It is not used in production.

## D-026 — Dockerfile
- `api/Dockerfile` (python:3.11-slim plus ffmpeg) installs the package editable so `alembic/`, `alembic.ini` and the YAML config stay next to the code. Docker is not installed on this Mac, so the image itself has not been built; the same steps were run in a clean virtualenv and the API booted and migrated. The first real build happens on the host.

## D-027 — Supabase code is built and tested without a Supabase project
- **Context:** Phase 3 was started early because it does not depend on recordings.
- **Decision:** Storage uses the Storage REST API through httpx (no SDK), with endpoints taken from supabase-js's source and tested against a fake. The database is plain Postgres through `psycopg` 3; `postgresql://` URLs are rewritten to the driver, prepared statements are off (the pooler runs in transaction mode) and the pool is small (5 plus 5). `pgserver` (a throwaway local Postgres, dev dependency) runs the whole suite on a real Postgres with `TEST_PG=1 pytest`; both SQLite and Postgres pass. The lock-down SQL (`supabase/rls_and_storage.sql`) was run on that Postgres against stand-ins for the `anon` and `authenticated` roles and the `storage` schema.
- **Not verified against real Supabase:** the signed-URL response shape, the bucket insert into `storage.buckets` and role names on Supabase itself. Each is the documented behaviour but was only exercised against stand-ins. The first run on the real project is the proof; the seed scripts are dry-run by default for that reason.
- Postgres migrations are never applied at start-up: `python -m app.migrate` does it, and the API refuses to start on an empty Postgres with that instruction.

## D-028 — Seeding rules
- `seed.py` adds the nine rules and the six roster agents (three names come from the scripts, three from the Phase 1 mock) and, with `--from-local`, copies only test-set calls that were really processed, with their transcripts, violations and audio, redated into the last 14 days at the same time of day. It never invents a call. Evaluation runs copied are the latest of each configuration.
- `reset_demo.py` removes uploads and their audio, clears reviewer decisions, switches every rule back on and removes agents with no calls who are not on the roster. A test-set call whose roles a visitor swapped is analysed again from its cached transcript (no Gnani; the LLM answer is cached when the prompt matches, otherwise one LLM call).

