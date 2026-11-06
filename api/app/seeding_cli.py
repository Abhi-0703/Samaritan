"""Command line for the database scripts in scripts/ (all of them dry-run unless given --yes).

    seed                    the 9 rules and 6 agents; with --from-local, also the processed test-set calls, redated
    migrate_local_to_supabase   a straight copy of local calls, audio, cached transcripts and the LLM cache
    reset_demo              uploads removed, reviewer decisions and rule switches back to the seeded state

The destination is whatever DATABASE_URL and STORAGE_BACKEND say in api/.env. Passwords and keys are never printed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app import db
from app.config import API_DIR, Settings, get_settings
from app.seed import seed_rules
from app.seeding import Report, copy_data, reset_demo, seed_reference_data
from app.services.pipeline import analyse_call
from app.storage import get_storage
from app.storage.local import LocalStorage

DEFAULT_SOURCE_DB = f"sqlite:///{API_DIR / 'local.db'}"
DEFAULT_SOURCE_AUDIO = API_DIR / ".data" / "audio"


def describe(settings: Settings) -> str:
    url = make_url(db.normalise_url(settings.database_url))
    where = f"{url.drivername.split('+')[0]} at {url.host or url.database}" + (f":{url.port}" if url.port else "")
    return f"database {where}; audio storage: {settings.storage_backend}"


def same_database(a: str, b: str) -> bool:
    """True when both URLs point at the same database, whatever the driver name or password spelling."""

    def ident(url: str):
        u = make_url(db.normalise_url(url))
        return (u.drivername.split("+")[0], u.host, u.port, u.database, tuple(sorted(u.query.items())))

    return ident(a) == ident(b)


def confirm(args, action: str, settings: Settings) -> bool:
    print(f"Destination: {describe(settings)}")
    if args.yes:
        return True
    print(f"Dry run. Nothing was changed. Re-run with --yes to {action}.")
    return False


def _destination() -> Settings:
    settings = get_settings()
    db.init_db()
    return settings


def _print(report: Report) -> None:
    for line in report.lines():
        print(" ", line)


def cmd_seed(args) -> int:
    settings = _destination()
    what = "insert the nine rules and six agents" + (
        " and copy the processed test-set calls" if args.from_local else ""
    )
    if not confirm(args, what, settings):
        return 0
    with db.session_scope() as session:
        report = seed_reference_data(session)
        if args.from_local:
            report = _merge(report, _copy(session, args, only_test_set=True, redate_calls=True))
    _print(report)
    return 0


def _source(args) -> tuple[Session, LocalStorage]:
    src_engine = db.make_engine(args.source_url)
    return Session(src_engine), LocalStorage(args.source_audio)


def _copy(dst: Session, args, **kw) -> Report:
    src, src_storage = _source(args)
    with src:
        return copy_data(
            src, dst, src_storage=src_storage, dst_storage=get_storage(), replace=args.replace,
            progress=lambda name: print("  copied", name), **kw,
        )  # fmt: skip


def _merge(a: Report, b: Report) -> Report:
    for k, v in b.counts.items():
        a.add(k, v)
    a.notes += b.notes
    return a


def cmd_migrate(args) -> int:
    settings = _destination()
    if same_database(args.source_url, settings.database_url):
        print("The source and the destination are the same database.", file=sys.stderr)
        return 2
    if not confirm(args, "copy the local data", settings):
        return 0
    with db.session_scope() as session:
        seed_rules(session)
        report = _copy(session, args)
    _print(report)
    return 0


def cmd_reset(args) -> int:
    settings = _destination()
    if not confirm(args, "reset the demo to its seeded state", settings):
        return 0
    llm = None
    try:
        from app.detection.llm_judge import PROMPT_VERSION
        from app.services.llm import build_llm_service

        llm = build_llm_service(settings, PROMPT_VERSION)
    except Exception:  # without keys, swapped roles are reported instead of repaired
        pass
    with db.session_scope() as session:
        report = reset_demo(session, get_storage(), lambda s, c: analyse_call(s, c, llm))
    _print(report)
    return 0


def main(command: str, argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog=command, description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--yes", action="store_true", help="apply the changes (without it nothing is changed)")
    if command in ("seed", "migrate_local_to_supabase"):
        p.add_argument("--source-url", default=DEFAULT_SOURCE_DB, help="the local database to copy from")
        p.add_argument("--source-audio", type=Path, default=DEFAULT_SOURCE_AUDIO, help="the local audio folder")
        p.add_argument("--replace", action="store_true", help="overwrite calls that are already in the destination")
    if command == "seed":
        p.add_argument("--from-local", action="store_true", help="also copy the processed test-set calls")
    args = p.parse_args(argv)
    return {"seed": cmd_seed, "migrate_local_to_supabase": cmd_migrate, "reset_demo": cmd_reset}[command](args)
