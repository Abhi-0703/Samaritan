"""Merge Layer 1 and Layer 2 into the final flags (plan.md Section 6.4).

`rules_plus_llm`: the LLM has the final say on keyword candidates. A candidate it confirms becomes one violation with
detected_by "both"; an LLM-only flag is "llm"; a candidate the LLM did not return is dropped. V1 is always "metadata".
V8 follows the LLM when one was reachable, otherwise Layer 1. If no LLM was reachable, every Layer 1 hit is kept.

`rules_only` (the baseline on the Accuracy page): every Layer 1 hit, strong and weak, with no LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.detection.llm_judge import JudgeOutcome
from app.detection.rules_engine import IST, Layer1Result
from app.detection.types import DSegment

STRONG_CONFIDENCE = 0.85
WEAK_CONFIDENCE = 0.55
V8_EXPLANATION = "The agent did not state both their own name and the lender's name in the first 60 seconds."


@dataclass
class MergedFlag:
    rule_code: str
    segment_index: int | None
    quote: str | None
    start_s: float | None
    explanation: str
    confidence: float
    detected_by: str  # rules | llm | both | metadata


def _v1_flag(called_at: datetime) -> MergedFlag:
    hhmm = called_at.astimezone(IST).strftime("%H:%M")
    return MergedFlag(
        "V1", None, None, None,
        f"The call started at {hhmm} IST, outside the permitted window of 08:00 to 19:00, "
        "and the borrower did not ask for that time.",
        1.0, "metadata",
    )  # fmt: skip


def _layer1_flags(layer1: Layer1Result, segments: list[DSegment]) -> list[MergedFlag]:
    by_index = {s.index: s for s in segments}
    flags = []
    for c in layer1.candidates:
        seg = by_index[c.segment_index]
        flags.append(
            MergedFlag(
                c.rule_code, seg.index, seg.text[:200], seg.start_s,
                f"The agent's words matched '{c.matched_text}' in a keyword rule; no language-model check was made.",
                STRONG_CONFIDENCE if c.strength == "strong" else WEAK_CONFIDENCE, "rules",
            )
        )  # fmt: skip
    return flags


def _collapse_adjacent(flags: list[MergedFlag]) -> list[MergedFlag]:
    """The same rule flagged on neighbouring segments is one violation: keep the most confident (preferring `both`)."""
    out: list[MergedFlag] = []
    for f in sorted(flags, key=lambda x: (x.rule_code, x.segment_index if x.segment_index is not None else -1)):
        prev = out[-1] if out else None
        if (
            prev
            and prev.rule_code == f.rule_code
            and prev.segment_index is not None
            and f.segment_index is not None
            and f.segment_index - prev.segment_index <= 1
        ):
            better = (
                f if (f.detected_by == "both", f.confidence) > (prev.detected_by == "both", prev.confidence) else prev
            )
            out[-1] = better
        else:
            out.append(f)
    return out


def _order(flags: list[MergedFlag]) -> list[MergedFlag]:
    return sorted(flags, key=lambda f: (-1 if f.start_s is None else f.start_s, f.rule_code))


def rules_only_flags(
    segments: list[DSegment], layer1: Layer1Result, called_at: datetime, enabled_rules: set[str] | None = None
) -> list[MergedFlag]:
    flags = _layer1_flags(layer1, segments)
    if layer1.v1_outside_hours:
        flags.append(_v1_flag(called_at))
    if layer1.v8_missing_intro:
        flags.append(MergedFlag("V8", None, None, 0.0, V8_EXPLANATION, WEAK_CONFIDENCE, "rules"))
    return _order(_filter(_collapse_adjacent(flags), enabled_rules))


def merge_flags(
    segments: list[DSegment],
    layer1: Layer1Result,
    judge: JudgeOutcome | None,
    called_at: datetime,
    enabled_rules: set[str] | None = None,
) -> list[MergedFlag]:
    if judge is None or not judge.ok:
        return rules_only_flags(segments, layer1, called_at, enabled_rules)

    by_index = {s.index: s for s in segments}
    flags: list[MergedFlag] = []
    if layer1.v1_outside_hours:
        flags.append(_v1_flag(called_at))

    for f in judge.flags:
        if f.rule_code == "V8":
            continue
        confirmed = any(
            c.rule_code == f.rule_code and f.segment_index is not None and abs(c.segment_index - f.segment_index) <= 1
            for c in layer1.candidates
        )
        seg = by_index[f.segment_index] if f.segment_index is not None else None
        flags.append(
            MergedFlag(
                f.rule_code, f.segment_index, f.quote, seg.start_s if seg else None,
                f.explanation, f.confidence, "both" if confirmed else "llm",
            )
        )  # fmt: skip

    v8 = next((f for f in judge.flags if f.rule_code == "V8"), None)
    if v8:  # the LLM's decision wins; Layer 1 agreeing makes it "both"
        flags.append(
            MergedFlag("V8", None, None, 0.0, v8.explanation or V8_EXPLANATION, v8.confidence,
                       "both" if layer1.v8_missing_intro else "llm")
        )  # fmt: skip
    return _order(_filter(_collapse_adjacent(flags), enabled_rules))


def _filter(flags: list[MergedFlag], enabled_rules: set[str] | None) -> list[MergedFlag]:
    return flags if enabled_rules is None else [f for f in flags if f.rule_code in enabled_rules]
