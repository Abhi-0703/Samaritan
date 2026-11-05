from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.services.gnani_client import (
    GnaniBatchClient,
    GnaniError,
    build_config,
    parse_error,
    parse_transcript,
)
from tests.fakes.gnani_fake import TRANSCRIPT_HOST, FakeGnani

KEY = "test-gnani-key-0000"


@pytest.fixture
def audio(tmp_path: Path) -> Path:
    p = tmp_path / "call_01.wav"
    p.write_bytes(b"RIFF" + b"\x00" * 2000)
    return p


@pytest.fixture
def fake() -> FakeGnani:
    return FakeGnani(api_key=KEY)


def make_client(fake: FakeGnani) -> tuple[GnaniBatchClient, list[float]]:
    sleeps: list[float] = []
    return GnaniBatchClient("https://api.vachana.ai", KEY, http=fake.client(), sleep=sleeps.append), sleeps


def cfg(**kw) -> dict:
    return build_config("hinglish", Settings(), **kw)


# ---- config ----------------------------------------------------------------------------------------------------


def test_build_config_v3_hinglish_and_marathi():
    s = Settings()
    h = build_config("hinglish", s)
    assert h["model"] == "prisma-v3.0" and h["language_code"] == "hi-IN,en-IN" and h["format"] == "transcribe"
    assert h["with_diarization"] is True and h["num_speakers"] == 2 and h["is_multi_channel"] is False
    assert build_config("marathi", s)["language_code"] == "mr-IN,en-IN"


def test_build_config_v25_has_no_format_and_uses_single_language():
    s = Settings()
    h = build_config("hinglish", s, model="prisma-v2.5")
    assert "format" not in h and h["language_code"] == "en-IN"
    assert build_config("marathi", s, model="prisma-v2.5")["language_code"] == "mr-IN"


def test_build_config_overrides():
    c = build_config("hinglish", Settings(), with_denoise=True, keyterms=["EMI"])
    assert c["with_denoise"] is True and c["keyterms"] == ["EMI"]


# ---- error normalisation ---------------------------------------------------------------------------------------


def _resp(status: int, body) -> httpx.Response:
    return httpx.Response(status, json=body) if not isinstance(body, str) else httpx.Response(status, text=body)


def test_parse_error_batch_shape():
    e = parse_error(_resp(404, {"error": "JOB_NOT_FOUND", "message": "Job x not found"}))
    assert (e.code, e.message, e.http_status, e.retryable, e.fatal) == (
        "JOB_NOT_FOUND",
        "Job x not found",
        404,
        False,
        False,
    )


def test_parse_error_auth_shape_and_fatal_flags():
    e = parse_error(
        _resp(401, {"detail": {"error_code": "INVALID_API_KEY", "message": "Invalid API key", "status_code": 401}})
    )
    assert e.code == "INVALID_API_KEY" and e.fatal and not e.retryable
    e = parse_error(
        _resp(
            403, {"detail": {"error_code": "SCOPE_NOT_ALLOWED", "message": "not in allowed scopes", "status_code": 403}}
        )
    )
    assert e.fatal
    assert "credits exhausted" in e.user_message.lower()


def test_parse_error_402_is_fatal_even_without_body():
    e = parse_error(_resp(402, ""))
    assert e.fatal and e.http_status == 402 and not e.retryable


def test_parse_error_validation_shape():
    e = parse_error(_resp(422, {"detail": [{"loc": ["body", "audio_file"], "msg": "field required"}]}))
    assert e.code == "VALIDATION_ERROR" and "audio_file" in e.message and not e.retryable


def test_parse_error_retryable_statuses():
    for status in (429, 500, 503, 504):
        assert parse_error(_resp(status, {"error": "X", "message": "m"})).retryable
    assert not parse_error(_resp(400, {"error": "INVALID_CONFIG", "message": "m"})).retryable


def test_parse_error_403_without_credit_or_scope_words_is_not_fatal():
    e = parse_error(_resp(403, {"error": "SOMETHING", "message": "no way"}))
    assert not e.fatal and not e.retryable


# ---- happy path ------------------------------------------------------------------------------------------------


def test_transcribe_happy_path(fake, audio):
    client, sleeps = make_client(fake)
    saved: list[tuple[str, dict]] = []
    transcript, job_id, sent = client.transcribe(audio, cfg(), on_job_created=lambda j, c: saved.append((j, c)))
    assert saved == [(job_id, sent)]
    assert [s.speaker_id for s in transcript.segments] == [1, 2, 1, 2]
    assert transcript.segments[0].start_s == 0.0 and transcript.segments[0].end_s == 4.2
    assert transcript.language_code == "hi-IN,en-IN" and transcript.duration_s and transcript.duration_s > 16
    assert sent["with_diarization"] is True and sent["num_speakers"] == 2
    # one poll sleep per non-terminal poll, never faster than 10 s
    assert sleeps and all(x >= 10.0 for x in sleeps)
    paths = [p for _, p in fake.requests]
    assert paths[0] == "/stt/v3/batch/jobs" and paths[1].endswith("/start")


