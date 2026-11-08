from __future__ import annotations

import json
from datetime import datetime

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.evaluation import ingest as ingest_mod
from app.evaluation import keys as keys_mod
from app.evaluation import labelling, report, runner
from app.evaluation.keys import AnswerKey, Expected, load_keys, parse_key
from app.models import Call, EvalRun
from app.services.llm.base import LLMTransientError
from tests.fakes.llm_fake import answer, flag
from tests.helpers import IST, make_agent, make_wav

THREAT = [
    (0.0, 4.0, 1, "Namaste, main Rohit Patil bol raha hoon Sahyog Finance se."),
    (4.2, 6.0, 2, "Haan ji boliye."),
    (6.2, 12.0, 1, "Kal tak payment nahi aaya toh main padosiyon ko bata dunga ki aap defaulter ho."),
    (12.5, 15.0, 2, "Aisa mat kijiye."),
]
CLEAN = [
    (0.0, 4.0, 1, "Namaste, main Rohit Patil bol raha hoon Sahyog Finance se."),
    (4.2, 6.0, 2, "Haan ji boliye."),
    (6.2, 12.0, 1, "Aapki EMI pending hai, kab tak bhar sakte hain?"),
    (12.5, 15.0, 2, "Paanch tarikh tak."),
]


def raw(segments) -> dict:
    return {
        "language_code": "hi-IN", "duration_seconds": segments[-1][1] + 1, "model": "gnani-prisma-v3.0",
        "mode": "transcribe",
        "segments": [{"segment_id": i, "start_time": s, "end_time": e, "text": t, "speaker_id": sp}
                     for i, (s, e, sp, t) in enumerate(segments)],
    }  # fmt: skip


def key(test_key="call_a", *expected, clean=False, time="11:20", split="test", agent=None, **kw) -> AnswerKey:
    return AnswerKey(
        test_key, split, kw.get("language", "hinglish"), time, False, kw.get("noisy", False), clean,
        tuple(Expected(r, t, h, "easy") for r, t, h in expected), agent_speaker_id=agent,
    )  # fmt: skip


@pytest.fixture
def add_call(session):
    agent = make_agent(session)

    def add(test_key, segments, called_at=None, status="done", with_transcript=True) -> Call:
        call = Call(
            agent_id=agent.id, loan_ref=test_key, language="hinglish", audio_path="x.wav", status=status,
            called_at=called_at or datetime(2026, 11, 3, 11, 20, tzinfo=IST), test_key=test_key, is_test_set=True,
            raw_transcript=raw(segments) if with_transcript else None,
            transcription_config={"model": "prisma-v3.0", "language_code": "hi-IN,en-IN"},
        )  # fmt: skip
        session.add(call)
        session.commit()
        return call

    return add


def evaluate(session, runtime, keys, **kw):
    return runner.evaluate(session, runtime.llm, keys, **kw)


# ---- the runner --------------------------------------------------------------------------------------------------


def test_both_configurations_run_on_the_same_cached_transcripts(session, runtime, llm_fake, gnani_fake, add_call):
    add_call("call_a", THREAT)
    add_call("call_b", CLEAN)
    llm_fake.responses = [answer([flag("V5", 2, "padosiyon ko bata dunga")]), answer()]
    keys = [key("call_a", ("V5", 6.2, "padosiyon"), agent=1), key("call_b", clean=True)]
    ev = evaluate(session, runtime, keys)
    assert gnani_fake.requests == []  # never transcribes
    assert set(ev.results) == {"rules_only", "rules_plus_llm"} and ev.warnings == [] and ev.not_evaluated == []
    for config in ("rules_only", "rules_plus_llm"):
        s, roles = runner.summary_for(ev.results[config])
        assert s.n_calls == 2 and s.overall.precision == 1.0 and s.overall.recall == 1.0
        assert (s.clean_calls_flagged, s.clean_calls_total) == (0, 1) and roles == 1.0
    assert ev.results["rules_plus_llm"].models == {"stt": "prisma-v3.0", "llm": "fake/fake-1"}
    assert ev.results["rules_only"].models["llm"] == "none"


