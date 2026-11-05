"""Map Gnani's integer speaker ids to Agent and Borrower (plan.md Section 6.1 step 1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from app.detection.lexicon import Pattern, compile_pattern
from app.detection.normalise import for_matching

LEXICON_DIR = Path(__file__).resolve().parent / "lexicons"


@dataclass
class RoleMapping:
    agent_speaker_id: int | None
    mapping: dict[int, str] = field(default_factory=dict)  # speaker id -> "agent" | "borrower"
    scores: dict[int, int] = field(default_factory=dict)

    def label(self, speaker_id: int | None) -> str:
        if speaker_id is None or self.agent_speaker_id is None:
            return "unknown"
        return self.mapping.get(speaker_id, "unknown")


@lru_cache
def _role_patterns() -> tuple[tuple[Pattern, ...], tuple[Pattern, ...]]:
    data = yaml.safe_load((LEXICON_DIR / "roles.yaml").read_text(encoding="utf-8"))
    agent = tuple(compile_pattern("roles", p, default_strength="weak") for p in data["agent_patterns"])
    borrower = tuple(compile_pattern("roles", p, default_strength="weak") for p in data["borrower_patterns"])
    return agent, borrower


def _hits(patterns: tuple[Pattern, ...], text: str) -> int:
    return sum(1 for p in patterns if p.regex.search(text))


def map_roles(segments: list[tuple[int | None, float, str]]) -> RoleMapping:
    """`segments` is (speaker_id, start_s, text) in time order.

    The speaker with the highest agent score is the Agent (agent-lexicon hits minus borrower-lexicon hits). Ties go to
    whoever speaks first. With one speaker id or none, every segment stays "unknown". If diarization produced more than
    two ids, the best-scoring id is the Agent and the others are treated as Borrower.
    """
    ids = {sid for sid, _, _ in segments if sid is not None}
    if len(ids) < 2:
        return RoleMapping(None)
    agent_pats, borrower_pats = _role_patterns()
    scores = {sid: 0 for sid in ids}
    first_seen: dict[int, float] = {}
    for sid, start, text in segments:
        if sid is None:
            continue
        first_seen.setdefault(sid, start)
        norm = for_matching(text)
        scores[sid] += _hits(agent_pats, norm) - _hits(borrower_pats, norm)
    agent = max(ids, key=lambda s: (scores[s], -first_seen[s]))
    return RoleMapping(agent, {s: ("agent" if s == agent else "borrower") for s in ids}, scores)
