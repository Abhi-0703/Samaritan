# progress.md
Last updated: 2026-11-05 | Phase: 1 | Step: design check done, awaiting user approval

## Status
Phase 0 is done and the user told the agent to proceed. Phase 1 (full web UI on mock data) is built: all seven routes, light and dark themes, upload drawer, call detail with waveform and transcript sync, evidence page. `npm run lint` and `npm run build` pass. Waiting for the user to look at it and give design feedback before Phase 2. The Accuracy figures are sample data, labelled as such in the UI.

## Next action
Ask the user for Phase 1 feedback (screenshots: Overview, Calls, Call detail, Accuracy in light and dark; ask whether they want a different accent colour) and for approval. On approval, start Phase 2 by sending ONE message with the Phase 2 [ASK USER] list (plan.md Section 12): Gnani key into `api/.env`, dashboard credits and rate limits, Groq and Gemini keys and model names, permission before any real Gnani call, recordings in `data/audio/`, RBI-reference drafting, Python 3.11 and ffmpeg installs.

## Completed
- Phase 0: repo skeleton, 30 scripts, 30 answer keys, COVERAGE.md, RECORDING_GUIDE.md. Verified by `python3 scripts/check_testset.py` (scripts and keys agree; all Section 9.1 totals met).
- Phase 1 build: `npm run lint` clean, `npm run build` passes, TypeScript strict, no `lib/mock` imports outside `src/lib` (ESLint rule enforces it), no forbidden style patterns found by grep.
- Phase 1 checked by hand in the browser: Overview, Calls (filter, search, sort, polling), upload drawer (file validation, wrong then right passcode, new row goes Queued to Done), call detail (waveform markers, click-to-seek, `?t=` deep link, Confirm/Dismiss recomputes score), failed call Retry, evidence page, Agents list and detail, Rules toggle (V9 off removes it from Overview), Accuracy slices. Light and dark seen at 1280 or 1440 px; mobile width seen on call detail.
- Design check with Anthropic's `frontend-design` skill (installed at `.claude/skills/frontend-design`, git-ignored; `skills-lock.json` left untracked). plan.md Section 3 overrides its call for bold choices. Fixes applied: one name per action (Swap roles), no "Open" badge on undecided flags, plain accuracy column names, 68-character prose lines, chart segment separators, reduced-motion support, clearer error text. Screenshots of Overview, Calls, Call detail and Accuracy in both themes were sent to the user.
- Contrast measured for the main colour pairs in both themes; all at 4.5:1 or better after the dark-mode fixes (D-009).

## In progress / unverified
- Not exercised: swap-roles button, "Fill from CSV", the passcode dialog (only the stored-passcode path ran), keyboard-only walkthrough, screen-reader pass, actual print preview of the evidence page, real audio playback sound (visual seek and progress verified), Marathi call detail page, Agents/Rules/Evidence in dark.
- Dev server logged one React hydration warning that was fixed (nav link class); a final clean reload of every route for console errors was not done.
- Placeholder audio is synthetic tones, so the waveform does not look like speech.
- All numbers on the Accuracy page are sample data from the mock client, not measurements.

## Waiting on the user
- Phase 1 design feedback and approval; accent colour preference.
- Phase 0 questions still open: friend speaks Marathi?, separate-channel recording possible?, draft RBI clause references?, GitHub repo.
- Recordings in `data/audio/`: 0 of 30.
- Later (Phase 2): Gnani key, Groq and Gemini keys and models, dashboard facts, permission for first real Gnani call.

## Key decisions
- `Gnani/` is the repo root (D-001). Test-set conventions: D-002 to D-007.
- next-themes replaced by a small provider (React 19 script error) (D-008). Dark filled buttons and accent text adjusted for AA (D-009).
- Next.js 16.4.3 with Cache Components kept; dynamic-id pages use `instant = false` (D-010). shadcn is Base UI based; TanStack Table v9 core only (D-011).
- Mock semantics the real API must match are listed in D-012 (percent vs fraction, 14-day critical count, V1 and V8 fields, passcode `demo123`).

## Deviations from plan.md
- next-themes not used (D-008). Dark-mode accent colours slightly extended (D-009). Both recorded in docs/decisions.md.

## Known issues
- Mock state resets on a full page reload; navigating inside the app keeps it.
- Toolchain: system Python is 3.9.6 (API needs 3.11+) and ffmpeg is missing (D-005). Ask before installing.
- Next dev overlay badge can sit over the sidebar's Collapse button in development only.
- Wavesurfer decodes whole files in the browser; fine for 3 minutes of audio.

## How to run and verify (commands that currently work)
- web: `cd web && npm install && cp .env.example .env.local && npm run dev` (http://localhost:3000)
- checks: `cd web && npm run lint && npm run build`
- test set: `python3 scripts/check_testset.py`; placeholder audio: `python3 scripts/make_placeholder_audio.py`
- api: not built yet   tests: none yet

## Environment (no secrets)
- Gnani key: not provided  LLM key: none
- Database: none (mock data in memory)   Deployed: no
- Tools: node v24, npm 11, git 2.54, python3 3.9.6; no ffmpeg
