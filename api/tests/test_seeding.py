from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import db
from app.models import Agent, Base, Call, EvalRun, LlmCache, Rule, Segment, Violation
from app.seed import seed_rules
from app.seeding import ROSTER, copy_data, redate, reset_demo, seed_reference_data
from app.storage.local import LocalStorage
from tests.helpers import IST, make_agent, make_call, make_wav

TODAY = datetime(2026, 11, 6, 15, 0, tzinfo=IST)


# ---- reference data ----------------------------------------------------------------------------------------------


def test_seed_adds_nine_rules_and_six_agents_once(session):
    session.query(Rule).delete()
    session.commit()
    first = seed_reference_data(session)
    session.commit()
    assert session.query(Rule).count() == 9 and [
        a.name for a in session.scalars(select(Agent).order_by(Agent.name))
    ] == sorted(ROSTER)
    assert first.counts["agents added"] == 6
    again = seed_reference_data(session)
    assert "agents added" not in again.counts and session.query(Agent).count() == 6


def test_seed_keeps_existing_agents_and_a_rules_enabled_switch(session):
    make_agent(session, "rohit patil", "Field")  # the same person, different spelling and team
    session.get(Rule, "V3").enabled = False
    session.commit()
    seed_reference_data(session)
    session.commit()
    assert session.query(Agent).count() == 6 and session.get(Rule, "V3").enabled is False


def test_redate_keeps_the_time_of_day_and_stays_in_the_last_14_days():
    stored_utc = datetime(2026, 5, 1, 16, 10)  # 21:40 IST the same evening, written as UTC 16:10
    stored_utc = stored_utc.replace(tzinfo=__import__("datetime").UTC)
    for i in range(30):
        d = redate(stored_utc, i, TODAY)
        assert (d.hour, d.minute) == (21, 40) and d.tzinfo is not None
        assert 0 <= (TODAY.date() - d.date()).days <= 13
    assert redate(stored_utc, 0, TODAY).date() == TODAY.date() and redate(stored_utc, 14, TODAY).date() == TODAY.date()


# ---- copying -----------------------------------------------------------------------------------------------------


@pytest.fixture
def worlds(tmp_path):
    """A 'local' database with processed calls and an empty destination, each with its own audio folder."""
    src_engine, dst_engine = (db.make_engine(f"sqlite:///{tmp_path / n}") for n in ("src.db", "dst.db"))
    for e in (src_engine, dst_engine):
        Base.metadata.create_all(e)
    src, dst = Session(src_engine), Session(dst_engine)
    for s in (src, dst):
        seed_rules(s)
        s.commit()
    src_audio, dst_audio = LocalStorage(tmp_path / "src_audio"), LocalStorage(tmp_path / "dst_audio")

    rohit = make_agent(src, "Rohit Patil")
    other = make_agent(src, "Visitor Agent")
    test_call = make_call(src, rohit, called_at=datetime(2026, 5, 1, 21, 40, tzinfo=IST), test_key="call_07",
                          violations=[("V1", "confirmed"), ("V5", "open")])  # fmt: skip
    test_call.is_test_set = True
    test_call.raw_transcript = {"segments": [{"text": "secret original 9876543210"}]}
    test_call.audio_path = src_audio.save(str(test_call.id), make_wav(tmp_path / "t.wav", 2), "t.wav")
    upload = make_call(src, other, loan_ref="UP-1")
    upload.audio_path = src_audio.save(str(upload.id), make_wav(tmp_path / "u.wav", 2), "u.wav")
    for hour, n in ((10, 4), (12, 9)):
        src.add(EvalRun(run_at=datetime(2026, 11, 4, hour, tzinfo=IST), config="rules_only", prompt_version="v1",
                        models={"stt": "s", "llm": "none"}, n_calls=n, overall={"precision": 1, "recall": 1, "f1": 1},
                        per_rule={}, per_slice={}, failures=[]))  # fmt: skip
    src.add(LlmCache(key="k" * 64, response={"violations": []}))
    src.get(Rule, "V4").enabled = False
    src.commit()

    make_agent(dst, "Rohit Patil")  # the destination already has the roster entry, under another id
    return {"src": src, "dst": dst, "src_audio": src_audio, "dst_audio": dst_audio, "test": test_call, "upload": upload,
            "rohit": rohit}  # fmt: skip


def run(w, **kw):
    r = copy_data(w["src"], w["dst"], src_storage=w["src_audio"], dst_storage=w["dst_audio"], today=TODAY, **kw)
    w["dst"].commit()
    return r


def test_seed_from_local_copies_only_processed_test_calls_redated(worlds):
    report = run(worlds, only_test_set=True, redate_calls=True)
    dst = worlds["dst"]
    (call,) = dst.scalars(select(Call)).all()
    assert call.test_key == "call_07" and call.is_test_set and call.status == "done"
    assert (call.called_at.astimezone(IST).hour, call.called_at.astimezone(IST).minute) == (21, 40)  # V1 still applies
    assert 0 <= (TODAY.date() - call.called_at.astimezone(IST).date()).days <= 13
    assert call.raw_transcript == worlds["test"].raw_transcript  # the transcript is reused, never re-fetched
    assert dst.query(Segment).count() == 6
    statuses = {v.rule_code: v.reviewer_status for v in dst.scalars(select(Violation))}
    assert statuses == {"V1": "confirmed", "V5": "open"}
    assert call.agent.name == "Rohit Patil" and dst.query(Agent).count() == 1  # mapped to the existing agent
    assert call.agent_id != worlds["rohit"].id
    assert (
        worlds["dst_audio"].local_path(call.audio_path).read_bytes()
        == worlds["src_audio"].local_path(call.audio_path).read_bytes()
    )
    assert [(r.config, r.n_calls) for r in dst.scalars(select(EvalRun))] == [("rules_only", 9)]  # only the latest run
    assert dst.query(LlmCache).count() == 1 and dst.get(Rule, "V4").enabled is False
    assert report.counts["calls copied"] == 1 and report.counts["audio files uploaded"] == 1


