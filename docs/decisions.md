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
