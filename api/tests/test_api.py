from __future__ import annotations

import json
from datetime import datetime

import pytest

from app.config import get_settings
from app.models import Call, Rule
from tests.helpers import IST, make_agent, make_call, make_wav

SEGMENTS = [
    (0.0, 4.0, 1, "Namaste, main Rohit Patil bol raha hoon Sahyog Finance se."),
    (4.2, 6.0, 2, "Haan ji. Mera number 9876543210 hai."),
    (6.2, 12.0, 1, "Kal tak payment nahi aaya toh main padosiyon ko bata dunga ki aap defaulter ho."),
    (12.5, 15.0, 2, "Aisa mat kijiye."),
]


def wav_bytes(tmp_path, name="a.wav", seconds=5.0) -> bytes:
    return make_wav(tmp_path / name, seconds).read_bytes()


def upload(client, tmp_path, entries=None, files=None, headers=None, raw_metadata=None):
    entries = entries or [
        {
            "filename": "a.wav",
            "agent_name": "Rohit Patil",
            "called_at": "2026-11-03T11:20:00+05:30",
            "language": "hinglish",
            "loan_ref": "SF-PL-204871",
        }
    ]
    files = files if files is not None else [("files", ("a.wav", wav_bytes(tmp_path), "audio/wav"))]
    meta = raw_metadata if raw_metadata is not None else json.dumps(entries)
    return client.post("/calls/upload", files=files, data={"metadata": meta}, headers=headers or {})


def error(resp) -> dict:
    body = resp.json()
    assert set(body) == {"error"} and set(body["error"]) == {"code", "message"}
    return body["error"]


# ---- basics ------------------------------------------------------------------------------------------------------


def test_health_and_unknown_route_use_the_error_envelope(client):
    assert client.get("/health").json() == {"status": "ok"}
    r = client.get("/nope")
    assert r.status_code == 404 and error(r)["code"] == "not_found"


def test_the_nine_rules_are_listed_and_ordered(client):
    rules = client.get("/rules").json()
    assert [r["code"] for r in rules] == [f"V{i}" for i in range(1, 10)] and all(r["enabled"] for r in rules)


# ---- upload ------------------------------------------------------------------------------------------------------


def test_upload_creates_queued_calls_and_the_worker_processes_them(client, runtime, gnani_fake, llm_fake, tmp_path):
    from tests.fakes.llm_fake import answer, flag

    gnani_fake.default_segments = SEGMENTS
    llm_fake.responses = [answer([flag("V5", 2, "padosiyon ko bata dunga")])]
    r = upload(client, tmp_path)
    assert r.status_code == 200
    (call,) = r.json()
    assert call["status"] == "queued" and call["agent_name"] == "Rohit Patil" and call["language"] == "hinglish"
    assert call["called_at"].endswith("+05:30") and call["duration_s"] == pytest.approx(5.0, abs=0.2)
    assert runtime.worker.pending == 1
    runtime.worker.drain()
    detail = client.get(f"/calls/{call['id']}").json()
    assert detail["status"] == "done" and detail["score"] == 85 and detail["violations_count"] == 1
    assert [v["rule_code"] for v in detail["violations"]] == ["V5"]
    assert detail["transcription"]["language_code"] == "hi-IN,en-IN"
    assert detail["roles_look_correct"] is True and detail["analysis_notice"] is None
    assert [s["speaker"] for s in detail["segments"]] == ["agent", "borrower", "agent", "borrower"]
    assert "9876543210" not in json.dumps(detail)


def test_raw_transcript_never_leaves_the_server(client, runtime, gnani_fake, tmp_path):
    gnani_fake.default_segments = SEGMENTS
    (call,) = upload(client, tmp_path).json()
    runtime.worker.drain()
    for path in (f"/calls/{call['id']}", "/calls", f"/agents/{client.get('/agents').json()[0]['id']}"):
        text = client.get(path).text
        assert "raw_transcript" not in text and "9876543210" not in text and "speaker_id" not in text


