# Gnani findings

Working notes for Phase 2. Facts are tagged by source.

## Pricing and credits (from the user's Gnani dashboard, 2026-11-05)
- 1 credit = ₹1. Balance at the time: 5,000 of 5,000 credits (about 250 hours of STT at the rate below).
- Speech to Text, every variant (REST, WebSocket, Batch; Prisma v2.5 and v3.0): **₹20.00 per hour** of audio, so about 0.33 credits per minute.
- Text to Speech (not used here): ₹18 per 10,000 characters.
- Listed limits: 60 requests per minute for REST and Batch; 20 concurrent WebSocket sessions.
- The dashboard has Usage (credits consumed and a per-request history with request ID, model, usage and cost), Billing and Pricing pages.
- Budget for this project: about 76 minutes of audio (30 calls plus the spike) is roughly 25 credits. Whether Gnani rounds each file up (for example to the next minute) is not published; check the Usage page after the first real call.

## From docs.gnani.ai (read 2026-11-05)
- Auth header `X-API-Key-ID`; base URL `https://api.vachana.ai`. Keys are made at https://app.gnani.ai/voice.
- Errors page: 402 means insufficient credit (no body documented); 403 `SCOPE_NOT_ALLOWED`; 429 `RATE_LIMITED` with the message "Only 1 active request is allowed at a time". So `GNANI_MAX_CONCURRENT=1` is required, not just cautious.
- Retry 429, 500, 503, 504 and connection errors with backoff; do not retry other 4xx.
- Batch limits: 10 MB per uploaded file, up to 4 h per file, 100 files per job. Speaker separation exists only in Batch.
- Batch pages exist under both `/api/STTBatch/` and `/api/STT/batch/`; the plan uses the latter.
- The docs index page called "Dashboard" is about a different Gnani product (call and chat metrics), not credits.

## Verified by a real call (2026-11-05, with the user's permission)
- `GET /stt/v3/batch/jobs?limit=5` with the user's key returned HTTP 200 and `{data: [], pagination: {has_more: false, next_cursor: null}}`. So the key is valid, has the STT scope, and the account has no batch jobs yet. Response shape matches the docs. No audio was sent.

## First real transcriptions (2026-11-08, configuration A, five Hinglish calls, 12 minutes of audio)
- Batch accepts `prisma-v3.0` with `language_code=hi-IN,en-IN`, `format=transcribe`, `with_diarization`, `num_speakers=2`. All five jobs completed.
- **Script:** Gnani writes Hindi in Devanagari and keeps English words in Latin ("आपकी पर्सनल लोन की ईएमआई 10 दिन से पेंडिंग है", "payment हो जाए तो"). Numbers come out as digits. Layer 1 and the LLM prompt work on this output as it is.
- **Lender name:** "Sahyog Finance" is heard as Safe Finance, Syro Finance, Syed Bank Finance, service finance. The V8 introduction check must not depend on the exact name (it accepts a "...Finance" word near the agent's own name).
- **Speakers:** with one mixed mono channel, diarization separated the two voices on all five calls. A single turn is often split into several segments, but the speaker ids stayed stable.
- **Rate limit:** every job saw `429 RATE_LIMITED` once or twice on the polling `GET` calls; the client's retry absorbed them. Nothing failed.
- **Cost:** 12.0 minutes of audio, expected about 4 credits. The Usage page has not been checked against this yet.
- **Not tried yet:** configurations B to E (codemix, v2.5, denoise, keyterms) and a Marathi call (`call_05` is not recorded).

### Problem found in the recordings, not in Gnani
All five recordings begin with the speaker reading the script's header line and recording notes aloud (20 to 35 seconds), for example "Agent Rohit Patil, borrower Anil Kumar, loan ... Recording notes: ...". That text is in the transcript, is attributed to a speaker, and in `call_10` the diarization gave the reader of the header and the borrower the same id, so the agent and borrower were swapped for the whole call and the V6 disclosure was missed. In `call_16` the notes even contain the lender's name. The recordings must start at the agent's first spoken line. Proposed fix: cut the first 20 to 35 seconds (cut points taken from the transcript boundaries) and transcribe the trimmed files again, about 3 credits.

## Open
- Whether Gnani rounds billing per file; check the Usage page after this run.
- Chosen transcription configuration (plan Section 7.4, spike A to E): A works; B to E not compared.
