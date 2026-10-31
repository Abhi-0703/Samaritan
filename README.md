# Samaritan

Samaritan audits loan-recovery phone calls for Indian lenders. A compliance team uploads call recordings; the system transcribes them with Gnani Prisma speech-to-text, flags violations of RBI recovery-conduct rules with a two-layer detection engine (deterministic rules plus an LLM judge that must quote its evidence), scores each call and agent, and publishes its own measured accuracy on a labelled test set.

Status: under construction. Phase 0 (repository skeleton and the 30-call synthetic test set) and Phase 1 (the web app on mock data) are in place; the API, database and evaluation arrive in later phases. The full README (architecture diagram, run steps, results, limitations) is written in Phase 4.

- `plan.md` — build specification
- `architecture.md` — how the system is structured and why
- `progress.md` — current state, for whoever continues the work
- `web/` — the Next.js app (runs on mock data for now; see `web/README.md`)
- `data/` — synthetic call scripts, answer keys and the recording guide

All data in this project is synthetic. No real names, numbers or recordings are used.
