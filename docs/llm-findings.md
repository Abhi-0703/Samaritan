# LLM findings (Phase 2, 2026-11-05)

One real call per provider on the synthetic dev script `call_16` (missing introduction plus a threat to tell neighbours). No Gnani data was involved.

## Groq, `openai/gpt-oss-120b`
- Works with `response_format: json_object` and `reasoning_effort: low`. It found V8 and V5, and both passed evidence verification.
- Tokens per call: about 2,440 prompt plus 429 completion with low reasoning effort. Without it the completion was 1,257 tokens, mostly hidden reasoning. So a call costs roughly 2,900 tokens, which is about 2.7 calls a minute against the 8,000 tokens per minute limit, and about 70 calls a day against 200,000.
- Latency 1.5 to 3 s.
- The char-based token estimate (3.5 chars per Latin token, 1.5 per Devanagari) predicted 2,394 prompt tokens; the real figure was 2,437.
- With low reasoning the model also flagged a V9 on a borderline line ("Do-teen hafte bahut zyada hain. Ek hafte mein kuch kijiye.", confidence 0.71). That is a dev-set case to look at when tuning the prompt, using dev calls only.

## Gemini
- `gemini-2.5-flash` and `gemini-2.5-flash-lite` appear in the model list but return 404: Google has retired them for new accounts. A model in `models.list` is not proof it can be called.
- **`gemini-3.5-flash` is the choice.** It answered correctly in 2.5 s with 2,461 prompt and 149 completion tokens. `GEMINI_MODEL` is set to it.
- `gemini-3.8-flash` gave the same answer but took 135 s. `gemini-3.5-flash-lite` rejected the `thinking_budget=0` setting with HTTP 400 (not investigated further).
- Free-tier request and token limits were not measured; the fallback limiter uses 10 requests and 200,000 tokens a minute as a conservative guess.
