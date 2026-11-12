# Samaritan: X post drafts

Before posting: (1) check the Gnani AI handle (the drafts assume @GnaniAI); (2) replace every {{PASSCODE}} with the real demo passcode, or delete those lines. Attach the demo video to the first post. Open the live site once just before posting, so the free server is awake.

## Option A: one long post (X Premium, about 3,200 characters; the first lines show before "Show more")

I spent two days playing a ruthless loan collector.

Alone. In my room. Shouting "pay now or else" at a robot voice called Rishi.

Then I built an AI whose only job is to catch me. Meet Samaritan 👇

#GnaniAI #GreatIndianAIInternshipChallenge

━━━━━━━━━━━━━━

THE PROBLEM
RBI has rules for recovery calls. Nothing before 8am or after 7pm. No abuse. No threats. No telling the borrower's boss or neighbours about the debt. No pretending to be the police.

But a lender makes thousands of calls a day. Nobody can listen to all of them, so the rules mostly get checked after something has already gone wrong.

WHAT SAMARITAN DOES
Upload a call recording. It transcribes it, works out who is the agent and who is the borrower, checks 9 RBI-style rules, and pins every violation on the waveform. Click a flag and you hear the exact moment. A reviewer can confirm or dismiss each one, and the agent's compliance score updates.

Built for compliance teams, QA leads and anyone who has to audit collection calls.

HOW IT WORKS
1️⃣ @GnaniAI Vachana speech-to-text (prisma-v3.0) turns the call into a Hindi/English transcript with speaker labels
2️⃣ Layer 1 is fast and deterministic: Hinglish lexicons for threats, abuse, shaming and false authority, plus a plain clock check for the 8am–7pm rule
3️⃣ Layer 2 is an LLM (gpt-oss-120b on Groq, Gemini as fallback) that reads the context and decides whether a flagged line is really a violation

THE RULE I REFUSED TO BREAK
The LLM is not allowed to make things up. Every flag has to quote the transcript. If the quote isn't actually in the call, the flag is thrown away.

"Kal tak nahi bhara toh recovery wale ghar aayenge" → flagged.
"Helpline pe bata dijiye" → left alone.

THINGS THAT BIT ME
• The speech model hears "Sahyog Finance" as "Syro Finance", "Safe Finance" and "Syed Bank". My "agent never introduced the lender" rule flagged almost every call until I taught it that any "<word> Finance se" counts as a name.
• My own recordings began with me reading the script header aloud. The AI faithfully transcribed that too.
• My time-labelling tool crashed on real data because it was only ever tested on the format I assumed.

DOES IT WORK?
22 recorded Hinglish calls, with violations scripted into some. On the held-out 14: 88% precision, 93% recall, and 0 of 8 clean calls wrongly flagged. With rules alone, precision is 66%. The LLM layer earns its keep.

Honest caveats: I played the agent and a computer voice played the borrower, so telling the speakers apart is easier than on a real call. It's a small sample and there are no Marathi calls yet. Treat it as a promising prototype, not a proven auditor.

UNDER THE HOOD
FastAPI + SQLAlchemy, Next.js 16 + TypeScript (strict), Supabase Postgres with row-level security, a private audio bucket with short-lived signed links, Render and Vercel. Transcripts and LLM answers are cached, so re-running costs nothing. About 400 tests. No secrets in the repo.

Try it, break it, and tell me what it misses 👇
🔗 https://samaritan-six.vercel.app
💻 https://github.com/Abhi-0703/Samaritan

To upload your own call, use the demo passcode: {{PASSCODE}}
(Free-tier credits, so please keep it to a call or two. The first load can take a minute while the free server wakes up.)

---

## Option B: 7-tweet thread (works without Premium)

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

Built for compliance and QA teams. Upload your own call and try it.

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

Break it, tell me what it misses 👇
🔗 https://samaritan-six.vercel.app
💻 https://github.com/Abhi-0703/Samaritan
🔑 Upload your own call: {{PASSCODE}}

---

## Final post (as posted, about 1,300 characters, attach the demo video)

A few days ago I became the world's worst debt collector. I threatened people. I lied. I pretended to be the RBI. All to a robot called Rishi. Then I built an AI to catch me. This is Samaritan. 🎧

What it does: you upload a loan-recovery call and it tells you whether the agent broke the rules. No calls at 10pm. No threats. No shaming. No posing as police. 9 RBI-style rules, every violation pinned on the waveform. Click a flag, hear the exact moment.

How it works:
🎙 @GnaniAI Vachana speech-to-text turns the call into text, with speakers
🔎 Word lists + a clock check find the suspects
🧠 An LLM judges the context, but it must quote the call. No quote, no flag. It can't invent a crime.

Does it work? On 14 held-out calls: 88% precision, 93% recall, 0 clean calls wrongly flagged. Honest caveat: small acted set, and the borrower was a robot 🤖

Try it 👇
🔗 https://samaritan-six.vercel.app
No password needed to explore: open any call it has already analysed, listen to the audio and see every flag.

🔑 To analyse your own call, the upload password is: samaritan2026
Upload a Hinglish call (English too, less tested). Marathi is next! Uploads cost me credits, so I'll change the password when they run low. Please keep it to a call or two 🙏

📱 Works on your phone too
⏳ First load can take up to a minute: free-tier server waking up

Suggestions and ideas to improve it? I'd love to hear them. #GnaniAI #GreatIndianAIInternshipChallenge
