# Samaritan: solution pitch (one page)

**An AI auditor for loan-recovery calls.** Live: https://samaritan-six.vercel.app · Code: https://github.com/Abhi-0703/Samaritan

## The problem
RBI's recovery-agent guidance is clear: no calls before 8 am or after 7 pm, no abuse, no threats, no telling a borrower's employer or neighbours about the debt, no posing as the police or a court. But a lender makes thousands of calls a day and nobody can listen to them all, so the rules are usually checked only after a complaint.

## The solution
Samaritan listens to every call. A compliance team uploads recordings; Samaritan transcribes each one, works out who is the agent and who is the borrower, checks nine RBI-style rules, and pins every violation on the audio waveform. A reviewer clicks a flag, hears the exact moment, and confirms or dismisses it. Each call and each agent gets a compliance score. It is built for compliance teams, QA leads and collections agencies.

## How it works
1. **Gnani Vachana speech-to-text (`prisma-v3.0`)**, batch API with two-speaker diarization, turns a Hinglish call into a transcript with speaker labels and timestamps.
2. **Role mapping** decides which speaker is the agent from how each one talks.
3. **Layer 1, rules:** a clock check for the calling-hours rule, a check that the lender was named, and Hinglish and Marathi lexicons that find candidate lines.
4. **Layer 2, LLM judge** (Groq `gpt-oss-120b`, Gemini as fallback) reads each candidate with its context, on masked text, and decides whether it is a real violation.
5. **Evidence check:** every flag must quote the transcript. If the quote is not in the call, the flag is discarded, so the model cannot invent a violation.

Stack: FastAPI and SQLAlchemy, Next.js 16 with TypeScript, Supabase Postgres and a private audio bucket, Render and Vercel. About 400 automated tests.

## Does it work? (measured, with the caveats)
On 22 recorded Hinglish calls, the held-out 14 give **88% precision and 93% recall**, with **0 of 8 clean calls wrongly flagged**. Rules alone reach 66% precision, so the LLM layer earns its place. The accuracy page in the app shows every number, and the README lists every known failure.

This is a prototype, not a proven auditor: the sample is small, the calls are acted from scripts, 5 of the 22 are two real people and the other 17 have me as the agent with a computer voice as the borrower (which makes telling speakers apart easier than on real calls), and Marathi is built but untested on real audio.

## Gnani models used
Gnani Vachana **prisma-v3.0** speech-to-text (batch API, Hindi and English, diarization on).

## What I would do next
Record real two-person calls, run Marathi end to end, confirm the RBI clause citations against the primary documents, and replace the in-process worker with a real job queue.
