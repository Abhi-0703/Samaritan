"""Scores (plan.md Section 5.3). Weights live in app/config/scoring.yaml."""

from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache

from app.config import load_yaml


@lru_cache
def _weights() -> tuple[float, float, dict[str, float]]:
    d = load_yaml("scoring.yaml")
    return float(d["base"]), float(d["floor"]), {k: float(v) for k, v in d["deductions"].items()}


def call_score(severities: Iterable[str]) -> float:
    """Start at 100; critical -30, high -15, medium -5 per violation; never below 0."""
    base, floor, deductions = _weights()
    return max(floor, base - sum(deductions[s] for s in severities))


def mean_score(scores: Iterable[float | None]) -> float | None:
    values = [s for s in scores if s is not None]
    return sum(values) / len(values) if values else None
