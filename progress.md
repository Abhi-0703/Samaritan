# progress.md
Last updated: 2026-11-09 | Phase 2.8 evaluated on 22 recorded calls (Hinglish only); Phase 3 and 4 remainder next

## Status
Phases 0 and 1 approved. Phase 2 steps 2.1 to 2.7 are built and unit-tested against fakes (396 tests, ruff clean): API skeleton and models, Gnani batch client with a fake server, audio prep, Layer 1 detection, LLM layer and judge, pipeline, worker, all endpoints, and the evaluation harness (metrics, runner, report, ingest, time-labelling, `GET /eval/latest`, `POST /eval/run`). Real runs on 2026-11-08/09: 22 calls recorded and transcribed with Gnani config A (6 earlier calls with headers trimmed, then 16 more; 17 of the 22 have a computer-voice borrower, the agent is a real person on a microphone; data in `api/local.db`, reports in `eval/reports/`). Latest report 20261109-175339: rules only precision 66% / recall 83%; after labelling times (D-032) and strict matching: rules plus LLM precision 84% / recall 91%, dev 78/88, test 88/93, timestamp accuracy 95%, 0 of 8 clean calls wrongly flagged, role mapping 100% (script order). Remaining errors are in D-032; no tuning done after seeing test errors. Not covered: the 8 Marathi calls (no second speaker). Small, same-author, synthetic-borrower sample: not proof of accuracy. Keys for Gnani, Groq and Gemini are in `api/.env` (Gemini model `gemini-3.5-flash`, D-017). Deadline: 2026-11-10 23:59 IST.

## Done while waiting for recordings
Phase 3 code (Supabase storage over REST, Postgres engine setup, lock-down SQL, seed / migrate / reset scripts, `supabase/README.md`; D-027, D-028). The whole suite (396 tests) passes on SQLite and, with `TEST_PG=1`, on a real local Postgres. Run against the real Supabase project on 2026-11-09: tables migrated, `supabase/rls_and_storage.sql` run (RLS on all 8 tables, 0 anon privileges, private `call-audio` bucket), seeded with 9 rules, 6 agents and the 22 processed calls (435 segments, 25 flags, 22 audio files, no Gnani credits); API on Supabase passes `scripts/smoke.py`; signed audio URL serves the file, unsigned and public paths are refused. Web `httpClient`, upload progress, waking-up banner, `scripts/smoke.py`, `api/Dockerfile`, fake-backed `python -m app.devserver` (D-024 to D-026). Checked in the browser against the dev server: upload, Queued to Done, flagged moment, dismiss recomputing the score, API-stopped banner and recovery. `npm run build` passes with `NEXT_PUBLIC_DATA_SOURCE=api`. Deployed on 2026-11-09 (read-only smoke test passes on the live API; live site checked in the browser: Overview and Accuracy load real data, no console errors). Not done: a live upload through the site, README, submission drafts, real recordings.

