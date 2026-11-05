"""Plain data types shared by the detection steps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Speaker = Literal["agent", "borrower", "unknown"]
Strength = Literal["strong", "weak"]


@dataclass
class DSegment:
    """A transcript segment as the detection steps see it. `text` is already masked."""

    index: int
    speaker: Speaker
    start_s: float
    end_s: float
    text: str


@dataclass(frozen=True)
class Candidate:
    """A Layer 1 hit: a keyword or phrase in agent speech that might break a rule."""

    rule_code: str
    segment_index: int
    matched_text: str
    strength: Strength
