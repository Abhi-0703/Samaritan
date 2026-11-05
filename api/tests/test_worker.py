from __future__ import annotations

import threading
import time
import uuid

from sqlalchemy.orm import Session

from app.models import Call
from app.services.pipeline import QueueHalt
from app.worker import Worker
from tests.helpers import make_agent, make_call


def make_worker(session: Session, process):
    from app import db

    return Worker(db.session_factory(), process)


def test_enqueue_ignores_a_call_already_waiting(session):
    w = make_worker(session, lambda s, i: None)
    cid = uuid.uuid4()
    assert w.enqueue(cid) is True and w.enqueue(cid) is False and w.pending == 1


def test_a_call_can_be_enqueued_again_once_it_has_run(session):
    w = make_worker(session, lambda s, i: None)
    cid = uuid.uuid4()
    w.enqueue(cid)
    w.drain()
    assert w.enqueue(cid) is True


def test_calls_run_one_at_a_time_in_order(session):
    order = []
    w = make_worker(session, lambda s, i: order.append(i))
    ids = [uuid.uuid4() for _ in range(3)]
    for i in ids:
        w.enqueue(i)
    assert w.drain() == 3 and order == ids


def test_a_failing_call_does_not_stop_the_queue(session):
    seen = []

    def process(s, cid):
        seen.append(cid)
        if len(seen) == 1:
            raise RuntimeError("boom")

    w = make_worker(session, process)
    a, b = uuid.uuid4(), uuid.uuid4()
    w.enqueue(a)
    w.enqueue(b)
    assert w.drain() == 2 and seen == [a, b] and w.paused is False


def test_a_fatal_gnani_error_pauses_and_a_retry_resumes(session):
    def process(s, cid):
        raise QueueHalt("Gnani credits exhausted")

    w = make_worker(session, process)
    a, b = uuid.uuid4(), uuid.uuid4()
    w.enqueue(a)
    w.enqueue(b)
    assert w.drain() == 1  # stops after the first
    assert w.paused and "credits" in w.pause_reason and w.pending == 1
    assert w.drain() == 0  # still paused
    w.resume()
    assert not w.paused and w.pause_reason is None
    assert w.drain() == 1 and w.paused and w.pending == 0  # the second runs, and halts again as this fake always does


def test_resume_unfinished_picks_up_calls_left_mid_flight(session):
    agent = make_agent(session)
    queued = make_call(session, agent, status="queued")
    mid = make_call(session, agent, status="transcribing")
    make_call(session, agent, status="done")
    make_call(session, agent, status="failed")
    seen = []
    w = make_worker(session, lambda s, i: seen.append(i))
    assert w.resume_unfinished() == 2
    assert w.resume_unfinished() == 0  # nothing is queued twice
    w.drain()
    assert set(seen) == {queued.id, mid.id}


def test_the_background_thread_processes_calls_and_stops(session):
    done = threading.Event()
    w = make_worker(session, lambda s, i: done.set())
    w.start()
    w.start()  # a second start does not spawn a second thread
    w.enqueue(uuid.uuid4())
    assert done.wait(5)
    w.stop()
    assert w._thread is not None and not w._thread.is_alive()


def test_the_real_pipeline_runs_through_the_worker(session, runtime, gnani_fake, llm_fake):
    from tests.fakes.llm_fake import answer
    from tests.helpers import make_wav

    gnani_fake.default_segments = [
        (0.0, 3.0, 1, "Namaste, main Rohit Patil Sahyog Finance se bol raha hoon."),
        (3.5, 5.0, 2, "Haan."),
    ]
    llm_fake.responses = [answer()]
    agent = make_agent(session)
    call = Call(agent_id=agent.id, loan_ref="L1", language="hinglish", audio_path="", status="queued",
                called_at=make_call(session, agent).called_at)  # fmt: skip
    session.add(call)
    session.flush()
    call.audio_path = runtime.storage.save(str(call.id), make_wav(runtime.storage.root / "a.wav"), "a.wav")
    session.commit()
    runtime.worker.enqueue(call.id)
    started = time.monotonic()
    runtime.worker.drain()
    session.expire_all()
    assert session.get(Call, call.id).status == "done" and time.monotonic() - started < 30
