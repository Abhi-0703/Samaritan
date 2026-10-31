# Recording guide

You and a friend act out 30 fake loan-recovery calls from the scripts in `data/scripts/`. These recordings are the evaluation set for Samaritan, so the goal is calls that sound like real phone calls, not a reading of text.

All people, numbers and loans in the scripts are fictional. Do not use anyone's real name, number, account or Aadhaar. Record only yourselves.

## 1. Roles and reading a script

- **You** play the AGENT (the recovery agent). **Your friend** plays the BORROWER. In a few scripts the "borrower" is really a relative or colleague of the borrower (see the header and recording notes).
- Read the `[header line]` and **Recording notes** first. They say the time to log, the noise to use, and the tone.
- **Speak naturally.** Add fillers ("umm", "haan haan", "arre"), short interruptions and pauses. Do not read at a flat pace.
- **Markers like `<<V5>>` at the end of a line are never spoken.** They tell the answer key which line breaks which rule. Leave them out.
- **Lines with a marker must keep the key words as written.** The answer key points at those words (`quote_hint`). You may change grammar to fit your voice (raha/rahi, karta/karti), but do not soften or remove the threat, insult or false claim.
- Other lines can be paraphrased freely. Do not add new threats, insults, pressure or disclosures anywhere, because the answer key would then be wrong. If something slips out, record that call again.
- **Marathi scripts** are in Devanagari. The line under each, starting with `>`, is a Latin spelling only to help you read aloud. Do not read the `>` lines as extra dialogue.
- **Calls with a V8 marker** (`call_16`, `call_21`, `call_28`): the agent must never say his own name or "Sahyog Finance" during the whole call. Be careful not to slip.
- **Call lengths** should come out between 1.5 and 3 minutes. The 8-minute system limit is not a concern.

## 2. The call time (important)

The `Time:` in each script header is the time the call will be **logged** as in Samaritan, in Indian Standard Time. You do not have to record at that time of day. You will enter it when you upload or seed the call. It decides the "outside permitted hours" check (V1), so keep it exactly as the header says.

- `call_07`, `call_13`, `call_19`, `call_26` are intentionally outside 08:00 to 19:00. That is their only schedule-related violation.
- `call_22` is logged at exactly 19:00, which is allowed.
- `call_12` is logged at 20:30 but the borrower asked for that time. When uploading it, tick "Borrower asked for this call time".

## 3. How to record

Pick one method and use it for all calls where possible.

1. **Real phone call on speaker.** Call each other and record with a call-recorder app, or put a second device on speaker next to the phone. Good for natural audio. Note that Android and iPhone call-recording rules differ; a voice-memo app next to the speaker always works.
2. **Voice memo on one phone, both of you close together.** Simple and reliable. Speaker separation then depends on the transcription service telling two voices apart.
3. **Separate recordings, one per person** (each records their own side while on a call). Merge into one stereo file with the command in section 6. This is only needed for **one or two calls**, to test how Gnani handles separate channels. Do not do it for all 30.

Practical tips:
- Quiet room unless the script says noise. Keep the phone about 30 cm from your mouth. No headphones crackle.
- Speak at normal phone volume, not whispering or shouting, except where the notes ask for a raised voice.
- If you stumble, keep going if it still sounds natural. Otherwise start the call again.

## 4. File naming and size

- One file per call, named exactly like the script: `call_01.m4a`, `call_02.m4a` and so on. `.wav`, `.mp3`, `.ogg` and `.flac` also work. Keep each under **25 MB** (a 3-minute m4a is well below that).
- Put every file in **`data/audio/`**. That folder is git-ignored, so recordings are never committed.
- Do not rename after recording. The test key (`call_07`) is how the system matches a recording to its answer key.

## 5. Noisy calls

Eight calls are recorded with background noise (the header `Noise:` field says which: traffic, fan or office): `call_10`, `call_11`, `call_13`, `call_18`, `call_20`, `call_23`, `call_24`, `call_30`.

Two ways:
- **Record with real noise**: an open window for traffic, a fan or table fan next to the phone, or office chatter and keyboard sounds played from a laptop at a normal volume.
- **Mix noise in afterwards** with ffmpeg (section 6). Keep the speech clearly audible: a person should still be able to follow every word.

## 6. ffmpeg recipes

ffmpeg is not installed yet on this machine. On macOS: `brew install ffmpeg`.

Mix a noise file into a recording (noise looped, at about 25% volume):

```bash
ffmpeg -i call_10_clean.m4a -stream_loop -1 -i traffic.mp3 \
  -filter_complex "[1:a]volume=0.25[n];[0:a][n]amix=inputs=2:duration=first:normalize=0" \
  -c:a aac call_10.m4a
```

Merge two single-person recordings into one stereo file (agent on the left channel, borrower on the right):

```bash
ffmpeg -i agent_side.m4a -i borrower_side.m4a \
  -filter_complex "[0:a][1:a]join=inputs=2:channel_layout=stereo[a]" \
  -map "[a]" call_01.wav
```

Check a file's length and format:

```bash
ffprobe -hide_banner call_01.m4a
```

Use a noise sample you recorded yourself or a free, royalty-free one.

## 7. What to record first

The first real Gnani test (Phase 2) needs at least 5 recordings, including 2 Hinglish, 1 Marathi and 1 noisy:

1. `call_01` (Hinglish, clean, quiet)
2. `call_10` (Hinglish, noisy)
3. `call_05` (Marathi)
4. `call_02` (Hinglish, two violations)
5. `call_16` (Hinglish, missing introduction)

Then record the rest. The minimum useful set is 20 calls. All 30 are needed for the final evaluation. If you can, record `call_01` a second time as a separate-channel stereo file for the channel test.

## 8. After recording

1. Copy the files into `data/audio/`.
2. Tell the agent the files are in place. Nothing is sent to Gnani until you approve the first real call and the full run.
3. Later (Phase 2, after transcripts are cached) you will run `eval/label_times.py`. It prints each call's transcript with segment numbers and asks which segment holds each expected violation. That fills in `approx_time_s` in the answer keys. Expect about 10 minutes for all 30 calls.

## 9. Script checks

`python3 scripts/check_testset.py` verifies that scripts and answer keys agree (markers, quotes, times, languages, counts) and regenerates `data/COVERAGE.md`. Run it after any change to a script or key.
