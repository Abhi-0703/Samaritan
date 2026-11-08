"""Record a test call alone: you read the AGENT lines into the microphone, a synthetic voice reads the BORROWER lines,
and the clips are joined into one natural-sounding call (plan.md Section 9; docs/decisions.md D-031).

The result is a single mono file in data/audio/, like a real recording, so it exercises the normal upload path where
the transcription service has to tell two voices apart. It is NOT a real two-person call: the borrower is synthetic,
the voices differ a lot, and the evaluation report lists these calls as such (data/audio_meta/call_NN.json).

    api/.venv/bin/python scripts/record_call.py call_14
    api/.venv/bin/python scripts/record_call.py --list-devices
    api/.venv/bin/python scripts/record_call.py call_13 --noise brown --noise-level 0.05

Needs macOS (`say` and `afplay`), ffmpeg, and a microphone the terminal is allowed to use.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import wave
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.evaluation.keys import AUDIO_DIR, REPO_DIR, SCRIPTS_DIR

AUDIO_META_DIR = REPO_DIR / "data" / "audio_meta"
TAKES_DIR = REPO_DIR / "data" / "audio_takes"
RATE = 48000
MARKER = re.compile(r"\s*<<[A-Z0-9, ]+>>\s*")
SPEAKERS = {"AGENT:": "agent", "BORROWER:": "borrower"}


class RecorderError(RuntimeError):
    """Something the person can fix; the message says what."""


class Quit(Exception):
    """The person chose to stop. Takes already recorded are kept."""


# ---- the script ---------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Turn:
    index: int
    speaker: str  # agent | borrower
    text: str
    latin: str | None = None  # the Latin reading aid under a Marathi line


@dataclass
class Script:
    test_key: str
    header: dict[str, str]
    notes: str
    turns: list[Turn] = field(default_factory=list)

    @property
    def language(self) -> str:
        return self.header.get("language", "").lower()


def parse_script(path: Path) -> Script:
    header: dict[str, str] = {}
    notes = ""
    turns: list[Turn] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if line.startswith("[") and line.endswith("]"):
            for part in line[1:-1].split("|"):
                key, _, value = part.partition(":")
                header[key.strip().lower()] = value.strip()
        elif line.startswith("Recording notes:"):
            notes = line.split(":", 1)[1].strip()
        elif raw.lstrip().startswith(">") and turns and raw[:1].isspace():
            last = turns[-1]
            turns[-1] = Turn(last.index, last.speaker, last.text, raw.lstrip()[1:].strip())
        else:
            for prefix, speaker in SPEAKERS.items():
                if line.startswith(prefix):
                    text = MARKER.sub(" ", line[len(prefix) :]).strip()
                    turns.append(Turn(len(turns), speaker, text))
                    break
    if not turns:
        raise RecorderError(f"No AGENT or BORROWER lines found in {path.name}.")
    return Script(path.stem, header, notes, turns)


# ---- audio helpers (ffmpeg) ----------------------------------------------------------------------------------------


def _ffmpeg(*args: str) -> None:
    res = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], capture_output=True, text=True)
    if res.returncode:
        raise RecorderError(f"ffmpeg failed: {res.stderr.strip()[-300:]}")


def duration_s(path: Path) -> float:
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )  # fmt: skip
    try:
        return float(res.stdout.strip())
    except ValueError:  # an empty file has no duration ("N/A")
        return 0.0


TRIM = (
    "silenceremove=start_periods=1:start_silence=0.08:start_threshold={db}dB,areverse,"
    "silenceremove=start_periods=1:start_silence=0.12:start_threshold={db}dB,areverse"
)


def prepare_clip(src: Path, dst: Path, trim_db: float = -42.0) -> None:
    """Cut the silence the keypresses leave at both ends, even the loudness and make every clip the same format."""
    _ffmpeg("-i", str(src), "-af", TRIM.format(db=trim_db) + ",loudnorm=I=-20:TP=-2:LRA=11",
            "-ar", str(RATE), "-ac", "1", "-c:a", "pcm_s16le", str(dst))  # fmt: skip
    if duration_s(dst) < 0.15:
        raise RecorderError(f"{src.name} has no speech in it (too quiet or empty). Record that line again.")


def _read_pcm(path: Path) -> bytes:
    with wave.open(str(path), "rb") as w:
        if (w.getnchannels(), w.getframerate(), w.getsampwidth()) != (1, RATE, 2):
            raise RecorderError(f"{path.name} is not 48 kHz mono 16-bit.")
        return w.readframes(w.getnframes())


@dataclass(frozen=True)
class Noise:
    kind: str | None = None  # white | pink | brown
    file: Path | None = None
    level: float = 0.04  # linear gain on the noise, about -28 dB

    def describe(self) -> dict | None:
        if self.file:
            return {"file": self.file.name, "level": self.level}
        return {"synthetic": self.kind, "level": self.level} if self.kind else None


def assemble(clips: list[tuple[Turn, Path]], out_path: Path, *, seed: int = 0, noise: Noise | None = None) -> float:
    """Join the clips into one call with natural pauses, optionally under noise. Returns the duration in seconds."""
    rng = random.Random(seed)
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        pcm = bytearray()
        previous: Turn | None = None
        for turn, path in clips:
            prepared = tmpdir / f"{turn.index:03d}.wav"
            prepare_clip(path, prepared)
            if previous is not None:  # a turn change takes a little longer than a pause inside one speaker's turn
                gap = rng.uniform(0.25, 0.75) if previous.speaker != turn.speaker else rng.uniform(0.1, 0.3)
                pcm += b"\x00\x00" * int(RATE * gap)
            pcm += _read_pcm(prepared)
            previous = turn
        joined = tmpdir / "joined.wav"
        with wave.open(str(joined), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(bytes(pcm))

        out_path.parent.mkdir(parents=True, exist_ok=True)
        encode = ["-c:a", "aac", "-b:a", "128k", "-ar", str(RATE), "-ac", "1", str(out_path)]
        if noise and (noise.kind or noise.file):
            if noise.file:
                source = ["-stream_loop", "-1", "-i", str(noise.file)]
            else:
                source = ["-f", "lavfi", "-i", f"anoisesrc=color={noise.kind}:sample_rate={RATE}:amplitude=0.5"]
            _ffmpeg("-i", str(joined), *source, "-filter_complex",
                    f"[1:a]volume={noise.level}[n];[0:a][n]amix=inputs=2:duration=first:normalize=0",
                    *encode)  # fmt: skip
        else:
            _ffmpeg("-i", str(joined), *encode)
    return duration_s(out_path)


# ---- the session --------------------------------------------------------------------------------------------------


@dataclass
class IO:
    """Everything that touches the person or the machine, so a session can be tested without either."""

    ask: Callable[[str], str]
    show: Callable[[str], None]
    record: Callable[[Path], None]  # blocks until the person stops; writes a WAV
    speak: Callable[[str, Path], None]  # synthetic voice to a WAV
    play: Callable[[Path], None]


def collect_clips(script: Script, workdir: Path, io: IO, *, resume: bool = True) -> list[tuple[Turn, Path]]:
    """Walk the script. Agent lines are recorded (or kept from an earlier take); borrower lines are spoken aloud."""
    workdir.mkdir(parents=True, exist_ok=True)
    n = len(script.turns)
    clips: list[tuple[Turn, Path]] = []
    for turn in script.turns:
        path = workdir / f"turn_{turn.index:03d}_{turn.speaker}.wav"
        label = f"[{turn.index + 1}/{n}]"
        if turn.speaker == "borrower":
            if not (resume and path.exists()):
                io.speak(turn.text, path)
            io.show(f"{label} BORROWER (synthetic voice): {turn.text}")
            io.play(path)
            clips.append((turn, path))
            continue

        while True:
            if resume and path.exists():
                io.show(f"{label} YOU (earlier take kept): {turn.text}")
                answer = io.ask("  Enter = keep it, r = record it again, q = quit and save: ").strip().lower()
                if answer == "q":
                    raise Quit
                if answer != "r":
                    break
                path.unlink()
                continue
            io.show(f"\n{label} YOU, read this line:\n    {turn.text}")
            if turn.latin:
                io.show(f"    ({turn.latin})")
            if io.ask("  Press Enter, then speak (q = quit and save): ").strip().lower() == "q":
                raise Quit
            io.record(path)
            while True:
                answer = io.ask("  Enter = keep, r = redo, p = play it back, q = quit and save: ").strip().lower()
                if answer == "p":
                    io.play(path)
                    continue
                break
            if answer == "q":
                raise Quit
            if answer == "r":
                path.unlink(missing_ok=True)
                continue
            break
        clips.append((turn, path))
    return clips


# ---- the machine --------------------------------------------------------------------------------------------------


def list_audio_devices() -> list[tuple[int, str]]:
    res = subprocess.run(
        ["ffmpeg", "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
        capture_output=True, text=True,
    )  # fmt: skip
    devices, in_audio = [], False
    for line in res.stderr.splitlines():
        if "AVFoundation audio devices" in line:
            in_audio = True
        elif in_audio:
            m = re.search(r"\[(\d+)\]\s+(.+)$", line)
            if m:
                devices.append((int(m[1]), m[2].strip()))
    return devices


def pick_device(devices: list[tuple[int, str]], wanted: int | None = None) -> tuple[int, str]:
    """The built-in microphone unless told otherwise: Bluetooth earbuds drop to phone quality while recording."""
    if not devices:
        raise RecorderError("No microphone found. Check System Settings > Sound > Input.")
    if wanted is not None:
        for d in devices:
            if d[0] == wanted:
                return d
        raise RecorderError(f"No audio device number {wanted}. Run with --list-devices.")
    for d in devices:
        if re.search(r"built-in|macbook|imac|mac mini|studio display", d[1], re.I) and "camera" not in d[1].lower():
            return d
    return devices[0]


def mic_recorder(device: int, prompt: Callable[[str], str], show: Callable[[str], None]) -> Callable[[Path], None]:
    def record(path: Path) -> None:
        proc = subprocess.Popen(
            ["ffmpeg", "-hide_banner", "-y", "-f", "avfoundation", "-i", f":{device}", "-ac", "1", "-ar", str(RATE),
             str(path)],
            stdin=subprocess.PIPE, stderr=subprocess.PIPE,
        )  # fmt: skip
        ready, log = threading.Event(), bytearray()

        def drain() -> None:
            assert proc.stderr is not None
            for line in iter(proc.stderr.readline, b""):
                log.extend(line)
                if b"Press [q]" in line:
                    ready.set()

        threading.Thread(target=drain, daemon=True).start()
        if not ready.wait(5) or proc.poll() is not None:
            proc.kill()
            raise RecorderError(
                "The microphone could not be opened. If macOS asked for microphone access, allow it for your terminal "
                "(System Settings > Privacy & Security > Microphone) and try again.\n"
                + log.decode(errors="replace")[-300:]
            )
        show("  ● RECORDING. Speak now, then press Enter to stop.")
        prompt("")
        try:
            assert proc.stdin is not None
            proc.stdin.write(b"q")
            proc.stdin.flush()
        except OSError:
            pass
        proc.wait(timeout=10)
        if not path.exists() or path.stat().st_size < 2000:
            raise RecorderError("Nothing was recorded. Check the microphone and try that line again.")

    return record


def have_voice(voice: str) -> bool:
    res = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
    return any(line.split()[0] == voice for line in res.stdout.splitlines() if line.strip())


def say_speaker(voice: str, rate: int) -> Callable[[str, Path], None]:
    def speak(text: str, path: Path) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            aiff = Path(tmp) / "t.aiff"
            res = subprocess.run(
                ["say", "-v", voice, "-r", str(rate), "-o", str(aiff), "--", text], capture_output=True, text=True
            )
            if res.returncode or not aiff.exists():
                raise RecorderError(f"The voice '{voice}' could not read a line: {res.stderr.strip()}")
            _ffmpeg("-i", str(aiff), "-ar", str(RATE), "-ac", "1", "-c:a", "pcm_s16le", str(path))

    return speak


def afplay(path: Path) -> None:
    subprocess.run(["afplay", str(path)], check=False)


# ---- provenance ---------------------------------------------------------------------------------------------------


def write_provenance(script: Script, *, voice: str, rate: int, noise: Noise | None, seconds: float,
                     directory: Path = AUDIO_META_DIR) -> Path:  # fmt: skip
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{script.test_key}.json"
    agent_turns = sum(t.speaker == "agent" for t in script.turns)
    path.write_text(
        json.dumps(
            {
                "test_key": script.test_key,
                "agent": "human, microphone",
                "borrower": "synthetic",
                "voice": voice,
                "voice_rate": rate,
                "noise": noise.describe() if noise else None,
                "turns": {"agent": agent_turns, "borrower": len(script.turns) - agent_turns},
                "duration_s": round(seconds, 1),
                "made_with": "scripts/record_call.py",
                "made_at": datetime.now(UTC).isoformat(timespec="seconds"),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def load_provenance(directory: Path = AUDIO_META_DIR) -> dict[str, dict]:
    if not directory.exists():
        return {}
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("call_*.json"))}


# ---- command line -------------------------------------------------------------------------------------------------


def main(argv: list[str] | None = None, io: IO | None = None) -> int:
    p = argparse.ArgumentParser(prog="record_call", description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("test_key", nargs="?", help="for example call_14 (the script is data/scripts/call_14.md)")
    p.add_argument("--list-devices", action="store_true", help="show the microphones and exit")
    p.add_argument("--device", type=int, help="microphone number from --list-devices (default: the built-in one)")
    p.add_argument(
        "--voice", default="Rishi", help="the borrower's voice; see `say -v '?'` (default Rishi, Indian English)"
    )
    p.add_argument("--rate", type=int, default=165, help="words per minute for the borrower (default 165)")
    p.add_argument(
        "--noise", choices=["white", "pink", "brown"], help="mix in synthetic noise (brown is rumbly, like traffic)"
    )
    p.add_argument("--noise-file", type=Path, help="mix in a noise recording (looped) instead")
    p.add_argument("--noise-level", type=float, default=0.04, help="noise gain, 0.02 faint to 0.12 loud (default 0.04)")
    p.add_argument("--fresh", action="store_true", help="throw away earlier takes and start over")
    p.add_argument("--assemble-only", action="store_true", help="join the takes that exist, without recording")
    p.add_argument("--overwrite", action="store_true", help="replace data/audio/<call>.m4a if it exists")
    p.add_argument("--dry-run", action="store_true", help="show the script as it would be recorded and stop")
    p.add_argument("--seed", type=int, default=0, help="seed for the pause lengths")
    p.add_argument("--audio-dir", type=Path, default=AUDIO_DIR)
    p.add_argument("--scripts-dir", type=Path, default=SCRIPTS_DIR)
    p.add_argument("--takes-dir", type=Path, default=TAKES_DIR)
    p.add_argument("--meta-dir", type=Path, default=AUDIO_META_DIR)
    args = p.parse_args(argv)
    out = print

    try:
        if shutil.which("ffmpeg") is None:
            raise RecorderError("ffmpeg is not installed (brew install ffmpeg).")
        if args.list_devices:
            for number, name in list_audio_devices():
                out(f"  [{number}] {name}")
            return 0
        if not args.test_key:
            p.error("give a call such as call_14, or --list-devices")
        script = parse_script(args.scripts_dir / f"{args.test_key}.md")
        target = args.audio_dir / f"{script.test_key}.m4a"
        if script.language == "marathi" and args.voice == "Rishi":
            raise RecorderError(
                "This is a Marathi call and this Mac has no Marathi voice, so a synthetic borrower would be read "
                "wrongly and spoil the test. Record Marathi calls with a real second person."
            )
        if target.exists() and not args.overwrite and not args.dry_run:
            raise RecorderError(f"{target} already exists. Use --overwrite to replace it.")

        agent_lines = sum(t.speaker == "agent" for t in script.turns)
        out(
            f"\n{script.test_key}: {len(script.turns)} lines, {agent_lines} for you and "
            f"{len(script.turns) - agent_lines} for the borrower."
        )
        out(f"Header: {' | '.join(f'{k}: {v}' for k, v in script.header.items())}")
        out(f"Notes for you (do NOT read these aloud): {script.notes}\n")
        noisy = script.header.get("noise", "quiet").lower() not in ("quiet", "")
        if noisy and not (args.noise or args.noise_file):
            out(
                f"Hint: this call is meant to be noisy ({script.header['noise']}). "
                "Add --noise brown --noise-level 0.06 (or --noise-file).\n"
            )
        if args.dry_run:
            for t in script.turns:
                out(f"  {t.speaker.upper():9} {t.text}")
            return 0
        noise = Noise(args.noise, args.noise_file, args.noise_level) if (args.noise or args.noise_file) else None

        workdir = args.takes_dir / script.test_key
        if args.fresh and workdir.exists():
            shutil.rmtree(workdir)
        if args.assemble_only:
            existing = sorted(workdir.glob("turn_*.wav"))
            if len(existing) != len(script.turns):
                raise RecorderError(
                    f"Only {len(existing)} of {len(script.turns)} lines have a take. Record the rest first."
                )
            clips = [(t, workdir / f"turn_{t.index:03d}_{t.speaker}.wav") for t in script.turns]
        else:
            if not have_voice(args.voice):
                raise RecorderError(f"The voice '{args.voice}' is not installed. Run `say -v '?'` to see the choices.")
            if io is None:
                device, name = pick_device(list_audio_devices(), args.device)
                out(f"Microphone: [{device}] {name}. Use headphones or keep the volume low.")
                out("Read only the line shown, in your own voice. Do not read the header or notes. Fillers are fine.\n")
                io = IO(input, out, mic_recorder(device, input, out), say_speaker(args.voice, args.rate), afplay)
            clips = collect_clips(script, workdir, io, resume=not args.fresh)

        out("\nJoining the lines into one recording ...")
        seconds = assemble(clips, target, seed=args.seed, noise=noise)
        write_provenance(
            script, voice=args.voice, rate=args.rate, noise=noise, seconds=seconds, directory=args.meta_dir
        )
        out(f"Saved {target} ({seconds:.0f} s). It is marked as a synthetic-borrower call in {args.meta_dir.name}/.")
        if seconds < 90:
            out("Note: shorter than 90 seconds. That is fine for the pipeline but the plan asks for 1.5 to 3 minutes.")
        return 0
    except Quit:
        out("\nStopped. Your takes are saved; run the same command again to carry on where you left off.")
        return 0
    except RecorderError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
