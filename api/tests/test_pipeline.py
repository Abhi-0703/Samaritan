from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from app import db
from app.models import Call, Rule, Segment, Violation
from app.services.pipeline import QueueHalt, analyse_call, process_call, queued_call_ids
from tests.fakes.gnani_fake import FakeGnani
from tests.fakes.llm_fake import answer, flag
from tests.helpers import IST, make_agent, make_wav

SEGMENTS = [
    (0.0, 4.0, 1, "Namaste, main Rohit Patil bol raha hoon Sahyog Finance se."),
    (4.2, 6.0, 2, "Haan ji boliye. Mera number 9876543210 hai."),
    (6.2, 12.0, 1, "Kal tak payment nahi aaya toh main padosiyon ko bata dunga ki aap defaulter ho."),
    (12.5, 15.0, 2, "Aisa mat kijiye. Main paanch tarikh tak kar dunga."),
]
V5 = flag("V5", 2, "padosiyon ko bata dunga")


@pytest.fixture
def make_queued(session, runtime):
    def make(called_at=None, language="hinglish") -> Call:
        agent = make_agent(session)
        call = Call(
            agent_id=agent.id, loan_ref="SF-PL-204871", language=language, audio_path="",
            called_at=called_at or datetime(2026, 11, 3, 11, 20, tzinfo=IST), status="queued",
        )  # fmt: skip
        session.add(call)
        session.flush()
        call.audio_path = runtime.storage.save(str(call.id), make_wav(runtime.storage.root / "src.wav"), "call.wav")
        session.commit()
        return call

    return make


def run(session, runtime, call, llm="runtime"):
    process_call(
        session, call.id, runtime.gnani, runtime.llm if llm == "runtime" else llm, runtime.storage, runtime.settings
    )
    session.expire_all()
    return session.get(Call, call.id)


def test_happy_path_end_to_end(session, runtime, gnani_fake, llm_fake, make_queued):
    gnani_fake.default_segments = SEGMENTS
    llm_fake.responses = [answer([V5])]
    seen = []
    gnani_fake.on_request = lambda m, p: (
        seen.append(("gnani", session_status(call.id))) if p == "/stt/v3/batch/jobs" else None
    )
    llm_fake.on_call = lambda: seen.append(("llm", session_status(call.id)))
    call = make_queued()

    def session_status(cid):
        with db.session_factory()() as s:
            return s.get(Call, cid).status

    done = run(session, runtime, call)
    assert seen == [("gnani", "transcribing"), ("llm", "analysing")]  # status was visible while each stage ran
    assert done.status == "done" and done.error is None and done.processed_at
    assert done.gnani_job_id and done.transcription_config["num_speakers"] == 2
    assert done.agent_speaker_id == 1 and done.roles_look_correct is True
    segs = session.scalars(select(Segment).where(Segment.call_id == call.id).order_by(Segment.idx)).all()
    assert [s.speaker for s in segs] == ["agent", "borrower", "agent", "borrower"]
    assert "[PHONE]" in segs[1].text and "9876543210" not in " ".join(s.text for s in segs)
    assert "9876543210" in str(done.raw_transcript)  # the raw transcript keeps it, server-side only
    v = session.scalars(select(Violation).where(Violation.call_id == call.id)).all()
    assert [(x.rule_code, x.detected_by, x.reviewer_status) for x in v] == [("V5", "both", "open")]
    assert v[0].segment_id == segs[2].id and v[0].start_s == 6.2 and "padosiyon" in v[0].quote
    assert done.score == 85  # high: -15
    meta = done.analysis_meta
    assert meta["llm_failed"] is False and meta["llm_provider_used"] == "fake" and meta["prompt_version"]
    assert meta["llm_prompt_tokens"] == 400


def test_v1_is_metadata_and_needs_no_segment(session, runtime, gnani_fake, make_queued):
    gnani_fake.default_segments = SEGMENTS
    done = run(session, runtime, make_queued(called_at=datetime(2026, 11, 3, 21, 40, tzinfo=IST)))
    v1 = session.scalars(select(Violation).where(Violation.call_id == done.id, Violation.rule_code == "V1")).one()
    assert (v1.detected_by, v1.segment_id, v1.start_s, v1.confidence) == ("metadata", None, None, 1.0)
    assert done.score == 85


def test_cached_transcript_skips_gnani(session, runtime, gnani_fake, make_queued):
    gnani_fake.default_segments = SEGMENTS
    call = make_queued()
    run(session, runtime, call)
    gnani_fake.requests.clear()
    call.status = "queued"
    session.commit()
    again = run(session, runtime, call)
    assert again.status == "done" and gnani_fake.requests == []


def test_saved_job_id_is_resumed_not_recreated(session, runtime, gnani_fake, make_queued):
    gnani_fake.default_segments = SEGMENTS
    call = make_queued()
    job_id, _ = runtime.gnani.create_job(
        runtime.storage.local_path(call.audio_path), {"model": "prisma-v3.0", "language_code": "hi-IN,en-IN"}
    )
    runtime.gnani.start_job(job_id)  # the job existed before the "restart"
    call.gnani_job_id = job_id
    session.commit()
    gnani_fake.requests.clear()
    done = run(session, runtime, call)
    assert done.status == "done" and done.gnani_job_id == job_id
    assert ("POST", "/stt/v3/batch/jobs") not in gnani_fake.requests


def test_non_fatal_gnani_failure_marks_the_call_failed_with_a_reason(session, runtime, gnani_fake, make_queued):
    gnani_fake.job_outcome = "FAILED"
    done = run(session, runtime, make_queued())
    assert done.status == "failed" and "UNSUPPORTED_LANGUAGE" in done.error and done.raw_transcript is None


