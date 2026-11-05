# progress.md
Last updated: 2026-11-05 | Phase: 1 complete, Phase 2 not started | Step: waiting for Phase 2 inputs

## Status
Phases 0 and 1 are approved by the user (scripts confirmed actable; Phase 1 design "looks right"). Python 3.11 and ffmpeg are installed. RBI references are drafted but unverified. Phase 2 (FastAPI backend, Gnani, LLM, detection, evaluation) has not started. The user has put the Gnani, Groq and Gemini keys in `api/.env` (all three verified working). Pricing is known: STT is Rs 20 per hour, so the whole plan costs about 25 credits. Deadline: 2026-11-10 23:59 IST.

## Next action
When the user supplies the Phase 2 inputs (at least the Gnani key in `api/.env`, Groq and Gemini keys and model names), start Phase 2.1: create `api/` with `python3.11 -m venv`, FastAPI skeleton, config, error envelope, SQLAlchemy models, Alembic migration, 9 seeded rules, local storage. Work that needs no keys (2.1 to 2.4, fake Gnani server, audio prep) may start before the keys arrive.

## Completed
- Phase 0: repo skeleton, 30 scripts, 30 answer keys, COVERAGE.md, RECORDING_GUIDE.md. User confirmed the scripts are actable. Verified by `python3 scripts/check_testset.py` (scripts and keys agree; all Section 9.1 totals met).
- Phase 1 build: `npm run lint` clean, `npm run build` passes, TypeScript strict, no `lib/mock` imports outside `src/lib` (ESLint rule enforces it), no forbidden style patterns found by grep.
- Phase 1 checked by hand in the browser: Overview, Calls (filter, search, sort, polling), upload drawer (file validation, wrong then right passcode, new row goes Queued to Done), call detail (waveform markers, click-to-seek, `?t=` deep link, Confirm/Dismiss recomputes score), failed call Retry, evidence page, Agents list and detail, Rules toggle (V9 off removes it from Overview), Accuracy slices. Light and dark seen at 1280 or 1440 px; mobile width seen on call detail.
- Design check with Anthropic's `frontend-design` skill (installed at `.claude/skills/frontend-design`, git-ignored; `skills-lock.json` left untracked). plan.md Section 3 overrides its call for bold choices. Fixes applied: one name per action (Swap roles), no "Open" badge on undecided flags, plain accuracy column names, 68-character prose lines, chart segment separators, reduced-motion support, clearer error text. Screenshots of Overview, Calls, Call detail and Accuracy in both themes were sent to the user.
- Contrast measured for the main colour pairs in both themes; all at 4.5:1 or better after the dark-mode fixes (D-009).

## In progress / unverified
- Not exercised: swap-roles button, "Fill from CSV", the passcode dialog (only the stored-passcode path ran), keyboard-only walkthrough, screen-reader pass, actual print preview of the evidence page, real audio playback sound (visual seek and progress verified), Marathi call detail page, Agents/Rules/Evidence in dark.
- Dev server logged one React hydration warning that was fixed (nav link class); a final clean reload of every route for console errors was not done.
- Placeholder audio is synthetic tones, so the waveform does not look like speech.
- RBI reference strings are drafts with no confirmed clause numbers (docs/rbi-references.md).
- All numbers on the Accuracy page are sample data from the mock client, not measurements.

## Waiting on the user
- Permission before the first real transcription (the spike) and, later, the full 30-call run. Keys are in `api/.env`; credits are no longer a question (D-016). Gemini model: recommended `gemini-2.5-flash`, not yet written to `.env`.
- GitHub repository URL (user said they will provide it); nothing is pushed yet.
- RBI source PDFs saved under `docs/rbi-sources/`, or pasted paragraphs, to verify clause numbers (D-014).
- Recordings in `data/audio/`: 0 of 30 (user and friend both speak Marathi; separate-channel recording is possible for 1 or 2 calls).

## Key decisions
- `Gnani/` is the repo root (D-001). Test-set conventions: D-002 to D-007.
- next-themes replaced by a small provider (React 19 script error) (D-008). Dark filled buttons and accent text adjusted for AA (D-009).
- Next.js 16.4.3 with Cache Components kept; dynamic-id pages use `instant = false` (D-010). shadcn is Base UI based; TanStack Table v9 core only (D-011).
- Mock semantics the real API must match are listed in D-012 (percent vs fraction, 14-day critical count, V1 and V8 fields, passcode `demo123`).

## Deviations from plan.md
- next-themes not used (D-008). Dark-mode accent colours slightly extended (D-009). Both recorded in docs/decisions.md.

## Known issues
- Mock state resets on a full page reload; navigating inside the app keeps it.
- Use `/opt/homebrew/bin/python3.11` for the API (system python3 is 3.9.6). ffmpeg 9.0.2 is installed (D-015).
- Next dev overlay badge can sit over the sidebar's Collapse button in development only.
- Wavesurfer decodes whole files in the browser; fine for 3 minutes of audio.

## How to run and verify (commands that currently work)
- web: `cd web && npm install && cp .env.example .env.local && npm run dev` (http://localhost:3000)
- checks: `cd web && npm run lint && npm run build`
- test set: `python3 scripts/check_testset.py`; placeholder audio: `python3 scripts/make_placeholder_audio.py`
- api: not built yet   tests: none yet

## Environment (no secrets)
- Gnani key: provided and verified (read-only list-jobs call returned 200)  LLM keys: Groq and Gemini provided and verified (model lists fetched)
- Database: none (mock data in memory)   Deployed: no
- Tools: node v24, npm 11, git 2.54, python3.11 3.11.18, ffmpeg 9.0.2