def test_a_full_migration_copies_everything_without_changing_dates(worlds):
    run(worlds)
    dst = worlds["dst"]
    assert dst.query(Call).count() == 2 and dst.query(Agent).count() == 2 and dst.query(EvalRun).count() == 2
    moved = dst.get(Call, worlds["test"].id)
    assert moved.called_at == worlds["test"].called_at
    assert dst.get(Call, worlds["upload"].id).agent.name == "Visitor Agent"


def test_copying_twice_changes_nothing_and_replace_overwrites(worlds):
    run(worlds)
    second = run(worlds)
    assert second.counts["calls skipped (already there)"] == 2 and "calls copied" not in second.counts
    assert worlds["dst"].query(Call).count() == 2 and worlds["dst"].query(Violation).count() == 2
    worlds["src"].get(Call, worlds["test"].id).loan_ref = "CHANGED"
    worlds["src"].commit()
    run(worlds, replace=True)
    assert (
        worlds["dst"].get(Call, worlds["test"].id).loan_ref == "CHANGED" and worlds["dst"].query(Violation).count() == 2
    )


def test_a_missing_audio_file_is_reported_not_fatal(worlds):
    worlds["src_audio"].local_path(worlds["test"].audio_path).unlink()
    report = run(worlds, only_test_set=True)
    assert worlds["dst"].query(Call).count() == 1 and any("call_07" in n and "not copied" in n for n in report.notes)


def test_audio_goes_to_the_destination_storage_under_its_own_key(worlds, tmp_path):
    from app.storage.supabase import SupabaseStorage
    from tests.fakes.supabase_fake import PROJECT, SERVICE_KEY, FakeSupabaseStorage

    fake = FakeSupabaseStorage()
    dest = SupabaseStorage(PROJECT, SERVICE_KEY, "call-audio", http=fake.client(), cache_dir=tmp_path / "c")
    copy_data(worlds["src"], worlds["dst"], src_storage=worlds["src_audio"], dst_storage=dest, today=TODAY)
    assert set(fake.objects) == {worlds["test"].audio_path, worlds["upload"].audio_path}


# ---- resetting the demo ------------------------------------------------------------------------------------------


def test_reset_restores_the_seeded_state(session, tmp_path):
    storage = LocalStorage(tmp_path / "reset_audio")
    seed_reference_data(session)
    rohit = session.scalars(select(Agent).where(Agent.name == "Rohit Patil")).one()
    kept = make_call(session, rohit, test_key="call_01", violations=[("V5", "dismissed"), ("V4", "confirmed")])
    kept.is_test_set = True
    visitor_agent = make_agent(session, "Visitor Agent")
    visitor_call = make_call(session, visitor_agent, loan_ref="UP")
    visitor_call.audio_path = storage.save(str(visitor_call.id), make_wav(tmp_path / "v.wav", 1), "v.wav")
    session.get(Rule, "V9").enabled = False
    unused_agent = make_agent(session, "Unused Visitor")
    session.commit()
    path = storage.local_path(visitor_call.audio_path)
    assert path.exists() and kept.score == 70  # the confirmed critical costs 30; the dismissed high flag does not count

    report = reset_demo(session, storage)
    session.commit()
    assert not path.exists() and session.get(Call, visitor_call.id) is None
    assert session.get(Agent, visitor_agent.id) is None and session.get(Agent, unused_agent.id) is None
    assert session.query(Agent).count() == 6  # the roster is back to exactly the six
    assert {v.reviewer_status for v in session.get(Call, kept.id).violations} == {"open"}
    assert all(r.enabled for r in session.scalars(select(Rule)))
    assert session.get(Call, kept.id).score == 55  # V5 high (-15) and V4 critical (-30), nothing dismissed
    assert report.counts["uploaded calls removed"] == 1 and report.counts["reviewer decisions cleared"] == 2


def test_reset_keeps_an_extra_agent_who_has_test_calls(session, tmp_path):
    extra = make_agent(session, "Script Agent")
    make_call(session, extra, test_key="call_02").is_test_set = True
    session.commit()
    reset_demo(session, LocalStorage(tmp_path / "a"))
    assert session.get(Agent, extra.id) is not None


def test_reset_restores_swapped_roles_by_reanalysing_from_the_cache(session, tmp_path):
    call = make_call(session, make_agent(session), test_key="call_03")
    call.is_test_set = True
    call.analysis_meta = {"agent_speaker_override": 2, "llm_failed": False}
    session.commit()
    seen = []
    report = reset_demo(session, LocalStorage(tmp_path / "a"), lambda s, c: seen.append((c.id, dict(c.analysis_meta))))
    assert seen == [(call.id, {"llm_failed": False})] and report.counts["swapped roles restored"] == 1
    without = make_call(session, call.agent, test_key="call_04")
    without.is_test_set = True
    without.analysis_meta = {"agent_speaker_override": 1}
    session.commit()
    note = reset_demo(session, LocalStorage(tmp_path / "a")).notes
    assert note == ["call_04: roles were swapped; run a retry to restore them"]
