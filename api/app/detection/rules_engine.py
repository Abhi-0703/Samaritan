"""Layer 1: deterministic rules (plan.md Section 6.2). Fast and free.

V1 is decided here and never by the LLM. V8 is a presence check over the first 60 seconds. V2 to V7 and V9 are lexicon
matches on agent speech that the LLM later confirms or drops (strong = almost always a violation, weak = needs judging).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from functools import lru_cache

from app.config import load_yaml
from app.detection.lexicon import Pattern, load_intro_patterns, load_lexicons
from app.detection.normalise import WORD_CLASS, for_matching, has_devanagari
from app.detection.types import Candidate, DSegment

IST = timezone(timedelta(hours=5, minutes=30))  # India has no daylight saving, so a fixed offset is exact
WINDOW_START = time(8, 0, 0)
WINDOW_END = time(19, 0, 0)


def is_outside_permitted_hours(called_at: datetime, borrower_requested_time: bool) -> bool:
    """V1. 08:00:00 and 19:00:00 are allowed; a borrower-requested time is never a violation."""
    if borrower_requested_time:
        return False
    t = called_at.astimezone(IST).time()
    return t < WINDOW_START or t > WINDOW_END


@lru_cache
def _lender_regexes() -> tuple[re.Pattern[str], ...]:
    out = []
    for alias in load_yaml("workspace.yaml")["lender_aliases"]:
        needle = re.escape(for_matching(alias))
        tail = "" if has_devanagari(alias) else f"(?!{WORD_CLASS})"
        out.append(re.compile(f"(?<!{WORD_CLASS}){needle}{tail}", re.UNICODE))
    return tuple(out)


def _introduction_window_s() -> float:
    return float(load_yaml("workspace.yaml")["introduction_window_s"])


@dataclass
class IntroCheck:
    self_introduced: bool
    lender_named: bool

    @property
    def missing(self) -> bool:
        return not (self.self_introduced and self.lender_named)


def check_introduction(segments: list[DSegment], language: str) -> IntroCheck:
    """V8. The agent must state their own name AND the lender's name within the first 60 seconds.

    Both may appear in any agent segment inside the window. If roles are unknown, all speech in the window counts.
    """
    window = _introduction_window_s()
    agent_known = any(s.speaker == "agent" for s in segments)
    pool = [s for s in segments if s.start_s < window and (s.speaker == "agent" or not agent_known)]
    text = " ".join(for_matching(s.text) for s in pool)
    intro = any(p.regex.search(text) for p in load_intro_patterns() if p.applies_to(language))
    lender = any(r.search(text) for r in _lender_regexes())
    return IntroCheck(intro, lender)


def _match(patterns: tuple[Pattern, ...], text: str, language: str) -> tuple[str, str] | None:
    """Best match for one segment: a strong pattern beats a weak one, otherwise the first hit."""
    best: tuple[str, str] | None = None
    for p in patterns:
        if not p.applies_to(language):
            continue
        m = p.regex.search(text)
        if not m:
            continue
        if p.strength == "strong":
            return m.group(0).strip(), "strong"
        if best is None:
            best = (m.group(0).strip(), "weak")
    return best


def find_candidates(segments: list[DSegment], language: str, enabled_rules: set[str] | None = None) -> list[Candidate]:
    """V2 to V7 and V9: at most one candidate per (rule, segment), on agent speech (all speech if roles are unknown)."""
    lexicons = load_lexicons()
    agent_known = any(s.speaker == "agent" for s in segments)
    out: list[Candidate] = []
    for seg in segments:
        if agent_known and seg.speaker != "agent":
            continue
        text = for_matching(seg.text)
        if not text:
            continue
        for code, patterns in lexicons.items():
            if enabled_rules is not None and code not in enabled_rules:
                continue
            hit = _match(patterns, text, language)
            if hit:
                out.append(Candidate(code, seg.index, hit[0], hit[1]))  # type: ignore[arg-type]
    return out


@dataclass
class Layer1Result:
    v1_outside_hours: bool = False
    v8_missing_intro: bool = False
    candidates: list[Candidate] = field(default_factory=list)


def run_layer1(
    segments: list[DSegment],
    language: str,
    called_at: datetime,
    borrower_requested_time: bool,
    enabled_rules: set[str] | None = None,
) -> Layer1Result:
    def on(code: str) -> bool:
        return enabled_rules is None or code in enabled_rules

    return Layer1Result(
        v1_outside_hours=on("V1") and is_outside_permitted_hours(called_at, borrower_requested_time),
        v8_missing_intro=on("V8") and check_introduction(segments, language).missing,
        candidates=find_candidates(segments, language, enabled_rules),
    )
