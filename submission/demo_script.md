# Samaritan: demo video script, with slides (target 2:45, limit 3:00)

The form asks for a 2–3 minute demo of the build. This version uses the slides in `samaritan_intro.pptx` before and during the live upload. Lines in quotes are what you say; lines in [brackets] are what is on screen. Times are targets, not exact.

## The flow at a glance

| Time | On screen | What happens |
|---|---|---|
| 0:00–0:12 | Slide 1, banner | the hook |
| 0:12–0:32 | Slide 2, the problem | why this is needed |
| 0:32–0:47 | Slide 3, what it does | the idea in four steps |
| 0:47–0:52 | Slide 6, "Now, let's audit a call. Live." | switch to the browser |
| 0:52–1:20 | Browser | upload the call live |
| 1:20–1:50 | Slide 4, how it decides | explain while it processes |
| 1:50–2:25 | Browser | the result, flags, audio, score |
| 2:25–2:45 | Browser, Accuracy page | honest numbers |
| 2:45–2:55 | Slide 5, built with | thank Gnani, close |

## Before you press record (10 minutes)

1. **Wake the server.** Open https://samaritan-six.vercel.app and let the Overview fill in. Render's free plan sleeps when idle.
2. **Open the slides in presentation mode** (Keynote or PowerPoint, "Play slideshow"). Put the browser in a second window or desktop so you can switch with Cmd+Tab (or Ctrl+Left/Right to change desktops).
3. **Pick the audio:** `data/audio/call_14.m4a`. In it the agent claims to be "the RBI recovery cell" and says "tomorrow the police will come and send you to jail". That gives two flags, and the call time gives a third.
4. **Plan the "Called at (IST)" time:** today's date at **21:40**. The rule says no calls after 19:00, so this flags the clock rule. Leave **"Borrower asked for this call time" unticked**.
5. **Do one practice upload first**, so you know it works and how long it takes (usually 1–2 minutes).
6. **Keep a backup tab open:** a finished call, for example the one from your practice upload. If the live upload is slow or fails on camera, say "here is one I ran a minute ago" and carry on. Do not pretend.
7. **Record system audio as well as your microphone** (see the OBS notes), because the call audio plays during the demo.
8. **Tidy the screen:** browser at 100% zoom, no other tabs, notifications off.

## The script

### Slide 1 · Hook (0:00–0:12)
[SAMARITAN banner. Smile, then speak.]
"Two days ago I became the world's worst debt collector. I threatened people. I lied. I pretended to be the RBI. All to a robot called Rishi. Then I built an AI to catch me. This is Samaritan."

### Slide 2 · The problem (0:12–0:32)
[Press next.]
"RBI has rules for recovery calls. Nothing before eight a.m. or after seven p.m. No abuse, no threats, no telling your boss or your neighbours. But a lender makes thousands of calls a day and a human can review a handful. So the rules get checked after something has already gone wrong."

### Slide 3 · What it does (0:32–0:47)
[Press next.]
"Samaritan listens to all of them. You upload a recording. It transcribes it, works out who is the agent and who is the borrower, checks nine RBI-style rules, and pins every violation on the waveform. Built for compliance teams and QA leads."

### Slide 6 · Cue (0:47–0:52)
[Press next to the "Now, let's audit a call. Live." slide, then switch to the browser.]
"So let's audit a brand-new call. Live."

### Browser · Live upload (0:52–1:20)
[Show the Overview for two seconds. Click **Upload calls**, drop `call_14.m4a`, choose agent **Imran Shaikh**, any loan reference, set **Called at** to 21:40 today, and type the passcode.]
"This is a call I recorded. The agent is Imran. And I'll say it happened at nine-forty p.m. No, the borrower did not ask for that. Passcode, and upload."
[Click Upload. The row appears as Queued.]
"Queued. While it works, here is what is happening under the hood."

### Slide 4 · How it decides (1:20–1:50)
[Switch to the slides, slide 4.]
"Gnani's Vachana speech-to-text turns the audio into Hinglish text with speaker labels. Then I work out who is the agent. Layer one is fast: word lists and a plain clock check. Layer two is an LLM that reads the context. And my favourite rule: the LLM has to quote the call. If its quote is not really in the transcript, the flag is deleted. No quote, no flag. It is not allowed to hallucinate a crime."
[If you are still waiting, say: "This takes a minute on a free server, so I'm skipping ahead." Cut or speed up the wait in the edit and put "sped up" on screen.]

### Browser · The result (1:50–2:25)
[Switch back. The row says Done. Open the call.]
"Done. Three flags. One: the call was at nine-forty p.m., that is the clock. Two: 'I'm speaking from the RBI recovery cell', that is impersonation. Three: 'tomorrow the police will come and send you to jail', a false legal threat."
[Click a flag. The waveform jumps and the audio plays for about three seconds.]
"Click a flag and you hear that exact moment. A reviewer confirms or dismisses it, and the agent's score updates."
[Click Confirm or Dismiss on one flag and point at the score.]

### Browser · Does it work? (2:25–2:45)
[Open the Accuracy page.]
"Does it work? On fourteen held-out calls: eighty-eight percent precision, ninety-three percent recall, and zero clean calls wrongly flagged. Honest caveat: it is only twenty-two acted calls, and most of them have a robot as the borrower. This is a prototype, not a verdict."

### Slide 5 · Close (2:45–2:55)
[Switch to slide 5, Built with.]
"Built on Gnani's speech-to-text, with FastAPI, Next.js and Supabase. Try it yourself, the link is below. I'm Abhinav. Hashtag GnaniAI."

## If it goes wrong on camera

- **Upload says the passcode is wrong:** check for a stray space and retype. You can cut and retake.
- **"Server is waking up" banner:** wait; it fills in by itself in under a minute. This is why you wake it first.
- **Stuck on Queued for over two minutes:** switch to the backup tab and say so.
- **A flag is missing or an extra one appears:** say it plainly ("it caught two of the three I planted") and carry on. Honest beats polished, and the Accuracy page already says the sample is small.
- **Running over three minutes:** drop Slide 5 and end on the Accuracy page with "Link below, hashtag GnaniAI."

## After recording

Edit out dead time (the upload wait), export at 1080p, and upload the video to LinkedIn and/or X. Paste the post from `social_post.md` (replace `{{PASSCODE}}` first). Then fill in the form: your name, email, institution, the project URL (use the GitHub link; the README links to the one-page pitch), the video link, and the post link for the bonus category.
