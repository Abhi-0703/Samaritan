from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.config import get_settings
from app.storage import get_storage
from app.storage.supabase import StorageError, SupabaseStorage
from tests.fakes.supabase_fake import PROJECT, SERVICE_KEY, FakeSupabaseStorage
from tests.helpers import make_wav


@pytest.fixture
def fake():
    return FakeSupabaseStorage()


@pytest.fixture
def store(fake, tmp_path):
    return SupabaseStorage(PROJECT, SERVICE_KEY, "call-audio", http=fake.client(), cache_dir=tmp_path / "cache")


def test_save_uploads_with_upsert_and_returns_the_key(store, fake, tmp_path):
    wav = make_wav(tmp_path / "a.wav", 1)
    key = store.save("abc-123", wav, "Recording.WAV")
    assert key == "abc-123.wav" and fake.objects[key] == wav.read_bytes()
    assert fake.upsert_headers == ["true"]  # re-running a seed must not fail on an existing file


def test_local_path_downloads_once_and_reuses_the_file(store, fake, tmp_path):
    wav = make_wav(tmp_path / "a.wav", 1)
    key = store.save("c1", wav, "a.wav")
    p = store.local_path(key)
    assert p.read_bytes() == wav.read_bytes()
    gets = lambda: [r for r in fake.requests if r[0] == "GET"]  # noqa: E731
    store.local_path(key)
    assert len(gets()) == 1  # the second call used the cached file


def test_url_is_a_signed_url_with_an_expiry(store, tmp_path):
    key = store.save("c1", make_wav(tmp_path / "a.wav", 1), "a.wav")
    url, expires = store.url("c1", key)
    assert url == f"{PROJECT}/storage/v1/object/sign/call-audio/c1.wav?token=tok123"
    assert datetime.now(UTC) + timedelta(minutes=55) < expires < datetime.now(UTC) + timedelta(hours=1)


def test_delete_removes_the_object_and_its_cached_copy(store, fake, tmp_path):
    key = store.save("c1", make_wav(tmp_path / "a.wav", 1), "a.wav")
    cached = store.local_path(key)
    store.delete(key)
    assert key not in fake.objects and not cached.exists()
    store.delete(key)  # deleting something already gone is fine


def test_errors_are_clear_and_never_contain_the_key(store, fake, tmp_path):
    wav = make_wav(tmp_path / "a.wav", 1)
    fake.fail_with = 500
    with pytest.raises(StorageError) as e:
        store.save("c1", wav, "a.wav")
    assert "HTTP 500" in str(e.value) and "boom" in str(e.value) and SERVICE_KEY not in str(e.value)
    with pytest.raises(StorageError, match="download the audio"):
        store.local_path("missing.wav")
    with pytest.raises(StorageError, match="sign the audio URL"):
        store.url("x", "missing.wav")
    bad = SupabaseStorage(PROJECT, "wrong-key", "call-audio", http=fake.client(), cache_dir=tmp_path / "c2")
    with pytest.raises(StorageError, match="HTTP 401"):
        bad.save("c1", wav, "a.wav")


def test_keys_with_odd_characters_are_url_encoded(store, fake, tmp_path):
    key = store.save("c 1", make_wav(tmp_path / "a.wav", 1), "a b.wav")
    assert key == "c 1.wav" and fake.objects[key]
    assert "c%201.wav" in store.url("c 1", key)[0]


def test_missing_configuration_is_refused():
    with pytest.raises(StorageError, match="SUPABASE_URL"):
        SupabaseStorage("", "", "call-audio")


def test_the_factory_picks_the_backend_from_settings(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "supabase")
    monkeypatch.setenv("SUPABASE_URL", PROJECT)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", SERVICE_KEY)
    get_settings.cache_clear()
    get_storage.cache_clear()
    s = get_storage()
    assert isinstance(s, SupabaseStorage) and s.base == f"{PROJECT}/storage/v1" and s.bucket == "call-audio"


def test_the_settings_never_show_the_service_key(monkeypatch):
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", SERVICE_KEY)
    get_settings.cache_clear()
    assert SERVICE_KEY not in repr(get_settings())


# ---- through the API ---------------------------------------------------------------------------------------------


@pytest.fixture
def supabase_client(runtime, fake, tmp_path):
    """The API wired to the fake bucket instead of the local folder."""
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.runtime import Runtime, make_worker

    storage = SupabaseStorage(PROJECT, SERVICE_KEY, "call-audio", http=fake.client(), cache_dir=tmp_path / "cache")
    rt = Runtime(
        runtime.settings,
        runtime.gnani,
        runtime.llm,
        storage,
        make_worker(runtime.settings, runtime.gnani, runtime.llm, storage),
    )
    with TestClient(create_app(lambda s: rt)) as c:
        yield c, rt


def test_upload_pipeline_and_audio_url_work_on_the_supabase_backend(supabase_client, gnani_fake, fake, tmp_path):
    client, rt = supabase_client
    gnani_fake.default_segments = [
        (0.0, 4.0, 1, "Namaste, main Rohit Patil Sahyog Finance se."),
        (4.5, 6.0, 2, "Haan."),
    ]
    wav = make_wav(tmp_path / "up.wav", 5).read_bytes()
    meta = json.dumps(
        [{"filename": "up.wav", "agent_name": "Rohit", "called_at": "2026-11-03T11:20:00", "language": "hinglish",
          "loan_ref": "L1"}]
    )  # fmt: skip
    r = client.post("/calls/upload", files=[("files", ("up.wav", wav, "audio/wav"))], data={"metadata": meta})
    assert r.status_code == 200
    call_id = r.json()[0]["id"]
    assert fake.objects[f"{call_id}.wav"] == wav  # the upload went to the bucket, not to disk
    rt.worker.drain()
    assert client.get(f"/calls/{call_id}").json()["status"] == "done"
    audio = client.get(f"/calls/{call_id}/audio").json()
    assert audio["url"].startswith(f"{PROJECT}/storage/v1/object/sign/call-audio/{call_id}.wav?token=")
    assert audio["expires_at"].endswith("+05:30")


def test_a_storage_outage_on_the_audio_url_is_a_502_with_the_envelope(supabase_client, fake, session, tmp_path):
    from tests.helpers import make_agent, make_call

    client, _ = supabase_client
    call = make_call(session, make_agent(session))
    fake.fail_with = 503
    r = client.get(f"/calls/{call.id}/audio")
    assert r.status_code == 502 and r.json()["error"]["code"] == "storage_unavailable"
