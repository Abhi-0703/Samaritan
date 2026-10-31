# progress.md
Last updated: 2026-11-01 02:14 IST | Phase: 0 | Step: finished, awaiting user approval

## Status
Phase 0 is built: repo skeleton, 30 call scripts, 30 answer keys, coverage report and recording guide. All automated acceptance checks pass. Waiting for the user to confirm the scripts are actable and to answer the Phase 0 questions. No code for Phase 1+ exists yet. Deadline: 2026-11-10 23:59 IST.

## Next action
When the user approves Phase 0, start Phase 1: first send ONE message with the Phase 1 [ASK USER] items (none needed beforehand except screenshots at the end), then scaffold `web/` with `npx create-next-app@latest web --typescript --tailwind --eslint --app --src-dir` (move `web/.env.example` aside first; the folder must be empty, then restore it) and build the design system before pages (plan.md Section 12, Phase 1).

## Completed
- Phase 0 skeleton: git initialised on `main`, folders per plan 8.1, `.gitignore` (`.env*` ignored, `.env.example` kept; `data/audio/` ignored), `api/.env.example`, `web/.env.example`, README stub, `docs/decisions.md`. Verified by `ls` and `git status`.
- Phase 0 test material: `data/scripts/call_01..30.md`, `data/answer_keys/call_01..30.json`, `data/COVERAGE.md`, `data/RECORDING_GUIDE.md`. Verified by `python3 scripts/check_testset.py` -> "OK: 30 scripts and keys agree". Checked: markers vs keys, every quote_hint inside its marked line, header time/language/noise/requested-time vs key, V1 consistent with time, word counts 255-328, unique loan refs, all Section 9.1 totals and per-rule dev/test minimums.

## In progress / unverified
- Phase 0 acceptance item "user confirms the scripts are actable" - not yet confirmed by the user.
- Script wording is untested against real speech and real transcription; some lines may need adjusting after the first recordings.
- Marathi scripts (255-273 spoken words) may record shorter than 1.5 minutes - see D-007.

## Waiting on the user
- Approval of Phase 0 and confirmation the 30 scripts are actable.
- GitHub repo to push to (if any): not yet provided.
- Does the friend playing the borrower speak Marathi (8 calls need it)? Not yet answered.
- Is separate-channel recording possible (agent and borrower each recorded on their own channel)? Not yet answered.
- Recordings in `data/audio/`: 0 of 30 received (first batch suggested in RECORDING_GUIDE.md section 7).
- Whether to draft RBI clause references for the rules (plan 5.2): not yet answered.
- Later (Phase 2 start): Gnani key, dashboard facts, Groq/Gemini keys and model names, permission before the first real Gnani call.

## Key decisions
- `Gnani/` folder is the repo root, no extra `samaritan/` folder (D-001).
- Answer keys gain optional `hard_negative` and `notes` fields; scripts mark violating lines with `<<Vn>>` so scripts and keys can be machine-checked (D-002, D-003).
- Marathi quote hints are Devanagari (D-004). 250-word minimum applies to spoken Devanagari words (D-007).
- Allocation of the 30 calls: see D-006 and `data/COVERAGE.md`. Dev = calls 01, 02, 05, 06, 09, 11, 16, 20, 22, 26.

## Deviations from plan.md
- None to requirements. Additive only: extra optional key fields and script markers (see decisions above), plus `scripts/check_testset.py`, which plan.md does not list.

## Known issues
- Local toolchain: system `python3` is 3.9.6 (API needs 3.11+) and `ffmpeg`/`ffprobe` are missing (D-005). Homebrew is installed. Fix before Phase 2; ask the user before installing.
- `docs/gnani-findings.md` does not exist yet; it is a Phase 2 output.

## How to run and verify (commands that currently work)
- test-set check: `python3 scripts/check_testset.py` (rewrites `data/COVERAGE.md`)
- web: not built yet   api: not built yet   tests: none yet

## Environment (no secrets)
- Gnani key: not provided  LLM key: none
- Database: none yet   Deployed: no
- Tools: node v24, npm 11, git 2.54, gh 2.98, python3 3.9.6; no ffmpeg
