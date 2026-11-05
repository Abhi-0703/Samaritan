"""Evaluation command line (the thin scripts in eval/ call this).

    python -m app.evaluation.cli ingest [--only call_01 call_02] [--yes]   register recordings and transcribe them
    python -m app.evaluation.cli run [--only ...]                          evaluate the cached transcripts
    python -m app.evaluation.cli label [--only ...]                        label times and speakers in the answer keys

`ingest` spends Gnani credits and asks first. `run` never transcribes. Tune on dev calls only.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

from sqlalchemy import select

from app import db
from app.config import get_settings
from app.detection.llm_judge import PROMPT_VERSION
from app.evaluation import ingest as ingest_mod
from app.evaluation import labelling, report, runner
from app.evaluation.keys import KEYS_DIR, REPORTS_DIR, key_path, load_keys
from app.migrate import upgrade_to_head
from app.models import Call
from app.seed import seed_rules
from app.services.gnani_client import client_from_settings
from app.services.llm import build_llm_service
from app.services.pipeline import QueueHalt, process_call
from app.storage import get_storage

CREDITS_PER_MINUTE = 20 / 60


def _setup():
    settings = get_settings()
    if settings.database_url.startswith("sqlite"):
        upgrade_to_head()
    db.init_db()
    with db.session_scope() as s:
        seed_rules(s)
    return settings, db.session_factory()


def _llm(settings):
    try:
        return build_llm_service(settings, PROMPT_VERSION)
    except Exception as e:  # a missing key is not fatal: the rules-only baseline still runs
        print(f"LLM unavailable ({type(e).__name__}); only rules_only will run.", file=sys.stderr)
        return None


def cmd_ingest(args) -> int:
    settings, factory = _setup()
    keys = load_keys()
    with factory() as session:
        calls, notes = ingest_mod.ingest(session, get_storage(), settings, keys, set(args.only or []))
        for n in notes[:5]:
            print("note:", n)
        if len(notes) > 5:
            print(f"note: ... and {len(notes) - 5} more without a recording")
        todo = [c for c in calls if not c.raw_transcript and c.status != "done"]
        minutes = sum((c.duration_s or 0) for c in todo) / 60
        print(f"{len(calls)} test calls registered; {len(todo)} need transcribing: {minutes:.1f} audio minutes, "
              f"about {minutes * CREDITS_PER_MINUTE:.1f} Gnani credits.")  # fmt: skip
        if not todo:
            return 0
        if not args.yes and input("Transcribe them with Gnani now? Type yes to continue: ").strip().lower() != "yes":
            print("Nothing sent to Gnani.")
            return 0
        gnani, llm, storage = client_from_settings(settings), _llm(settings), get_storage()
        for call in todo:
            print(f"processing {call.test_key} ...", flush=True)
            try:
                process_call(session, call.id, gnani, llm, storage, settings)
            except QueueHalt as e:
                print(f"Stopped: {e}")
                return 1
            session.refresh(call)
            print(f"  {call.status}" + (f": {call.error}" if call.error else ""))
    return 0


def cmd_run(args) -> int:
    settings, factory = _setup()
    keys = load_keys()
    with factory() as session:
        ev = runner.evaluate(session, _llm(settings), keys, set(args.only or []))
        if not any(r.outcomes for r in ev.results.values()):
            print("Nothing to evaluate. Ingest recordings first.")
            for k, why in ev.not_evaluated[:5]:
                print(f"  {k}: {why}")
            if len(ev.not_evaluated) > 5:
                print(f"  ... and {len(ev.not_evaluated) - 5} more")
            return 1
        runner.store(session, ev)
        path = report.write_report(ev, datetime.now(runner.IST), REPORTS_DIR)
    print(f"Report written to {path}")
    for w in ev.warnings:
        print("warning:", w)
    return 0


def cmd_label(args) -> int:
    _, factory = _setup()
    with factory() as session:
        for k in load_keys():
            if args.only and k.test_key not in args.only:
                continue
            call = session.scalars(select(Call).where(Call.test_key == k.test_key)).first()
            if call is None or not call.raw_transcript:
                print(f"{k.test_key}: no cached transcript, skipped")
                continue
            path = key_path(k.test_key, KEYS_DIR)
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("agent_speaker_id") is not None and all(
                v["approx_time_s"] is not None or v["rule_code"] in ("V1", "V8") for v in data["expected_violations"]
            ):
                continue
            print(f"\n=== {k.test_key} ({k.language}, {k.split}) ===")
            segments = call.raw_transcript.get("segments", [])
            new, changed = labelling.label_call(data, segments, input)
            if changed:
                labelling.save_key(path, new)
                print("saved")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eval", description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, fn in (("ingest", cmd_ingest), ("run", cmd_run), ("label", cmd_label)):
        p = sub.add_parser(name)
        p.add_argument("--only", nargs="*", help="test keys, e.g. call_01 call_02")
        if name == "ingest":
            p.add_argument("--yes", action="store_true", help="skip the confirmation (spends credits)")
        p.set_defaults(fn=fn)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