def test_create_sends_config_as_json_string_with_correct_parts(fake, audio):
    client, _ = make_client(fake)
    client.transcribe(audio, cfg(), poll_seconds=10)
    job = next(iter(fake.jobs.values()))
    assert job.config["language_code"] == "hi-IN,en-IN"
    assert job.filename == "call_01.wav" and job.size == audio.stat().st_size


def test_api_key_is_sent_to_api_but_never_to_the_presigned_url(fake, audio):
    client, _ = make_client(fake)
    client.transcribe(audio, cfg())
    assert fake.api_headers and all(h.get("x-api-key-id") == KEY for h in fake.api_headers)
    assert all(h.get("x-api-request-id") for h in fake.api_headers)
    assert fake.transcript_request_headers, "the transcript must have been downloaded"
    assert all("x-api-key-id" not in h for h in fake.transcript_request_headers)
    assert any(host == TRANSCRIPT_HOST for host in [h.get("host") for h in fake.transcript_request_headers])


def test_only_wav_or_flac_are_accepted(fake, tmp_path):
    client, _ = make_client(fake)
    bad = tmp_path / "call.mp3"
    bad.write_bytes(b"x")
    with pytest.raises(GnaniError) as e:
        client.create_job(bad, cfg())
    assert e.value.code == "BAD_FILE_EXTENSION" and not fake.requests


# ---- retries and failures --------------------------------------------------------------------------------------


def test_retries_server_errors_with_backoff_then_succeeds(fake, audio):
    fake.inject = [500, 503]
    client, sleeps = make_client(fake)
    job_id, _ = client.create_job(audio, cfg())
    assert job_id in fake.jobs
    assert sleeps == [0.5, 1.0]


def test_gives_up_after_three_retries(fake, audio):
    fake.inject = [500, 500, 500, 500]
    client, sleeps = make_client(fake)
    with pytest.raises(GnaniError) as e:
        client.create_job(audio, cfg())
    assert e.value.http_status == 500 and sleeps == [0.5, 1.0, 2.0]


def test_rate_limit_is_retried(fake, audio):
    fake.inject = [429]
    client, sleeps = make_client(fake)
    client.create_job(audio, cfg())
    assert sleeps == [0.5]


def test_connection_errors_are_retried_then_reported(audio):
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    sleeps: list[float] = []
    client = GnaniBatchClient(
        "https://api.vachana.ai", KEY, http=httpx.Client(transport=httpx.MockTransport(boom)), sleep=sleeps.append
    )
    with pytest.raises(GnaniError) as e:
        client.get_job("abc")
    assert e.value.code == "CONNECTION_ERROR" and e.value.retryable and len(sleeps) == 3


@pytest.mark.parametrize("flag,status", [("credits_exhausted", 402), ("scope_error", 403)])
def test_credit_and_scope_errors_are_fatal_and_not_retried(fake, audio, flag, status):
    setattr(fake, flag, True)
    client, sleeps = make_client(fake)
    with pytest.raises(GnaniError) as e:
        client.create_job(audio, cfg())
    assert e.value.fatal and e.value.http_status == status and sleeps == []
    assert len(fake.requests) == 1


def test_bad_key_is_fatal(fake, audio):
    client = GnaniBatchClient("https://api.vachana.ai", "wrong", http=fake.client(), sleep=lambda s: None)
    with pytest.raises(GnaniError) as e:
        client.create_job(audio, cfg())
    assert e.value.code == "INVALID_API_KEY" and e.value.fatal


def test_other_4xx_is_not_retried(fake, audio):
    fake.accepted_models = {"something-else"}
    client, sleeps = make_client(fake)
    with pytest.raises(GnaniError) as e:
        client.create_job(audio, cfg())
    assert e.value.http_status == 400 and sleeps == []


# ---- model name fallback ---------------------------------------------------------------------------------------


def test_v25_retries_once_with_gnani_prefix_when_the_name_is_rejected(fake, audio):
    fake.accepted_models = {"gnani-prisma-v2.5"}
    client, _ = make_client(fake)
    job_id, sent = client.create_job(audio, cfg(model="prisma-v2.5"))
    assert sent["model"] == "gnani-prisma-v2.5"
    assert fake.jobs[job_id].config["model"] == "gnani-prisma-v2.5"
    assert sum(1 for m, p in fake.requests if p == "/stt/v3/batch/jobs" and m == "POST") == 2


def test_v30_is_never_renamed(fake, audio):
    fake.accepted_models = {"gnani-prisma-v3.0"}
    client, _ = make_client(fake)
    with pytest.raises(GnaniError):
        client.create_job(audio, cfg())
    assert sum(1 for m, p in fake.requests if p == "/stt/v3/batch/jobs") == 1


