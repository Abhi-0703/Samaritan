"""Audio preparation (plan.md Section 7.6): probe, validate and convert uploads for Gnani.

Gnani wants 16 kHz mono 16-bit WAV (about 1.9 MB a minute). If that exceeds 9.5 MB it is re-encoded as FLAC, and if
that is still too big the call fails with a clear message. The batch API checks the file extension, so only .wav and
.flac are ever sent.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".flac"}
GNANI_MAX_BYTES = int(9.5 * 1024 * 1024)  # Gnani's limit is 10 MB per file; keep a margin
FFMPEG_TIMEOUT_S = 180


class AudioError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass
class AudioInfo:
    duration_s: float
    codec: str
    channels: int
    sample_rate: int
    format_name: str


@dataclass
class PreparedAudio:
    path: Path
    format: str  # "wav" or "flac"
    duration_s: float
    size_bytes: int
    channels: int


def ffmpeg_available() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    if not ffmpeg_available():
        raise AudioError("ffmpeg_missing", "ffmpeg is not installed on the server.", 500)
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT_S, check=False)
    except subprocess.TimeoutExpired as e:
        raise AudioError("audio_timeout", "Converting the audio took too long.", 422) from e


def probe(path: Path) -> AudioInfo:
    """Read the first audio stream with ffprobe. Anything without one is rejected as not audio."""
    out = _run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    if out.returncode != 0:
        raise AudioError("unsupported_media", "That file is not a readable audio file.")
    try:
        data = json.loads(out.stdout or "{}")
    except ValueError as e:
        raise AudioError("unsupported_media", "That file is not a readable audio file.") from e
    audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    if audio is None:
        raise AudioError("unsupported_media", "That file has no audio track.")
    fmt = data.get("format", {})
    raw_duration = fmt.get("duration") or audio.get("duration")
    try:
        duration = float(raw_duration)
    except (TypeError, ValueError) as e:
        raise AudioError("unsupported_media", "The audio length could not be read.") from e
    if duration <= 0:
        raise AudioError("unsupported_media", "The audio is empty.")
    return AudioInfo(
        duration_s=duration,
        codec=str(audio.get("codec_name", "")),
        channels=int(audio.get("channels") or 1),
        sample_rate=int(audio.get("sample_rate") or 0),
        format_name=str(fmt.get("format_name", "")),
    )


def validate_upload(path: Path, filename: str, *, max_mb: int, max_call_minutes: int) -> AudioInfo:
    """Checks for an upload: extension allow-list, size, real audio content, and length."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise AudioError("unsupported_media", f"{filename} is not a supported type. Use wav, mp3, m4a, ogg or flac.")
    if path.stat().st_size > max_mb * 1024 * 1024:
        raise AudioError("file_too_large", f"{filename} is larger than {max_mb} MB.", 413)
    info = probe(path)
    if info.duration_s > max_call_minutes * 60:
        raise AudioError(
            "audio_too_long",
            f"{filename} is {info.duration_s / 60:.1f} minutes long; the limit is {max_call_minutes} minutes.",
        )
    return info


def _convert(src: Path, dst: Path, codec: list[str], channels: int) -> None:
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vn", "-ac", str(channels), "-ar", "16000", *codec, str(dst)]
    out = _run(cmd)
    if out.returncode != 0 or not dst.exists():
        raise AudioError("audio_conversion_failed", "The audio could not be converted for transcription.", 422)


def prepare_for_gnani(
    src: Path, out_dir: Path, stem: str, *, multi_channel: bool = False, max_bytes: int = GNANI_MAX_BYTES
) -> PreparedAudio:
    """16 kHz 16-bit WAV (mono unless `multi_channel`), falling back to FLAC when WAV is too big for Gnani."""
    out_dir.mkdir(parents=True, exist_ok=True)
    info = probe(src)
    channels = 2 if multi_channel and info.channels >= 2 else 1
    wav = out_dir / f"{stem}.wav"
    _convert(src, wav, ["-c:a", "pcm_s16le"], channels)
    if wav.stat().st_size <= max_bytes:
        return PreparedAudio(wav, "wav", info.duration_s, wav.stat().st_size, channels)
    flac = out_dir / f"{stem}.flac"
    _convert(src, flac, ["-c:a", "flac"], channels)
    wav.unlink(missing_ok=True)
    if flac.stat().st_size > max_bytes:
        flac.unlink(missing_ok=True)
        raise AudioError(
            "audio_too_large_for_transcription",
            "This recording is too large to send for transcription even after compression. "
            "Shorten it or record at lower quality.",
            422,
        )
    return PreparedAudio(flac, "flac", info.duration_s, flac.stat().st_size, channels)
