"""Command line tools. The transcription spike (plan.md step 2.2) runs through here:

    python -m app.cli transcribe ../data/audio/call_01.m4a --language hinglish --config A

Every real run asks for confirmation first, because it spends Gnani credits (about 0.33 credits per audio minute).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from app.config import API_DIR, Settings, get_settings
from app.services import audio
from app.services.gnani_client import GnaniBatchClient, GnaniError, Transcript, build_config, client_from_settings

CREDITS_PER_MINUTE = 20 / 60  # Rs 20 per hour of audio, 1 credit = Rs 1 (docs/gnani-findings.md)
KEYTERMS = ["EMI", "overdue", "Sahyog Finance", "loan", "payment", "legal notice", "credit bureau"]

# Spike configurations from plan.md step 2.2. A is the default under test; the others change one thing.
CONFIGS = {
    "A": ("v3.0, hi-IN,en-IN (mr-IN,en-IN for Marathi), format transcribe", {}),
    "B": ("v3.0 with format codemix", {"format": "codemix"}),
    "C": ("v2.5, en-IN for Hinglish or mr-IN for Marathi", {"model": "prisma-v2.5"}),
    "D": ("A plus denoise", {"with_denoise": True}),
    "E": ("A plus keyterms", {"keyterms": KEYTERMS}),
}

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
LATIN = re.compile(r"[A-Za-z]")


def script_mix(text: str) -> dict[str, float]:
    dev, lat = len(DEVANAGARI.findall(text)), len(LATIN.findall(text))
    total = max(dev + lat, 1)
    return {"devanagari": dev / total, "latin": lat / total, "digits": len(re.findall(r"\d", text))}  # type: ignore[dict-item]


def summarise(t: Transcript, lines: int = 6) -> str:
    speakers = Counter(s.speaker_id for s in t.segments)
    mix = script_mix(" ".join(s.text for s in t.segments))
    out = [
        f"segments: {len(t.segments)}   duration: {t.duration_s}   model: {t.model}   language: {t.language_code}",
        f"speaker ids: {dict(speakers)}   devanagari {mix['devanagari']:.0%}, latin {mix['latin']:.0%}, "
        f"digits {int(mix['digits'])}",
        "first lines:",
    ]
    for s in t.segments[:lines]:
        out.append(f"  [{s.start_s:6.1f}-{s.end_s:6.1f}] speaker {s.speaker_id}: {s.text}")
    return "\n".join(out)


def run_transcribe(
    args: argparse.Namespace,
    settings: Settings,
    client: GnaniBatchClient | None = None,
    ask: Callable[[str], str] = input,
    out=sys.stdout,
) -> int:
    src = Path(args.audio).expanduser()
    if not src.exists():
        print(f"File not found: {src}", file=out)
        return 2
    desc, overrides = CONFIGS[args.config]
    overrides = dict(overrides)
    if args.multi_channel:
        overrides["is_multi_channel"] = True
    config = build_config(args.language, settings, **overrides)

    try:
        info = audio.probe(src)
    except audio.AudioError as e:
        print(f"Cannot use this file: {e.message}", file=out)
        return 2
    cost = info.duration_s / 60 * CREDITS_PER_MINUTE
    print(f"Config {args.config}: {desc}", file=out)
    print(json.dumps(config, ensure_ascii=False), file=out)
    print(
        f"Audio: {src.name}, {info.duration_s:.1f} s, {info.channels} channel(s). "
        f"Estimated cost: about {cost:.2f} credits.",
        file=out,
    )
    if args.dry_run:
        print("Dry run: nothing was sent.", file=out)
        return 0
    if not settings.gnani_api_key.get_secret_value():
        print("GNANI_API_KEY is empty. Put it in api/.env.", file=out)
        return 2
    if not args.yes and ask("This will spend Gnani credits. Continue? [y/N] ").strip().lower() not in {"y", "yes"}:
        print("Cancelled. Nothing was sent.", file=out)
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        prepared = audio.prepare_for_gnani(
            src, Path(tmp), f"{src.stem}_{args.config}", multi_channel=args.multi_channel
        )
        client = client or client_from_settings(settings)

        def on_status(s):
            print(f"  job {s.status} {s.progress or ''}", file=out)

        try:
            transcript, job_id, sent = client.transcribe(
                prepared.path,
                config,
                on_job_created=lambda j, _: print(f"  job created: {j}", file=out),
                on_status=on_status,
                poll_seconds=settings.gnani_poll_seconds,
            )
        except GnaniError as e:
            print(f"Gnani error {e.code}: {e.message}", file=out)
            return 3

    dest = Path(args.out) if args.out else API_DIR / ".data" / "spike"
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{src.stem}_{args.config}.json"
    path.write_text(
        json.dumps({"config": sent, "job_id": job_id, "transcript": transcript.raw}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(summarise(transcript), file=out)
    print(f"Saved: {path}", file=out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m app.cli")
    sub = p.add_subparsers(dest="command", required=True)
    t = sub.add_parser("transcribe", help="Transcribe one recording with Gnani Batch STT (spends credits)")
    t.add_argument("audio")
    t.add_argument("--language", choices=["hinglish", "marathi"], required=True)
    t.add_argument("--config", choices=sorted(CONFIGS), default="A")
    t.add_argument("--multi-channel", action="store_true", help="Keep stereo and set is_multi_channel")
    t.add_argument("--out", help="Folder for the raw transcript JSON (default api/.data/spike)")
    t.add_argument("--dry-run", action="store_true", help="Show the config and cost, send nothing")
    t.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "transcribe":
        return run_transcribe(args, get_settings())
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