def test_the_llm_removes_a_rules_false_alarm_and_the_two_configs_differ(session, runtime, llm_fake, add_call):
    add_call("call_a", THREAT)
    llm_fake.responses = [answer()]  # the LLM does not confirm the keyword hit
    ev = evaluate(session, runtime, [key("call_b", clean=True), key("call_a", clean=True)], only={"call_a"})
    only, plus = (runner.summary_for(ev.results[c])[0] for c in ("rules_only", "rules_plus_llm"))
    assert only.clean_calls_flagged == 1 and plus.clean_calls_flagged == 0
    assert only.overall.precision == 0.0 and plus.overall.f1 == 0.0  # nothing expected, nothing predicted: all zero


def test_v1_is_judged_on_the_keys_time_of_day(session, runtime, llm_fake, add_call):
    add_call("call_v1", CLEAN, called_at=datetime(2026, 11, 3, 9, 0, tzinfo=IST))  # stored at 09:00 ...
    ev = evaluate(session, runtime, [key("call_v1", ("V1", None, None), time="21:40")])  # ... but the key says 21:40
    s, _ = runner.summary_for(ev.results["rules_only"])
    assert s.overall.recall == 1.0 and s.per_rule["V1"].tp == 1


def test_calls_that_cannot_be_evaluated_are_listed_with_a_reason(session, runtime, add_call):
    add_call("call_x", CLEAN, status="failed", with_transcript=False)
    ev = evaluate(session, runtime, [key("call_x"), key("call_y", clean=True)])
    assert dict(ev.not_evaluated) == {
        "call_x": "no cached transcript (status failed)",
        "call_y": "no call with this test key (not recorded or not ingested yet)",
    }
    assert ev.results["rules_only"].outcomes == [] and runner.store(session, ev) == []  # nothing stored


def test_only_restricts_the_run(session, runtime, add_call):
    add_call("call_a", THREAT)
    add_call("call_b", CLEAN)
    ev = evaluate(session, runtime, [key("call_a"), key("call_b")], only={"call_b"})
    assert [o.key.test_key for o in ev.results["rules_only"].outcomes] == ["call_b"]


def test_an_llm_outage_does_not_record_a_misleading_rules_plus_llm_run(session, runtime, llm_fake, add_call):
    add_call("call_a", THREAT)
    llm_fake.responses = [LLMTransientError("down")]
    ev = evaluate(session, runtime, [key("call_a", ("V5", 6.2, None))])
    assert "rules_plus_llm" not in ev.results and "call_a" in ev.warnings[0] and "not recorded" in ev.warnings[0]
    assert [r.config for r in runner.store(session, ev)] == ["rules_only"]


def test_without_an_llm_only_the_baseline_runs(session, add_call):
    add_call("call_a", THREAT)
    ev = runner.evaluate(session, None, [key("call_a")])
    assert list(ev.results) == ["rules_only"] and "No LLM is configured" in ev.warnings[0]


def test_role_accuracy_uses_human_labels_and_falls_back_to_script_order(session, runtime, llm_fake, add_call):
    add_call("call_a", THREAT)
    llm_fake.responses = [answer()]
    right = evaluate(session, runtime, [key("call_a", agent=1)]).results["rules_only"]
    wrong = evaluate(session, runtime, [key("call_a", agent=2)]).results["rules_only"]
    unlabelled = evaluate(session, runtime, [key("call_a")]).results["rules_only"]
    assert runner.summary_for(right)[1] == 1.0 and runner.summary_for(wrong)[1] == 0.0
    assert runner.summary_for(unlabelled)[1] == 1.0 and unlabelled.outcomes[0].role_truth == "script order"
    assert right.outcomes[0].role_truth == "label"