def test_upload_reuses_an_existing_agent_by_name_ignoring_case(client, tmp_path):
    entries = [
        {
            "filename": "a.wav",
            "agent_name": "rohit patil",
            "called_at": "2026-11-03T11:20:00",
            "language": "hinglish",
            "loan_ref": "L",
        }
    ]
    first = upload(client, tmp_path, entries).json()[0]
    second = upload(client, tmp_path, entries).json()[0]
    assert first["agent_id"] == second["agent_id"] and len(client.get("/agents").json()) == 1
    assert first["called_at"] == "2026-11-03T11:20:00+05:30"  # a time without an offset is read as IST


def test_upload_with_an_agent_id(client, session, tmp_path):
    agent = make_agent(session, "Kavita Rao")
    entries = [
        {
            "filename": "a.wav",
            "agent_id": str(agent.id),
            "called_at": "2026-11-03T21:30:00+05:30",
            "language": "marathi",
            "loan_ref": "L",
            "borrower_requested_time": True,
        }
    ]
    call = upload(client, tmp_path, entries).json()[0]
    assert call["agent_name"] == "Kavita Rao" and call["language"] == "marathi" and call["borrower_requested_time"]


def test_upload_unknown_agent_id_is_404_and_creates_nothing(client, session, tmp_path):
    entries = [
        {
            "filename": "a.wav",
            "agent_id": "00000000-0000-0000-0000-000000000000",
            "called_at": "2026-11-03T11:20:00",
            "language": "hinglish",
            "loan_ref": "L",
        }
    ]
    r = upload(client, tmp_path, entries)
    assert r.status_code == 404 and error(r)["code"] == "not_found"
    assert session.query(Call).count() == 0


@pytest.mark.parametrize(
    "change, message",
    [
        ({"language": "tamil"}, "metadata is not valid (language): Input should be 'hinglish' or 'marathi'."),
        ({"loan_ref": ""}, "metadata is not valid (loan_ref): String should have at least 1 character."),
        (
            {"called_at": "yesterday"},
            "a.wav: called_at must be an ISO 8601 date and time, such as 2026-11-03T11:20:00+05:30.",
        ),
        ({"agent_name": "  "}, "a.wav: choose an agent or give an agent_name."),
    ],
)
def test_upload_rejects_bad_metadata(client, session, tmp_path, change, message):
    entry = {
        "filename": "a.wav", "agent_name": "Rohit", "called_at": "2026-11-03T11:20:00", "language": "hinglish",
        "loan_ref": "L",
    }  # fmt: skip
    r = upload(client, tmp_path, [{**entry, **change}])
    assert r.status_code == 400 and error(r) == {"code": "invalid_request", "message": message}
    assert session.query(Call).count() == 0


def test_upload_needs_files_and_matching_metadata(client, tmp_path):
    r = upload(client, tmp_path, files=[], raw_metadata="[]")
    assert r.status_code == 400 and "Attach at least one audio file" in error(r)["message"]
    r = upload(client, tmp_path, entries=[], raw_metadata="[]")
    assert r.status_code == 400 and "must match" in error(r)["message"]
    r = upload(client, tmp_path, raw_metadata="not json")
    assert r.status_code == 400 and "JSON array" in error(r)["message"]


def test_upload_is_atomic_one_bad_file_creates_nothing(client, session, tmp_path):
    good = ("files", ("a.wav", wav_bytes(tmp_path), "audio/wav"))
    bad = ("files", ("b.wav", b"this is not audio", "audio/wav"))
    entry = {
        "filename": "x",
        "agent_name": "Rohit",
        "called_at": "2026-11-03T11:20:00",
        "language": "hinglish",
        "loan_ref": "L",
    }
    r = upload(client, tmp_path, [entry, entry], files=[good, bad])
    assert r.status_code == 400 and error(r) == {
        "code": "unsupported_media",
        "message": "That file is not a readable audio file.",
    }
    assert session.query(Call).count() == 0


def test_upload_rejects_calls_that_are_too_long(client, session, tmp_path, monkeypatch):
    monkeypatch.setenv("MAX_CALL_MINUTES", "1")
    get_settings.cache_clear()
    long = [("files", ("a.wav", wav_bytes(tmp_path, seconds=70), "audio/wav"))]
    r = upload(client, tmp_path, files=long)
    assert r.status_code == 400 and error(r)["code"] == "audio_too_long"
    assert session.query(Call).count() == 0


