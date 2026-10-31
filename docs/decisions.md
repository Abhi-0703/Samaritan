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