def test_credits_exhausted_fails_the_call_and_halts_the_queue(session, runtime, gnani_fake, make_queued):
    gnani_fake.credits_exhausted = True
    call = make_queued()
    with pytest.raises(QueueHalt) as e:
        process_call(session, call.id, runtime.gnani, runtime.llm, runtime.storage, runtime.settings)
    session.expire_all()
    failed = session.get(Call, call.id)
    assert failed.status == "failed" and failed.error == "Gnani credits exhausted or key not permitted."
    assert "credits" in str(e.value).lower()


def test_llm_outage_keeps_layer1_results_and_flags_the_call(session, runtime, gnani_fake, llm_fake, make_queued):
    from app.services.llm.base import LLMTransientError

    gnani_fake.default_segments = SEGMENTS
    llm_fake.responses = [LLMTransientError("down")]
    done = run(session, runtime, make_queued())
    assert done.status == "done" and done.analysis_meta["llm_failed"] is True and done.roles_look_correct
    v = session.scalars(select(Violation).where(Violation.call_id == done.id)).all()
    assert {x.rule_code for x in v} == {"V5"} and all(x.detected_by == "rules" for x in v)


def test_no_llm_configured_is_the_same_as_an_outage(session, runtime, gnani_fake, make_queued):
    gnani_fake.default_segments = SEGMENTS
    done = run(session, runtime, make_queued(), llm=None)
    assert done.analysis_meta["llm_failed"] is True and done.status == "done"


def test_invented_quotes_never_become_violations(session, runtime, gnani_fake, llm_fake, make_queued):
    gnani_fake.default_segments = SEGMENTS
    llm_fake.responses = [answer([flag("V4", 2, "kal police aa jayegi aur jail bhej denge")])]
    done = run(session, runtime, make_queued())
    assert (
        session.scalars(select(Violation).where(Violation.call_id == done.id)).all() == []
    )  # and L1's V5 candidate was dropped
    assert done.analysis_meta["llm_rejected"] == 1 and done.score == 100


def test_disabled_rules_are_skipped_in_analysis(session, runtime, gnani_fake, llm_fake, make_queued):
    gnani_fake.default_segments = SEGMENTS
    llm_fake.responses = [answer([V5])]
    session.get(Rule, "V5").enabled = False
    session.commit()
    done = run(session, runtime, make_queued())
    assert session.scalars(select(Violation).where(Violation.call_id == done.id)).all() == [] and done.score == 100
    assert "DISABLED: do not report" in llm_fake.calls[0][0]


def test_reanalysis_keeps_reviewer_decisions(session, runtime, gnani_fake, llm_fake, make_queued):
    gnani_fake.default_segments = SEGMENTS
    llm_fake.responses = [answer([V5])]
    call = run(session, runtime, make_queued())
    v = session.scalars(select(Violation).where(Violation.call_id == call.id)).one()
    v.reviewer_status = "dismissed"
    session.commit()
    analyse_call(session, session.get(Call, call.id), runtime.llm)
    session.expire_all()
    again = session.scalars(select(Violation).where(Violation.call_id == call.id)).one()
    assert again.reviewer_status == "dismissed" and again.id != v.id
    assert session.get(Call, call.id).score == 100  # dismissed flags do not count


def test_marathi_call_runs_end_to_end(session, runtime, gnani_fake, llm_fake, make_queued):
    gnani_fake.default_segments = [
        (0.0, 5.0, 1, "नमस्कार, मी रोहित पाटील बोलतोय सहयोग फायनान्स मधून."),
        (5.5, 8.0, 2, "हो, बोला. पगार उशिरा झाला."),
        (8.5, 14.0, 1, "उद्या पोलीस तुमच्या दारात येतील आणि तुम्हाला तुरुंगात जावं लागेल."),
    ]
    llm_fake.responses = [answer([flag("V4", 2, "उद्या पोलीस तुमच्या दारात येतील")])]
    done = run(session, runtime, make_queued(language="marathi"))
    assert done.transcription_config["language_code"] == "mr-IN,en-IN" and done.score == 70
    v = session.scalars(select(Violation).where(Violation.call_id == done.id)).one()
    assert (v.rule_code, v.detected_by) == ("V4", "both")


def test_unreadable_audio_fails_with_a_clear_message(session, runtime, make_queued):
    call = make_queued()
    runtime.storage.local_path(call.audio_path).write_bytes(b"not audio")
    done = run(session, runtime, call)
    assert done.status == "failed" and "not a readable audio" in done.error


def test_unexpected_errors_fail_the_call_without_a_stack_trace(session, runtime, gnani_fake, make_queued, monkeypatch):
    gnani_fake.default_segments = SEGMENTS
    monkeypatch.setattr(
        "app.services.pipeline.mask_pii", lambda t: (_ for _ in ()).throw(RuntimeError("secret internals"))
    )
    done = run(session, runtime, make_queued())
    assert done.status == "failed" and done.error == "Analysis failed: RuntimeError. Retry the call."
    assert "secret internals" not in done.error


def test_queued_call_ids_lists_unfinished_calls_oldest_first(session, runtime, make_queued):
    a, b = make_queued(), make_queued()
    b.status = "transcribing"
    c = make_queued()
    c.status = "done"
    session.commit()
    assert queued_call_ids(session) == [a.id, b.id]


def test_fake_gnani_key_never_logged(session, runtime, gnani_fake, make_queued, caplog):
    gnani_fake.default_segments = SEGMENTS
    with caplog.at_level("DEBUG"):
        run(session, runtime, make_queued())
    assert "test-gnani-key-0000" not in caplog.text
    assert isinstance(gnani_fake, FakeGnani)
