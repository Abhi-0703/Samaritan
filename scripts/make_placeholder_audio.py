#!/usr/bin/env python3
"""Generate the placeholder call audio used by the Phase 1 mock client (standard library only).

The files are synthetic tones shaped like alternating speakers; they contain no speech.
Usage: python3 scripts/make_placeholder_audio.py
"""
import math
import random
import struct
import wave
from pathlib import Path

RATE = 8000
OUT = Path(__file__).resolve().parent.parent / "web" / "public" / "audio"
FILES = {"call-a.wav": 105, "call-b.wav": 140, "call-c.wav": 180}


def render(seconds: int, seed: int) -> bytes:
    rng = random.Random(seed)
    n = RATE * seconds
    samples = [128] * n
    t = 1.0
    speaker = 0
    while t < seconds - 2:
        length = rng.uniform(2.0, 6.5)
        f0 = (118, 205)[speaker] * rng.uniform(0.94, 1.08)
        syll = rng.uniform(3.2, 4.6)
        phase = 0.0
        start = int(t * RATE)
        stop = min(n, int((t + length) * RATE))
        for i in range(start, stop):
            x = (i - start) / RATE
            env = 0.5 + 0.5 * math.sin(2 * math.pi * syll * x + 1.1)
            fade = min(1.0, x / 0.08, (length - x) / 0.12)
            phase += 2 * math.pi * f0 * (1 + 0.03 * math.sin(2 * math.pi * 0.7 * x)) / RATE
            v = (math.sin(phase) + 0.5 * math.sin(2 * phase) + 0.25 * math.sin(3 * phase)) * env * max(0.0, fade)
            samples[i] = max(0, min(255, int(128 + v * 38)))
        t += length + rng.uniform(0.3, 1.1)
        speaker ^= 1
    return bytes(samples)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for i, (name, secs) in enumerate(FILES.items()):
        with wave.open(str(OUT / name), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(1)
            w.setframerate(RATE)
            w.writeframes(render(secs, seed=7 + i))
        print(f"wrote {name} ({secs}s)")


if __name__ == "__main__":
    main()