def test_upload_rejects_files_over_the_size_limit(client, session, tmp_path, monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    big = [("files", ("a.wav", wav_bytes(tmp_path, seconds=40), "audio/wav"))]  # about 1.3 MB
    r = upload(client, tmp_path, files=big)
    assert r.status_code == 413 and error(r)["code"] == "file_too_large"
    assert session.query(Call).count() == 0


# ---- demo mode ---------------------------------------------------------------------------------------------------


@pytest.fixture
def demo(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("UPLOAD_PASSCODE", "open-sesame")
    get_settings.cache_clear()


def test_demo_mode_blocks_upload_without_the_passcode(client, session, tmp_path, demo):
    assert error(upload(client, tmp_path))["code"] == "forbidden"
    assert error(upload(client, tmp_path, headers={"X-Upload-Passcode": "wrong"}))["code"] == "forbidden"
    assert session.query(Call).count() == 0
    assert upload(client, tmp_path, headers={"X-Upload-Passcode": "open-sesame"}).status_code == 200


def test_demo_mode_with_no_passcode_configured_blocks_everything(client, tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    get_settings.cache_clear()
    assert upload(client, tmp_path, headers={"X-Upload-Passcode": ""}).status_code == 403


def test_demo_mode_leaves_reads_open_and_rate_limits_writes(client, session, tmp_path, demo):
    assert client.get("/calls").status_code == 200 and client.get("/rules").status_code == 200
    call = make_call(session, make_agent(session), status="failed")
    h = {"X-Upload-Passcode": "open-sesame"}
    codes = [client.post(f"/calls/{call.id}/retry", headers=h).status_code for _ in range(11)]
    assert codes[:10] == [200] * 10 and codes[10] == 429


def test_demo_guard_covers_retry_and_swap_roles(client, session, demo):
    call = make_call(session, make_agent(session))
    assert client.post(f"/calls/{call.id}/retry").status_code == 403
    assert client.post(f"/calls/{call.id}/swap-roles").status_code == 403


# ---- listing -----------------------------------------------------------------------------------------------------


@pytest.fixture
def seeded(session):
    a, b = make_agent(session, "Asha Kulkarni"), make_agent(session, "Bharat Joshi")
    d = lambda day, hour=11: datetime(2026, 11, day, hour, 0, tzinfo=IST)  # noqa: E731
    return {
        "clean": make_call(session, a, called_at=d(1), loan_ref="LN-001", test_key="call_01"),
        "high": make_call(
            session, a, called_at=d(2), loan_ref="LN-002", violations=[("V5", "open")], language="marathi"
        ),
        "crit": make_call(session, b, called_at=d(3), loan_ref="LN-003", violations=[("V4", "open"), ("V5", "open")]),
        "dismissed": make_call(session, b, called_at=d(4), loan_ref="LN-004", violations=[("V4", "dismissed")]),
        "failed": make_call(session, b, called_at=d(5), loan_ref="LN-005", status="failed"),
        "agents": (a, b),
    }


def ids(resp):
    return [c["loan_ref"] for c in resp.json()["items"]]


def test_list_defaults_to_newest_first_with_paging(client, seeded):
    r = client.get("/calls").json()
    assert r["total"] == 5 and r["page"] == 1 and r["page_size"] == 25
    assert ids(client.get("/calls")) == ["LN-005", "LN-004", "LN-003", "LN-002", "LN-001"]
    assert ids(client.get("/calls?page=2&page_size=2")) == ["LN-003", "LN-002"]
    assert client.get("/calls?page=9&page_size=2").json()["items"] == []


def test_list_filters(client, seeded):
    a, b = seeded["agents"]
    assert ids(client.get(f"/calls?agent_id={a.id}")) == ["LN-002", "LN-001"]
    assert ids(client.get("/calls?language=marathi")) == ["LN-002"]
    assert ids(client.get("/calls?status=failed")) == ["LN-005"]
    assert ids(client.get("/calls?severity=critical")) == ["LN-003"]  # LN-004's critical flag is dismissed
    assert ids(client.get("/calls?rule_code=V5")) == ["LN-003", "LN-002"]
    assert ids(client.get("/calls?date_from=2026-11-02&date_to=2026-11-03")) == ["LN-003", "LN-002"]
    assert ids(client.get("/calls?q=ln-001")) == ["LN-001"] and ids(client.get("/calls?q=call_01")) == ["LN-001"]
    assert client.get("/calls?agent_id=garbage").json()["total"] == 0


def test_list_sorting(client, seeded):
    asc = client.get("/calls?sort=score&order=asc").json()["items"]
    assert asc[0]["score"] is None and asc[1]["score"] == 55  # calls without a score sort first when ascending
    by_score = client.get("/calls?sort=score&order=desc").json()["items"]
    scores = [c["score"] for c in by_score if c["score"] is not None]
    assert scores == sorted(scores, reverse=True)
    assert ids(client.get("/calls?sort=violations_count&order=desc"))[0] == "LN-003"
    assert ids(client.get("/calls?sort=agent_name&order=asc"))[:2] == ["LN-002", "LN-001"]  # Asha's, newest first
    r = client.get("/calls?sort=password")
    assert r.status_code == 400 and "sort must be one of" in error(r)["message"]


def test_list_validates_paging_with_the_envelope(client):
    for q in ("page=0", "page_size=101", "order=sideways", "status=nope"):
        r = client.get(f"/calls?{q}")
        assert r.status_code == 422 and error(r)["code"] == "invalid_request"


def test_scores_and_counts_ignore_dismissed_and_disabled(client, seeded):
    by_ref = {c["loan_ref"]: c for c in client.get("/calls").json()["items"]}
    assert by_ref["LN-001"]["score"] == 100 and by_ref["LN-002"]["score"] == 85
    assert by_ref["LN-003"]["score"] == 55 and by_ref["LN-003"]["max_severity"] == "critical"
    assert by_ref["LN-004"]["score"] == 100 and by_ref["LN-004"]["violations_count"] == 0
    assert by_ref["LN-005"]["score"] is None


# ---- one call ----------------------------------------------------------------------------------------------------


def test_get_call_includes_dismissed_flags_but_hides_disabled_rules(client, session, seeded):
    detail = client.get(f"/calls/{seeded['dismissed'].id}").json()
    assert [(v["rule_code"], v["reviewer_status"]) for v in detail["violations"]] == [("V4", "dismissed")]
    session.get(Rule, "V4").enabled = False
    session.commit()
    assert client.get(f"/calls/{seeded['dismissed'].id}").json()["violations"] == []


def test_unknown_and_malformed_ids_are_404_with_the_envelope(client):
    for cid in ("00000000-0000-0000-0000-000000000000", "not-a-uuid"):
        for suffix in ("", "/audio", "/audio/file"):
            r = client.get(f"/calls/{cid}{suffix}")
            assert r.status_code == 404 and error(r)["code"] == "not_found"
        assert client.post(f"/calls/{cid}/retry").status_code == 404
        assert client.post(f"/calls/{cid}/swap-roles").status_code == 404
    assert client.patch("/violations/nope", json={"reviewer_status": "open"}).status_code == 404
    assert client.get("/agents/nope").status_code == 404
    assert client.patch("/rules/V99", json={"enabled": False}).status_code == 404


def test_audio_url_and_file(client, runtime, gnani_fake, tmp_path):
    (call,) = upload(client, tmp_path).json()
    url = client.get(f"/calls/{call['id']}/audio").json()
    assert url["url"].startswith("http") and url["url"].endswith(f"/calls/{call['id']}/audio/file")
    assert url["expires_at"].endswith("+05:30")
    f = client.get(f"/calls/{call['id']}/audio/file")
    assert f.status_code == 200 and f.headers["content-type"].startswith("audio/") and f.content[:4] == b"RIFF"


# ---- retry and swap roles ----------------------------------------------------------------------------------------


def test_retry_requeues_a_failed_call_and_clears_the_error(client, session, runtime, gnani_fake):
    gnani_fake.default_segments = SEGMENTS
    call = make_call(session, make_agent(session), status="failed")
    call.error = "Gnani rejected the file."
    call.audio_path = runtime.storage.save(str(call.id), make_wav(runtime.storage.root / "r.wav"), "r.wav")
    session.commit()
    r = client.post(f"/calls/{call.id}/retry")
    assert r.status_code == 200 and r.json()["status"] == "queued" and r.json()["error"] is None
    runtime.worker.drain()
    assert client.get(f"/calls/{call.id}").json()["status"] == "done"


def test_retry_of_a_call_in_progress_does_nothing(client, session, runtime):
    call = make_call(session, make_agent(session), status="transcribing")
    assert client.post(f"/calls/{call.id}/retry").json()["status"] == "transcribing"
    assert runtime.worker.pending == 0


def test_retry_resumes_a_paused_queue_and_retranscribe_drops_the_cache(client, session, runtime):
    call = make_call(session, make_agent(session), status="failed")
    call.raw_transcript, call.gnani_job_id = {"segments": []}, "job-1"
    session.commit()
    runtime.worker.paused, runtime.worker.pause_reason = True, "credits"
    client.post(f"/calls/{call.id}/retry?retranscribe=true")
    session.expire_all()
    assert runtime.worker.paused is False and runtime.worker.pending == 1
    again = session.get(Call, call.id)
    assert again.raw_transcript is None and again.gnani_job_id is None


def test_swap_roles_reruns_detection_without_gnani(client, session, runtime, gnani_fake, llm_fake, tmp_path):
    from tests.fakes.llm_fake import answer

    gnani_fake.default_segments = SEGMENTS
    llm_fake.responses = [answer(), answer()]
    (call,) = upload(client, tmp_path).json()
    runtime.worker.drain()
    before = client.get(f"/calls/{call['id']}").json()
    assert before["segments"][0]["speaker"] == "agent"
    gnani_fake.requests.clear()
    r = client.post(f"/calls/{call['id']}/swap-roles")
    assert r.status_code == 200 and gnani_fake.requests == []
    assert [s["speaker"] for s in r.json()["segments"]] == ["borrower", "agent", "borrower", "agent"]
    again = client.post(f"/calls/{call['id']}/swap-roles").json()  # swapping back restores the original reading
    assert [s["speaker"] for s in again["segments"]] == ["agent", "borrower", "agent", "borrower"]


def test_swap_roles_needs_a_finished_call_with_two_speakers(client, session):
    call = make_call(session, make_agent(session), status="failed")
    r = client.post(f"/calls/{call.id}/swap-roles")
    assert r.status_code == 400 and error(r)["code"] == "invalid_state"


# ---- reviewing flags ---------------------------------------------------------------------------------------------


def test_dismissing_a_flag_recomputes_the_score(client, seeded):
    detail = client.get(f"/calls/{seeded['crit'].id}").json()
    v4 = next(v for v in detail["violations"] if v["rule_code"] == "V4")
    r = client.patch(f"/violations/{v4['id']}", json={"reviewer_status": "dismissed"})
    assert r.status_code == 200 and r.json()["call_score"] == 85
    assert r.json()["violation"]["reviewer_status"] == "dismissed"
    assert client.get(f"/calls/{seeded['crit'].id}").json()["score"] == 85
    r = client.patch(f"/violations/{v4['id']}", json={"reviewer_status": "confirmed"})
    assert r.json()["call_score"] == 55  # confirming counts again
    assert client.patch(f"/violations/{v4['id']}", json={"reviewer_status": "maybe"}).status_code == 422


# ---- rules -------------------------------------------------------------------------------------------------------


def test_disabling_a_rule_hides_its_flags_and_recomputes_without_deleting(client, session, seeded):
    r = client.patch("/rules/v4", json={"enabled": False})
    assert r.status_code == 200 and r.json()["enabled"] is False
    by_ref = {c["loan_ref"]: c for c in client.get("/calls").json()["items"]}
    assert by_ref["LN-003"]["score"] == 85 and by_ref["LN-003"]["violations_count"] == 1
    assert session.query(Rule).filter_by(code="V4", enabled=False).count() == 1
    client.patch("/rules/V4", json={"enabled": True})
    assert {c["loan_ref"]: c for c in client.get("/calls").json()["items"]}["LN-003"]["score"] == 55


# ---- agents ------------------------------------------------------------------------------------------------------


def test_agents_list_detail_and_create(client, seeded):
    agents = {a["name"]: a for a in client.get("/agents").json()}
    asha, bharat = agents["Asha Kulkarni"], agents["Bharat Joshi"]
    assert asha["calls_count"] == 2 and asha["avg_score"] == pytest.approx(92.5)
    assert asha["violation_rate"] == pytest.approx(0.5) and asha["top_rule_code"] == "V5"
    assert bharat["calls_count"] == 2 and bharat["critical_count"] == 1 and bharat["avg_score"] == pytest.approx(77.5)
    detail = client.get(f"/agents/{bharat['id']}").json()
    assert len(detail["calls"]) == 3 and {r["rule_code"] for r in detail["violations_by_rule"]} == {"V4", "V5"}
    assert detail["score_trend"] and all("avg_score" in p for p in detail["score_trend"])

    r = client.post("/agents", json={"name": " Chitra Nair ", "team": "Field"})
    assert r.status_code == 201 and r.json()["name"] == "Chitra Nair" and r.json()["calls_count"] == 0
    assert r.json()["avg_score"] is None
    dup = client.post("/agents", json={"name": "chitra nair"})
    assert dup.status_code == 409 and error(dup)["code"] == "conflict"
    assert client.post("/agents", json={"name": ""}).status_code == 422


# ---- overview ----------------------------------------------------------------------------------------------------


def test_overview_semantics_match_the_mock(client, session, seeded):
    o = client.get("/stats/overview").json()
    assert o["calls_audited"] == 4 and o["calls_pending"] == 0  # the failed call is neither
    assert o["calls_with_violations"] == 2 and o["calls_with_violations_pct"] == pytest.approx(50.0)
    assert o["avg_score"] == pytest.approx((100 + 85 + 55 + 100) / 4)
    assert len(o["violations_per_day"]) == 14 and o["violations_per_day"] == sorted(
        o["violations_per_day"], key=lambda d: d["date"]
    )
    assert [t["rule_code"] for t in o["top_rules"]][:1] == ["V5"] and o["top_rules"][0]["count"] == 2
    assert o["agents_needing_review"][0]["agent_name"] == "Bharat Joshi"
    assert [c["rule_code"] for c in o["recent_critical"]] == ["V4"]  # the dismissed V4 is not listed
    assert o["as_of"].endswith("+05:30")


def test_overview_counts_pending_and_handles_an_empty_database(client, session):
    o = client.get("/stats/overview").json()
    assert o["calls_audited"] == 0 and o["avg_score"] is None and o["calls_with_violations_pct"] == 0
    agent = make_agent(session)
    for s in ("queued", "transcribing", "analysing", "done", "failed"):
        make_call(session, agent, status=s)
    assert client.get("/stats/overview").json()["calls_pending"] == 3


def test_critical_flags_only_count_the_last_14_days(client, session):
    agent = make_agent(session)
    make_call(session, agent, called_at=datetime(2026, 1, 5, 11, 0, tzinfo=IST), violations=[("V4", "open")])
    assert client.get("/stats/overview").json()["critical_flags"] == 0


def test_unexpected_server_errors_are_wrapped_without_internals(runtime, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import create_app

    def boom(*a, **k):
        raise RuntimeError("secret internals")

    monkeypatch.setattr("app.routers.stats.overview", boom)
    with TestClient(create_app(lambda s: runtime), raise_server_exceptions=False) as c:
        r = c.get("/stats/overview")
    assert r.status_code == 500 and error(r) == {
        "code": "internal_error",
        "message": "Something went wrong on the server.",
    }
    assert "secret" not in r.text


def test_cors_allows_the_configured_origin(client):
    r = client.options("/calls", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
