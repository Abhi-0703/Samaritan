from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from app.services import audio
from app.services.audio import AudioError, ffmpeg_available, prepare_for_gnani, probe, validate_upload

pytestmark = pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg and ffprobe are required")


def make_audio(
    path: Path, seconds: float, *, rate: int = 44100, channels: int = 2, source: str = "sine=frequency=440"
) -> Path:
    """Generate a test file with ffmpeg. The extension picks the container."""
    cmd = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"{source}:duration={seconds}:sample_rate={rate}",
        "-ac",
        str(channels),
        str(path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return path


def streams(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)["streams"][0]


@pytest.mark.parametrize("ext", [".wav", ".mp3", ".m4a", ".ogg", ".flac"])
def test_probe_reads_every_allowed_format(tmp_path, ext):
    info = probe(make_audio(tmp_path / f"a{ext}", 3.0))
    assert 2.8 < info.duration_s < 3.3 and info.channels == 2 and info.sample_rate > 0


def test_probe_rejects_text_pretending_to_be_audio(tmp_path):
    fake = tmp_path / "call.wav"
    fake.write_text("this is not audio")
    with pytest.raises(AudioError) as e:
        probe(fake)
    assert e.value.code == "unsupported_media"


def test_probe_rejects_a_file_with_no_audio_track(tmp_path):
    video = tmp_path / "v.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=1", str(video)],
        check=True,
        capture_output=True,
    )
    with pytest.raises(AudioError) as e:
        probe(video)
    assert e.value.code == "unsupported_media"


def test_validate_accepts_a_normal_call(tmp_path):
    f = make_audio(tmp_path / "ok.m4a", 5)
    assert validate_upload(f, "ok.m4a", max_mb=25, max_call_minutes=8).duration_s > 4


def test_validate_rejects_unlisted_extension_even_if_it_is_audio(tmp_path):
    f = make_audio(tmp_path / "ok.wav", 2)
    renamed = f.rename(tmp_path / "ok.aac")
    with pytest.raises(AudioError) as e:
        validate_upload(renamed, "ok.aac", max_mb=25, max_call_minutes=8)
    assert e.value.code == "unsupported_media"


def test_validate_rejects_oversize_files(tmp_path):
    f = make_audio(tmp_path / "big.wav", 20, rate=44100, channels=2)  # ~3.5 MB
    with pytest.raises(AudioError) as e:
        validate_upload(f, "big.wav", max_mb=1, max_call_minutes=8)
    assert e.value.code == "file_too_large" and e.value.status_code == 413


def test_validate_rejects_calls_over_the_length_limit(tmp_path):
    f = make_audio(tmp_path / "long.wav", 75, rate=8000, channels=1)
    with pytest.raises(AudioError) as e:
        validate_upload(f, "long.wav", max_mb=25, max_call_minutes=1)
    assert e.value.code == "audio_too_long" and "limit is 1 minutes" in e.value.message


def test_prepare_makes_16k_mono_16bit_wav(tmp_path):
    src = make_audio(tmp_path / "in.mp3", 4, rate=44100, channels=2)
    out = prepare_for_gnani(src, tmp_path / "out", "call_01")
    s = streams(out.path)
    assert out.path.suffix == ".wav" and out.format == "wav"
    assert (s["codec_name"], int(s["sample_rate"]), int(s["channels"])) == ("pcm_s16le", 16000, 1)
    assert 3.5 < out.duration_s < 4.5 and out.size_bytes == out.path.stat().st_size


def test_prepare_keeps_stereo_only_when_multichannel_is_requested(tmp_path):
    src = make_audio(tmp_path / "in.wav", 3, channels=2)
    assert streams(prepare_for_gnani(src, tmp_path / "o1", "a", multi_channel=True).path)["channels"] == 2
    assert streams(prepare_for_gnani(src, tmp_path / "o2", "a", multi_channel=False).path)["channels"] == 1


def test_multichannel_on_a_mono_file_stays_mono(tmp_path):
    src = make_audio(tmp_path / "in.wav", 3, channels=1)
    assert prepare_for_gnani(src, tmp_path / "o", "a", multi_channel=True).channels == 1


def test_prepare_falls_back_to_flac_when_wav_is_too_big(tmp_path):
    src = make_audio(tmp_path / "in.wav", 30, rate=16000, channels=1)  # ~1 MB as WAV, tiny as FLAC
    out = prepare_for_gnani(src, tmp_path / "out", "c", max_bytes=200_000)
    assert out.format == "flac" and out.path.suffix == ".flac" and out.size_bytes <= 200_000
    assert not (tmp_path / "out" / "c.wav").exists()


def test_prepare_fails_clearly_when_even_flac_is_too_big(tmp_path):
    src = make_audio(tmp_path / "noise.wav", 20, rate=16000, channels=1, source="anoisesrc=color=white")
    with pytest.raises(AudioError) as e:
        prepare_for_gnani(src, tmp_path / "out", "n", max_bytes=100_000)
    assert e.value.code == "audio_too_large_for_transcription"
    assert list((tmp_path / "out").glob("*")) == []  # nothing left behind


def test_prepare_never_sends_an_unlisted_extension(tmp_path):
    src = make_audio(tmp_path / "in.ogg", 2)
    assert prepare_for_gnani(src, tmp_path / "out", "x").path.suffix in {".wav", ".flac"}


def test_missing_ffmpeg_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(audio.shutil, "which", lambda _: None)
    with pytest.raises(AudioError) as e:
        probe(tmp_path / "x.wav")
    assert e.value.code == "ffmpeg_missing" and e.value.status_code == 500
