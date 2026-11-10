# Samaritan: demo video script (target 2:45, limit 3:00)

The form asks for a 2–3 minute demo of the build. This script runs about 2:45 with the live upload. Lines in quotes are what you say; lines in [brackets] are what is on screen.

## Slides

`submission/samaritan_intro.pptx` (open it in Keynote or PowerPoint) has six slides and speaker notes with your lines for each. Use it like this:

| Slide | Say | Script time |
|---|---|---|
| 1. SAMARITAN banner | the hook | 0:00 |
| 2. Nobody can listen to every call | the problem | 0:15 |
| 3. Samaritan listens to all of them | what it does, who it is for | 0:35 |
| 4. How it decides | the pipeline (you can also show this while the upload processes) | 0:50 or during the wait |
| 5. Built with | optional, skip if running long | |
| 6. Now, let's audit a call. Live. | then switch to the browser | 1:00 |

Present slides 1 to 3 (and 6) before the live demo; slide 4 works well while the upload processes.

## Before you press record (10 minutes)

1. **Wake the server.** Open https://samaritan-six.vercel.app and let the Overview fill in. Render's free plan sleeps when idle.
2. **Pick the audio:** `data/audio/call_14.m4a`. In it the agent claims to be "the RBI recovery cell" and says "tomorrow the police will come and send you to jail". That should give two flags, and the call time gives a third.
3. **Plan the "called at" time:** today's date at **21:40**. The rule says no calls after 19:00, so this flags the clock rule. Leave "Borrower asked for this call time" **unticked**.
4. **Do one practice upload first**, so you know it works and how long it takes (usually 1–2 minutes). After the practice run, tick nothing else; just record.
5. **Have a backup open in a second tab:** a finished call, for example the one from your practice upload. If the live upload is slow or fails on camera, say "here is one I ran a minute ago" and carry on. Do not pretend.
6. **Screen:** browser at 100% zoom, dark theme is fine, close other tabs and notifications. Keep the passcode off screen if you can (type it quickly, or have it pasted).
7. **A short clip of the audio playing** is part of the demo, so turn your volume up and record system audio if your tool allows it.

## The script

**0:00–0:15 · Hook** [title card or your face]
"Two days ago I became the world's worst debt collector. I threatened people. I lied. I pretended to be the RBI. All to a robot called Rishi. Then I built an AI to catch me. This is Samaritan."

**0:15–0:35 · The problem** [Overview page]
"RBI has rules for recovery calls. Nothing before eight a.m. or after seven p.m. No abuse, no threats, no telling your boss. But a lender makes thousands of calls a day, and no human can listen to all of them. So the rules get checked after something has already gone wrong. Samaritan listens to every call."

**0:35–0:50 · The dashboard** [point at the cards and the chart]
"This is the live app. Twenty-two audited calls, compliance scores, critical flags this fortnight, and which rule gets broken the most. But old calls are boring. Let's audit a brand-new one, live."

**0:50–1:15 · Live upload** [click Upload calls, drop the file, fill the form]
"I'm dropping in a call I recorded. The agent is Imran. Loan reference, anything. And the time: I'll say this call happened at nine-forty p.m. And no, the borrower did not ask for it. Demo passcode, and upload."
[Click Upload. The row appears as Queued.]
"Queued. Now watch the pipeline work."

**1:15–1:55 · What happens behind the scenes** [show the README diagram, or just keep the Calls list visible and talk over it]
"First, Gnani's Vachana speech-to-text turns the audio into Hinglish text with speaker labels. Then I work out who is the agent and who is the borrower. Layer one is fast and dumb: word lists for threats and abuse, plus a plain clock check. Layer two is an LLM that reads the context. And here's my favourite rule: the LLM has to quote the transcript. If its quote isn't really in the call, the flag gets deleted. It is not allowed to hallucinate a crime."
[If it is still processing, say: "This takes a minute on a free server, so I'm speeding it up." and cut or speed up the wait. Put "sped up" on screen.]

**1:55–2:30 · The result** [the row says Done; open the call]
"Done. Three flags. One: the call was at nine-forty p.m., that's the clock. Two: 'I'm speaking from the RBI recovery cell', that's impersonation. Three: 'tomorrow the police will come and send you to jail', that's a false legal threat."
[Click a flag: the waveform jumps and the audio plays for about three seconds.]
"Click a flag and you hear that exact moment. A reviewer confirms or dismisses it, and the agent's score updates."
[Click Confirm or Dismiss on one flag and point at the score.]

**2:30–2:50 · Does it work?** [Accuracy page]
"Does it work? On fourteen held-out calls: eighty-eight percent precision, ninety-three percent recall, and zero clean calls wrongly flagged. Honest caveat: I played the agent, a robot played the borrower, and it's only twenty-two calls. This is a prototype, not a verdict."

**2:50–3:00 · Close** [title card with the link]
"Try it yourself, link below. Built on Gnani's speech-to-text. I'm Abhinav. Hashtag GnaniAI."

## If it goes wrong on camera

- **Upload says the passcode is wrong:** check for a stray space; retype it. You can cut and retake.
- **"Server is waking up" banner:** wait; it fills in by itself in under a minute. This is why you wake it first.
- **Stuck on Queued for over two minutes:** switch to the backup tab and say so.
- **A flag you did not expect appears or one is missing:** say it plainly ("it caught two of the three I planted") and carry on. Honest beats polished, and the Accuracy page already says the sample is small.

## After recording

Upload the video to LinkedIn and/or X, paste the post from `social_post.md` (replace `{{PASSCODE}}` first), and add the post link and the video link to the form. The form asks for: your name, email, institution, the project URL (use the GitHub link: the README links to the one-page pitch), the video link, and the post link for the bonus category.
