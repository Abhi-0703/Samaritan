"""Idempotent seeding of reference data."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import load_yaml
from app.models import Rule


def rule_definitions() -> list[dict]:
    return load_yaml("rules.yaml")["rules"]


def seed_rules(session: Session) -> int:
    """Insert missing rules and refresh their text. The `enabled` switch is never overwritten."""
    existing = {r.code: r for r in session.scalars(select(Rule))}
    changed = 0
    for d in rule_definitions():
        row = existing.get(d["code"])
        values = {
            "name": d["name"],
            "description": " ".join(d["description"].split()),
            "rbi_reference": " ".join(d["rbi_reference"].split()),
            "severity": d["severity"],
            "detection": d["detection"],
        }
        if row is None:
            session.add(Rule(code=d["code"], enabled=True, **values))
            changed += 1
        else:
            for k, v in values.items():
                if getattr(row, k) != v:
                    setattr(row, k, v)
                    changed += 1
    session.flush()
    return changed
