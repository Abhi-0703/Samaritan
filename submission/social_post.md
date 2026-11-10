# Samaritan: X thread draft

Post as a thread, attach the demo video to tweet 1. Check the Gnani AI handle before posting (the draft assumes @GnaniAI).

**1/7**

I spent two days playing a ruthless loan collector.

Alone. In my room. Shouting "pay now or else" at a robot voice called Rishi.

Then I built an AI whose only job is to catch me.

Meet Samaritan 🧵

#GnaniAI #GreatIndianAIInternshipChallenge

---

**2/7**

The problem: RBI has rules for recovery calls. Nothing before 8am or after 7pm. No abuse, no threats, no telling your boss or neighbours.

But a lender makes thousands of calls a day and nobody can listen to them all. So the rules get checked after something has gone wrong.

---

**3/7**

Samaritan listens to all of them.

Upload a recording → it transcribes, works out who is agent and who is borrower, checks 9 RBI-style rules and pins each violation on the waveform. Click a flag, hear the exact moment.

Built for compliance and QA teams.

---

**4/7**

How it works (the nerdy bit):

🎙 @GnaniAI Vachana STT (prisma-v3.0): Hinglish transcript + speaker labels
🔎 Layer 1: Hinglish lexicons + a clock check for the 8am–7pm rule
🧠 Layer 2: an LLM (gpt-oss-120b on Groq) judges the context

---

**5/7**

The part I'm proudest of: the LLM isn't allowed to make things up.

Every flag must quote the transcript. If the quote isn't really there, the flag is thrown away.

"Kal tak nahi bhara toh recovery wale ghar aayenge" → flagged.
A polite "helpline pe bata dijiye" → left alone.

---

**6/7**

Does it work? 22 recorded Hinglish calls, violations hidden in some.

Held-out 14: 88% precision, 93% recall, 0 of 8 clean calls wrongly flagged. Rules alone: 66% precision. The LLM earns its keep.

Caveat: I was the agent, a robot the borrower. Small sample, no Marathi yet.

---

**7/7**

Stack: FastAPI, Next.js 16 + TypeScript, Supabase (Postgres + private audio storage), Render, Vercel. ~400 tests, no secrets in the repo.

Try it, break it, tell me what it misses 👇
🔗 https://samaritan-six.vercel.app
💻 https://github.com/Abhi-0703/Samaritan
