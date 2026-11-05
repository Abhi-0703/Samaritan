from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from app.cli import CONFIGS, build_parser, run_transcribe, script_mix, summarise
from app.config import Settings
from app.services.audio import ffmpeg_available
from app.services.gnani_client import GnaniBatchClient, parse_transcript
from tests.fakes.gnani_fake import FakeGnani
from tests.test_audio import make_audio

pytestmark = pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg and ffprobe are required")

KEY = "test-gnani-key-0000"


def parse(*argv: str):
    return build_parser().parse_args(["transcribe", *argv])


@pytest.fixture
def src(tmp_path: Path) -> Path:
    return make_audio(tmp_path / "call_01.m4a", 5)


def fake_client(fake: FakeGnani) -> GnaniBatchClient:
    return GnaniBatchClient("https://api.vachana.ai", KEY, http=fake.client(), sleep=lambda s: None)


def test_dry_run_sends_nothing_and_shows_cost(src):
    out = io.StringIO()
    fake = FakeGnani(api_key=KEY)
    code = run_transcribe(
        parse(str(src), "--language", "hinglish", "--dry-run"), Settings(), fake_client(fake), out=out
    )
    text = out.getvalue()
    assert code == 0 and fake.requests == []
    assert '"model": "prisma-v3.0"' in text and "Estimated cost: about 0.03 credits" in text
    assert KEY not in text


def test_declining_the_prompt_sends_nothing(src):
    fake = FakeGnani(api_key=KEY)
    out = io.StringIO()
    code = run_transcribe(
        parse(str(src), "--language", "hinglish"), Settings(), fake_client(fake), ask=lambda _: "n", out=out
    )
    assert code == 1 and fake.requests == [] and "Cancelled" in out.getvalue()


def test_confirmed_run_saves_raw_transcript_and_prints_summary(src, tmp_path):
    fake = FakeGnani(api_key=KEY)
    out = io.StringIO()
    dest = tmp_path / "spike"
    code = run_transcribe(
        parse(str(src), "--language", "marathi", "--config", "D", "--out", str(dest)),
        Settings(),
        fake_client(fake),
        ask=lambda _: "y",
        out=out,
    )
    assert code == 0
    saved = json.loads((dest / "call_01_D.json").read_text(encoding="utf-8"))
    assert saved["config"]["with_denoise"] is True and saved["config"]["language_code"] == "mr-IN,en-IN"
    assert len(parse_transcript(saved["transcript"]).segments) == 4
    assert "speaker ids" in out.getvalue() and "Saved:" in out.getvalue()
    assert KEY not in out.getvalue() and KEY not in json.dumps(saved)


def test_the_file_sent_to_gnani_is_converted_audio(src, tmp_path):
    fake = FakeGnani(api_key=KEY)
    run_transcribe(
        parse(str(src), "--language", "hinglish", "--yes", "--out", str(tmp_path / "o")),
        Settings(),
        fake_client(fake),
        out=io.StringIO(),
    )
    job = next(iter(fake.jobs.values()))
    assert job.filename.endswith(".wav") and job.filename.startswith("call_01_A")


def test_gnani_errors_are_reported_without_a_traceback(src):
    fake = FakeGnani(api_key=KEY)
    fake.credits_exhausted = True
    out = io.StringIO()
    code = run_transcribe(parse(str(src), "--language", "hinglish", "--yes"), Settings(), fake_client(fake), out=out)
    assert code == 3 and "Gnani error" in out.getvalue()


def test_missing_file_and_non_audio(tmp_path):
    out = io.StringIO()
    assert run_transcribe(parse(str(tmp_path / "nope.wav"), "--language", "hinglish"), Settings(), out=out) == 2
    bad = tmp_path / "x.wav"
    bad.write_text("text")
    assert run_transcribe(parse(str(bad), "--language", "hinglish"), Settings(), out=io.StringIO()) == 2


def test_all_five_spike_configs_exist_and_c_is_v25():
    assert sorted(CONFIGS) == ["A", "B", "C", "D", "E"]
    assert CONFIGS["C"][1]["model"] == "prisma-v2.5" and CONFIGS["E"][1]["keyterms"]


def test_script_mix_and_summary():
    mix = script_mix("मेरा नाम Rohit hai 5000")
    assert 0 < mix["devanagari"] < 1 and mix["digits"] == 4
    t = parse_transcript({"segments": [{"start_time": 0, "end_time": 1, "text": "hello", "speaker_id": 1}]})
    assert "speaker ids: {1: 1}" in summarise(t)