# ---- job outcomes ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "outcome,code", [("FAILED", "JOB_FAILED"), ("START_FAILED", "START_FAILED"), ("CANCELLED", "JOB_CANCELLED")]
)
def test_failed_job_outcomes_raise_with_reason(fake, audio, outcome, code):
    fake.job_outcome = outcome
    client, _ = make_client(fake)
    with pytest.raises(GnaniError) as e:
        client.transcribe(audio, cfg())
    assert e.value.code == code and e.value.message and not e.value.fatal


def test_failed_file_message_is_surfaced(fake, audio):
    fake.job_outcome = "FAILED"
    client, _ = make_client(fake)
    with pytest.raises(GnaniError) as e:
        client.transcribe(audio, cfg())
    assert "UNSUPPORTED_LANGUAGE" in e.value.message


def test_partial_failure_still_returns_the_completed_file(fake, audio):
    fake.job_outcome = "PARTIAL_FAILURE"
    client, _ = make_client(fake)
    transcript, _, _ = client.transcribe(audio, cfg())
    assert len(transcript.segments) == 4


def test_timeout(fake, audio):
    fake.polls_until_done = 10_000
    client, sleeps = make_client(fake)
    with pytest.raises(GnaniError) as e:
        client.transcribe(audio, cfg(), timeout_s=30)
    assert e.value.code == "JOB_TIMEOUT" and sum(sleeps) >= 30


def test_polling_interval_has_a_floor_of_ten_seconds(fake, audio):
    client, sleeps = make_client(fake)
    client.transcribe(audio, cfg(), poll_seconds=1)
    assert sleeps and min(sleeps) == 10.0


# ---- idempotence and resume ------------------------------------------------------------------------------------


def test_resume_polls_the_existing_job_without_creating_a_second_one(fake, audio):
    client, _ = make_client(fake)
    created: list[str] = []
    job_id, _ = client.create_job(audio, cfg())  # the job exists before the "restart"
    client.start_job(job_id)
    fake.requests.clear()
    transcript, got_id, _ = client.transcribe(
        audio, cfg(), job_id=job_id, on_job_created=lambda j, c: created.append(j)
    )
    assert got_id == job_id and created == []
    assert not any(m == "POST" and p == "/stt/v3/batch/jobs" for m, p in fake.requests)
    assert len(transcript.segments) == 4


def test_resume_starts_a_job_that_was_created_but_never_started(fake, audio):
    client, _ = make_client(fake)
    job_id, _ = client.create_job(audio, cfg())
    transcript, got_id, _ = client.transcribe(audio, cfg(), job_id=job_id)
    assert got_id == job_id and transcript.segments
    assert sum(1 for m, p in fake.requests if p.endswith("/start")) == 1


def test_resume_of_an_unknown_job_creates_a_new_one(fake, audio):
    client, _ = make_client(fake)
    created: list[str] = []
    _, got_id, _ = client.transcribe(
        audio, cfg(), job_id="does-not-exist", on_job_created=lambda j, c: created.append(j)
    )
    assert created == [got_id] and got_id in fake.jobs


def test_start_of_an_already_started_job_is_not_an_error(fake, audio):
    client, _ = make_client(fake)
    job_id, _ = client.create_job(audio, cfg())
    client.start_job(job_id)
    assert client.start_job(job_id) == "STARTING"


# ---- transcript parsing ----------------------------------------------------------------------------------------


def test_parse_transcript_sorts_skips_blank_and_keeps_devanagari():
    raw = {
        "language_code": "hi-IN",
        "duration_seconds": 9.5,
        "model": "gnani-prisma-v3.0",
        "segments": [
            {"segment_id": 1, "start_time": 5.0, "end_time": 8.0, "text": "मेरा नाम रोहित है", "speaker_id": 1},
            {"segment_id": 0, "start_time": 0.0, "end_time": 4.0, "text": "hello", "speaker_id": 2},
            {"segment_id": 2, "start_time": 8.0, "end_time": 9.0, "text": "   ", "speaker_id": 1},
        ],
    }
    t = parse_transcript(raw)
    assert [s.text for s in t.segments] == ["hello", "मेरा नाम रोहित है"]
    assert t.duration_s == 9.5 and t.segments[0].speaker_id == 2


def test_parse_transcript_rejects_garbage():
    with pytest.raises(GnaniError):
        parse_transcript({"nope": 1})
    with pytest.raises(GnaniError):
        parse_transcript({"segments": [{"text": "x", "start_time": "a", "end_time": 1}]})


def test_missing_speaker_id_becomes_none():
    t = parse_transcript({"segments": [{"start_time": 0, "end_time": 1, "text": "x"}]})
    assert t.segments[0].speaker_id is None


def test_transcript_json_is_kept_whole_for_caching(fake, audio):
    client, _ = make_client(fake)
    transcript, _, _ = client.transcribe(audio, cfg())
    assert json.dumps(transcript.raw)  # serialisable for calls.raw_transcript
    assert transcript.raw["full_transcript"].startswith("Namaste")