def test_reviewer_decisions_and_disabled_rules_do_not_change_the_evaluation(session, runtime, llm_fake, add_call):
    from app.models import Rule

    add_call("call_a", THREAT)
    llm_fake.responses = [answer([flag("V5", 2, "padosiyon ko bata dunga")])]
    session.get(Rule, "V5").enabled = False  # a reviewer's toggle must not affect a measurement
    session.commit()
    s, _ = runner.summary_for(evaluate(session, runtime, [key("call_a", ("V5", 6.2, None))]).results["rules_only"])
    assert s.overall.recall == 1.0


# ---- stored rows and the API ---------------------------------------------------------------------------------------


def test_stored_rows_match_the_api_shape(session, runtime, llm_fake, add_call, client):
    add_call("call_a", THREAT)
    add_call("call_b", CLEAN)
    llm_fake.responses = [answer([flag("V5", 2, "padosiyon ko bata dunga")]), answer()]
    keys = [key("call_a", ("V5", 6.2, None), split="dev"), key("call_b", clean=True, language="marathi", noisy=True)]
    rows = runner.store(session, evaluate(session, runtime, keys))
    assert {r.config for r in rows} == {"rules_only", "rules_plus_llm"}
    latest = client.get("/eval/latest").json()
    run = latest["rules_plus_llm"]
    assert run["prompt_version"] and run["n_calls"] == 2 and run["models"]["llm"] == "fake/fake-1"
    assert run["overall"] == {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    assert run["clean_calls_total"] == 1 and run["clean_calls_flagged"] == 0 and run["run_at"].endswith("+05:30")
    assert run["per_rule"]["V5"] == {"precision": 1.0, "recall": 1.0, "f1": 1.0, "tp": 1, "fp": 0, "fn": 0}
    assert set(run["per_slice"]) == {"all", "dev", "test", "hinglish", "marathi", "noisy", "not_noisy"}
    assert run["per_slice"]["dev"]["n_calls"] == 1 and run["per_slice"]["marathi"]["n_calls"] == 1
    assert run["failures"] == []


def test_latest_is_null_before_any_run_and_picks_the_newest_after(session, client):
    assert client.get("/eval/latest").json() == {"rules_only": None, "rules_plus_llm": None}
    for hour, n in ((10, 3), (12, 7)):
        session.add(
            EvalRun(
                run_at=datetime(2026, 11, 4, hour, tzinfo=IST), config="rules_only", prompt_version="v1",
                models={"stt": "s", "llm": "none"}, n_calls=n, overall={"precision": 0, "recall": 0, "f1": 0},
                per_rule={}, per_slice={}, failures=[],
            )
        )  # fmt: skip
    session.commit()
    assert client.get("/eval/latest").json()["rules_only"]["n_calls"] == 7


def test_eval_run_endpoint_needs_the_admin_token(client):
    assert client.post("/eval/run").status_code == 403
    r = client.post("/eval/run", headers={"X-Admin-Token": "wrong"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"


def test_eval_run_endpoint_with_no_transcripts_is_a_clear_conflict(client, tmp_path, monkeypatch):
    d = tmp_path / "keys"
    d.mkdir()
    (d / "call_a.json").write_text(json.dumps(
        {"test_key": "call_a", "split": "dev", "language": "hinglish", "called_time_ist": "11:20",
         "borrower_requested_time": False, "noisy": False, "is_clean": True, "expected_violations": []}
    ))  # fmt: skip
    monkeypatch.setattr(keys_mod, "KEYS_DIR", d)
    monkeypatch.setattr(keys_mod, "load_keys", lambda: load_keys(d))
    r = client.post("/eval/run", headers={"X-Admin-Token": "test-admin-token"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "no_data"


def test_eval_run_endpoint_runs_and_stores(client, session, add_call, llm_fake, tmp_path, monkeypatch):
    add_call("call_a", THREAT)
    llm_fake.responses = [answer([flag("V5", 2, "padosiyon ko bata dunga")])]
    d = tmp_path / "keys"
    d.mkdir()
    (d / "call_a.json").write_text(json.dumps(
        {"test_key": "call_a", "split": "test", "language": "hinglish", "called_time_ist": "11:20",
         "borrower_requested_time": False, "noisy": False, "is_clean": False,
         "expected_violations": [{"rule_code": "V5", "approx_time_s": 6.2, "quote_hint": None, "difficulty": "easy"}]}
    ))  # fmt: skip
    monkeypatch.setattr(keys_mod, "load_keys", lambda: load_keys(d))
    r = client.post("/eval/run", headers={"X-Admin-Token": "test-admin-token"})
    assert r.status_code == 200 and r.json()["rules_plus_llm"]["overall"]["recall"] == 1.0
    assert r.json()["rules_only"]["n_calls"] == 1


def test_demo_mode_also_guards_eval_run(client, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("UPLOAD_PASSCODE", "open-sesame")
    get_settings.cache_clear()
    r = client.post("/eval/run", headers={"X-Admin-Token": "test-admin-token"})
    assert r.status_code == 403 and "passcode" in r.json()["error"]["message"]


# ---- the report --------------------------------------------------------------------------------------------------


def test_report_lists_models_slices_rules_and_failures(session, runtime, llm_fake, add_call, tmp_path):
    add_call("call_a", THREAT)
    llm_fake.responses = [answer()]  # the LLM misses the threat
    ev = evaluate(session, runtime, [key("call_a", ("V5", 6.2, "padosiyon")), key("call_z", clean=True)])
    text = report.render(ev, datetime(2026, 11, 6, 14, 30, tzinfo=IST))
    assert text.startswith("# Evaluation report, 2026-11-06 14:30 IST")
    needles = [
        "## rules_only", "## rules_plus_llm", "Prompt version", "| test | 1 |", "| V5 |", "### Known failure cases",
        "call_z (no call with this test key", "`call_a` (test) V5 FN: Missed", "Tuning used the `dev` calls only",
    ]  # fmt: skip
    for needle in needles:
        assert needle in text, needle
    path = report.write_report(ev, datetime(2026, 11, 6, 14, 30, tzinfo=IST), tmp_path / "reports")
    assert path.name == "20261106-143000.md" and path.read_text(encoding="utf-8") == text


def test_report_shows_n_a_for_undefined_ratios(session, runtime, llm_fake, add_call):
    add_call("call_b", CLEAN)
    llm_fake.responses = [answer()]
    text = report.render(evaluate(session, runtime, [key("call_b", clean=True)]), datetime(2026, 11, 6, tzinfo=IST))
    assert "n/a" in text and "None." in text


# ---- answer keys -------------------------------------------------------------------------------------------------


def test_the_real_answer_keys_load_and_match_the_plan_totals():
    keys = load_keys()
    assert len(keys) == 30 and sum(k.is_clean for k in keys) == 12
    assert sum(k.split == "dev" for k in keys) == 10 and sum(k.noisy for k in keys) == 8
    assert sum(k.language == "marathi" for k in keys) == 8


def test_parse_key_defaults_optional_fields():
    k = parse_key(
        {
            "test_key": "c", "split": "dev", "language": "marathi", "called_time_ist": "08:00",
            "borrower_requested_time": True, "noisy": True, "is_clean": True, "expected_violations": [],
        }
    )  # fmt: skip
    assert k.hard_negative is False and k.agent_speaker_id is None and k.expected == ()


def test_load_keys_with_no_files_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_keys(tmp_path)


# ---- labelling ---------------------------------------------------------------------------------------------------


SEGS = [{"start_s": s, "speaker_id": sp, "text": t} for s, e, sp, t in THREAT]


def asker(*answers):
    it = iter(answers)
    prompts = []

    def ask(prompt):
        prompts.append(prompt)
        return next(it)

    ask.prompts = prompts
    return ask


def key_dict(*expected, agent=None):
    return {"test_key": "call_a", "agent_speaker_id": agent,
            "expected_violations": [{"rule_code": r, "approx_time_s": t, "quote_hint": h, "difficulty": "easy"}
                                    for r, t, h in expected]}  # fmt: skip


def test_labelling_sets_the_time_and_the_agent():
    original = key_dict(("V1", None, None), ("V5", None, "padosiyon"))
    shown = []
    new, changed = labelling.label_call(original, SEGS, asker("1", "2"), shown.append)
    assert changed and new["agent_speaker_id"] == 1
    assert new["expected_violations"][0]["approx_time_s"] is None  # V1 is never asked
    assert new["expected_violations"][1]["approx_time_s"] == 6.2
    assert original["expected_violations"][1]["approx_time_s"] is None  # the input was not mutated
    assert shown[2] == "[  2] 0:06  speaker 1: " + THREAT[2][3]


def test_labelling_skips_on_blank_reasks_on_garbage_and_never_overwrites():
    ask = asker("", "99", "abc", "3")
    new, changed = labelling.label_call(key_dict(("V4", None, None), ("V5", 12.0, None)), SEGS, ask, lambda _: None)
    assert changed and new["agent_speaker_id"] is None  # blank skipped the agent question
    assert new["expected_violations"][0]["approx_time_s"] == 12.5  # the third try was valid
    assert new["expected_violations"][1]["approx_time_s"] == 12.0  # already labelled: not asked
    assert len(ask.prompts) == 4


def test_labelling_a_fully_labelled_key_asks_nothing():
    ask = asker()
    new, changed = labelling.label_call(key_dict(("V5", 6.2, None), agent=1), SEGS, ask, lambda _: None)
    assert not changed and ask.prompts == []


def test_saved_keys_keep_unicode_and_end_with_a_newline(tmp_path):
    p = tmp_path / "k.json"
    labelling.save_key(p, {"quote_hint": "उद्या पोलीस"})
    text = p.read_text(encoding="utf-8")
    assert "उद्या पोलीस" in text and text.endswith("\n") and json.loads(text)["quote_hint"] == "उद्या पोलीस"


# ---- ingest ------------------------------------------------------------------------------------------------------


@pytest.fixture
def folders(tmp_path):
    audio, scripts = tmp_path / "recordings", tmp_path / "scripts"
    audio.mkdir()
    scripts.mkdir()
    (scripts / "call_a.md").write_text(
        "# call_a\n\n[Agent: Sneha Kulkarni | Borrower: X | Loan: SF-PL-111 | Time: 21:40 | Language: Hinglish]\n"
    )
    return audio, scripts


def test_ingest_registers_recordings_as_queued_test_calls(session, runtime, folders):
    audio, scripts = folders
    make_wav(audio / "call_a.wav")
    keys = [key("call_a", time="21:40"), key("call_b")]
    calls, notes = ingest_mod.ingest(
        session, runtime.storage, runtime.settings, keys, audio_dir=audio, scripts_dir=scripts,
        now=datetime(2026, 11, 6, 15, 0, tzinfo=IST),
    )  # fmt: skip
    assert len(calls) == 1 and notes == [f"call_b: no recording in {audio}"]
    c = session.scalars(select(Call)).one()
    assert (c.test_key, c.is_test_set, c.status, c.language, c.loan_ref) == (
        "call_a",
        True,
        "queued",
        "hinglish",
        "SF-PL-111",
    )
    assert c.called_at.astimezone(IST).isoformat() == "2026-11-05T21:40:00+05:30"  # yesterday, at the key's time
    assert c.agent.name == "Sneha Kulkarni" and runtime.storage.local_path(c.audio_path).exists()
    assert c.duration_s == pytest.approx(5.0, abs=0.3)


def test_ingest_twice_does_not_duplicate_and_rejects_unreadable_audio(session, runtime, folders):
    audio, scripts = folders
    make_wav(audio / "call_a.wav")
    (audio / "call_b.mp3").write_bytes(b"not audio")
    kw = dict(audio_dir=audio, scripts_dir=scripts)
    keys = [key("call_a"), key("call_b")]
    ingest_mod.ingest(session, runtime.storage, runtime.settings, keys, **kw)
    calls, notes = ingest_mod.ingest(session, runtime.storage, runtime.settings, keys, **kw)
    assert session.query(Call).count() == 1 and len(calls) == 1
    assert notes == ["call_b: That file is not a readable audio file."]


def test_find_audio_and_script_fallbacks(folders):
    audio, scripts = folders
    assert ingest_mod.find_audio("call_a", audio) is None
    (audio / "call_a.m4a").write_bytes(b"x")
    assert ingest_mod.find_audio("call_a", audio).name == "call_a.m4a"
    assert ingest_mod.script_details("call_a", scripts) == ("Sneha Kulkarni", "SF-PL-111")
    assert ingest_mod.script_details("missing", scripts) == ("Test agent", "TEST-MISSING")


# ---- command line ------------------------------------------------------------------------------------------------


def test_cli_run_with_nothing_ingested_says_so(session, capsys):
    from app.evaluation import cli

    assert cli.main(["run"]) == 1
    assert "Nothing to evaluate" in capsys.readouterr().out


def test_cli_ingest_without_recordings_sends_nothing_to_gnani(session, capsys, gnani_fake, monkeypatch, tmp_path):
    from app.evaluation import cli

    monkeypatch.setattr(ingest_mod, "AUDIO_DIR", tmp_path / "none")
    monkeypatch.setattr(cli.ingest_mod, "ingest", lambda *a, **k: ([], ["call_01: no recording"]))
    assert cli.main(["ingest", "--only", "call_01"]) == 0
    out = capsys.readouterr().out
    assert "call_01: no recording" in out and "0 test calls registered" in out and gnani_fake.requests == []


def test_cli_ingest_asks_before_spending_credits_and_declining_sends_nothing(
    session, runtime, capsys, gnani_fake, monkeypatch, tmp_path
):
    from app.evaluation import cli

    make_wav(tmp_path / "call_01.wav", seconds=60)
    real = ingest_mod.ingest
    monkeypatch.setattr(
        cli.ingest_mod, "ingest", lambda *a, **k: real(*a, **{**k, "audio_dir": tmp_path, "scripts_dir": tmp_path})
    )
    monkeypatch.setattr(cli, "load_keys", lambda: [key("call_01")])
    monkeypatch.setattr("builtins.input", lambda prompt="": "no")
    assert cli.main(["ingest"]) == 0
    out = capsys.readouterr().out
    assert "1 need transcribing: 1.0 audio minutes, about 0.3 Gnani credits" in out and "Nothing sent to Gnani." in out
    assert gnani_fake.requests == []


def test_report_lists_calls_with_a_synthetic_borrower(session, runtime, llm_fake, add_call):
    add_call("call_a", THREAT)
    add_call("call_b", CLEAN)
    llm_fake.responses = [answer()]
    ev = evaluate(session, runtime, [key("call_a"), key("call_b", clean=True)])
    prov = {"call_b": {"borrower": "synthetic"}, "call_z": {"borrower": "synthetic"}}  # call_z was not evaluated
    text = report.render(ev, datetime(2026, 11, 6, tzinfo=IST), prov)
    assert (
        "Synthetic borrower voice (1 of 2 calls):** call_b." in text and "call_z" not in text.split("## rules_only")[0]
    )
    assert "Synthetic borrower" not in report.render(ev, datetime(2026, 11, 6, tzinfo=IST))