## Next action
Live-upload test on the deployed site (one short call; spends about 0.7 Gnani credits; the user types the passcode, which is not stored in the repo). Then README (Mermaid diagram, honest results table from D-032, live URLs, the demo passcode instructions) and the `submission/` files (demo_script.md, project_explanation.md, social_post.md with #GnaniAI and #GreatIndianAIInternshipChallenge). Push each with the user's go-ahead. Do not claim Marathi or 30 calls.

## Completed
- Phase 0: repo skeleton, 30 scripts, 30 answer keys, COVERAGE.md, RECORDING_GUIDE.md. User confirmed the scripts are actable. Verified by `python3 scripts/check_testset.py` (scripts and keys agree; all Section 9.1 totals met).
- Phase 1 build: `npm run lint` clean, `npm run build` passes, TypeScript strict, no `lib/mock` imports outside `src/lib` (ESLint rule enforces it), no forbidden style patterns found by grep.
- Phase 1 checked by hand in the browser: Overview, Calls (filter, search, sort, polling), upload drawer (file validation, wrong then right passcode, new row goes Queued to Done), call detail (waveform markers, click-to-seek, `?t=` deep link, Confirm/Dismiss recomputes score), failed call Retry, evidence page, Agents list and detail, Rules toggle (V9 off removes it from Overview), Accuracy slices. Light and dark seen at 1280 or 1440 px; mobile width seen on call detail.
- Design check with Anthropic's `frontend-design` skill (installed at `.claude/skills/frontend-design`, git-ignored; `skills-lock.json` left untracked). plan.md Section 3 overrides its call for bold choices. Fixes applied: one name per action (Swap roles), no "Open" badge on undecided flags, plain accuracy column names, 68-character prose lines, chart segment separators, reduced-motion support, clearer error text. Screenshots of Overview, Calls, Call detail and Accuracy in both themes were sent to the user.
- Contrast measured for the main colour pairs in both themes; all at 4.5:1 or better after the dark-mode fixes (D-009).

## In progress / unverified
- Everything in Phase 2 ran only against fakes. Real Gnani output (speaker ids, timestamps, Marathi text) and real LLM verdicts on the 30 calls are unverified; Layer 1 lexicons were tuned on dev scripts only (D-018).
- Not exercised: swap-roles button, "Fill from CSV", the passcode dialog (only the stored-passcode path ran), keyboard-only walkthrough, screen-reader pass, actual print preview of the evidence page, real audio playback sound (visual seek and progress verified), Marathi call detail page, Agents/Rules/Evidence in dark.
- Dev server logged one React hydration warning that was fixed (nav link class); a final clean reload of every route for console errors was not done.
- Placeholder audio is synthetic tones, so the waveform does not look like speech.
- RBI reference strings are drafts with no confirmed clause numbers (docs/rbi-references.md).
- All numbers on the Accuracy page are sample data from the mock client, not measurements.

## Waiting on the user
- Permission before the first real transcription (the spike) and, later, the full 30-call run. Credits are no longer a question (D-016).
- Tell the user my earlier `gemini-2.5-flash` advice was wrong (404); `gemini-3.5-flash` is set and tested (D-017).
- RBI source PDFs saved under `docs/rbi-sources/`, or pasted paragraphs, to verify clause numbers (D-014).
- Recordings in `data/audio/`: 22 of 30 (Hinglish only; 8 Marathi calls need a real second person and are out of scope unless one appears).

## Key decisions
- `Gnani/` is the repo root (D-001). Test-set conventions: D-002 to D-007.
- next-themes replaced by a small provider (React 19 script error) (D-008). Dark filled buttons and accent text adjusted for AA (D-009).
- Next.js 16.4.3 with Cache Components kept; dynamic-id pages use `instant = false` (D-010). shadcn is Base UI based; TanStack Table v9 core only (D-011).
- Phase 2 choices: D-018 (LLM layer, merge, lexicon leakage), D-019 to D-022 (stored upload, swap-roles override, no open write transaction across the LLM call, demo guard), D-023 (evaluation code in `api/app/evaluation`, role-mapping truth, ingest).
- Mock semantics the real API must match are listed in D-012 (percent vs fraction, 14-day critical count, V1 and V8 fields, passcode `demo123`).

## Deviations from plan.md
- next-themes not used (D-008). Dark-mode accent colours slightly extended (D-009). Both recorded in docs/decisions.md.

## Repository
- Remote `origin` is https://github.com/Abhi-0703/Samaritan (public). `main` was pushed on 2026-11-05 with the user's go-ahead, over HTTPS using the `gh` credential helper (no SSH key is set up on this Mac). Only `.env.example` files are on GitHub. Later pushes need the user's go-ahead each time.

## Known issues
- Mock state resets on a full page reload; navigating inside the app keeps it.
- Use `/opt/homebrew/bin/python3.11` for the API (system python3 is 3.9.6). ffmpeg 9.0.2 is installed (D-015).
- Next dev overlay badge can sit over the sidebar's Collapse button in development only.
- Wavesurfer decodes whole files in the browser; fine for 3 minutes of audio.

## How to run and verify (commands that currently work)
- web: `cd web && npm install && cp .env.example .env.local && npm run dev` (http://localhost:3000)
- checks: `cd web && npm run lint && npm run build`
- test set: `python3 scripts/check_testset.py`; placeholder audio: `python3 scripts/make_placeholder_audio.py`
- dev api on fakes (no keys, no credits): `cd api && .venv/bin/python -m app.devserver`; web against it: set `NEXT_PUBLIC_DATA_SOURCE=api` in `web/.env.local`; smoke: `python3 scripts/smoke.py [--upload]`
- api: `cd api && source .venv/bin/activate && uvicorn app.main:app --reload` (needs `api/.env`); `python -m app.cli transcribe <audio> --dry-run` shows the plan without calling Gnani
- tests: `cd api && .venv/bin/pytest && .venv/bin/ruff check .` (396 pass, 2 Postgres-only skipped; no network, no credits); on a real Postgres: `TEST_PG=1 .venv/bin/pytest`
- eval: `api/.venv/bin/python eval/run_eval.py run` (cached transcripts only), `... ingest` (asks before spending credits), `eval/label_times.py`

## Environment (no secrets)
- Gnani key: provided and verified (read-only list-jobs call returned 200)  LLM keys: Groq and Gemini provided and verified (model lists fetched)
- Database: Supabase Postgres via the Session pooler (`api/.env`; local SQLite copy in `api/local.db`)   Deployed: yes. API https://samaritan-api.onrender.com (Render free, Docker, `render.yaml`, auto-deploys from `main`), web https://samaritan-six.vercel.app (Vercel, root `web`, DATA_SOURCE=api, DEMO_MODE=true). Free Render sleeps after ~15 min idle (about a minute to wake)
- Tools: node v24, npm 11, git 2.54, python3.11 3.11.18, ffmpeg 9.0.2
