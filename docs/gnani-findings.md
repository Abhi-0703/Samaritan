# Gnani findings

Working notes for Phase 2. Facts are tagged by source. Nothing here has been confirmed by a real API call yet.

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

## Open (needs a real call, after the user's go-ahead)
- Does the key work, and does Batch accept `prisma-v3.0` on this account?
- Chosen transcription configuration (plan Section 7.4, spike A to E).
- Credit cost per call as shown on the Usage page.
