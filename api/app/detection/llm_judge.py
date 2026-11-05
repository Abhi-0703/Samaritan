"""Layer 2: the LLM judge (plan.md Section 6.3). One request per call, with evidence verification.

An LLM flag is accepted only if its quote really appears in the referenced segment (or one next to it), so the model
cannot invent evidence. Flags below 0.6 confidence are dropped and quotes are capped at 200 characters.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, Field
from rapidfuzz import fuzz

from app.detection.normalise import for_matching
from app.detection.types import Candidate, DSegment
from app.seed import rule_definitions
from app.services.llm.base import LLMUnavailable
from app.services.llm.limiter import estimate_tokens
from app.services.llm.service import LLMOutcome, LLMService

log = logging.getLogger("judge")

PROMPT_VERSION = "v1"  # bump on every change to the prompt, the examples or the user-message format
PROMPT_DIR = Path(__file__).resolve().parent / "prompts"

MIN_CONFIDENCE = 0.6
FUZZY_THRESHOLD = 85
MAX_QUOTE_CHARS = 200
WINDOW_TOKEN_LIMIT = 3500
WINDOW_SEGMENTS = 60
WINDOW_OVERLAP = 5
JUDGED_RULES = ["V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9"]  # V1 is never asked of the LLM


class JudgeViolation(BaseModel):
    rule_code: str
    segment_index: int | None = None
    quote: str | None = None
    explanation: str = ""
    confidence: float = Field(ge=0.0, le=1.0)


class JudgeResult(BaseModel):
    roles_look_correct: bool = True
    violations: list[JudgeViolation] = Field(default_factory=list)


@dataclass
class VerifiedFlag:
    rule_code: str
    segment_index: int | None
    quote: str | None
    explanation: str
    confidence: float


@dataclass
class JudgeOutcome:
    ok: bool  # False when no LLM could be reached: the caller keeps the Layer 1 results
    flags: list[VerifiedFlag] = field(default_factory=list)
    roles_look_correct: bool = True
    provider: str | None = None
    model: str | None = None
    fallback_used: bool = False
    cached: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0
    windows: int = 0
    rejected: list[tuple[str, str]] = field(default_factory=list)  # (summary, reason), for logs and failure analysis
    error: str | None = None


# ---- prompt ------------------------------------------------------------------------------------------------------


def _rule_block(d: dict, enabled: bool) -> str:
    note = "" if enabled else " (DISABLED: do not report)"
    return (
        f"{d['code']}: {d['name']}{note}\n"
        f"  Flag when: {' '.join(d['flag_when'].split())}\n"
        f"  Do NOT flag when: {' '.join(d['do_not_flag_when'].split())}"
    )


def build_system_prompt(enabled_rules: set[str] | None = None) -> str:
    defs = rule_definitions()
    blocks = [_rule_block(d, enabled_rules is None or d["code"] in enabled_rules or d["code"] == "V1") for d in defs]
    template = (PROMPT_DIR / "judge_system.txt").read_text(encoding="utf-8")
    return template.replace("{RULE_DEFINITIONS}", "\n".join(blocks))


def _clock(seconds: float) -> str:
    s = int(max(seconds, 0))
    return f"{s // 60:02d}:{s % 60:02d}"


def _line(s: DSegment) -> str:
    return f"[{s.index}] {s.speaker.upper()} ({_clock(s.start_s)}): {s.text}"


def split_windows(segments: list[DSegment]) -> list[list[DSegment]]:
    """One window for a normal call; ~60 segments with 5 overlapping for long ones (plan.md Section 6.3)."""
    if not segments or estimate_tokens("\n".join(_line(s) for s in segments)) <= WINDOW_TOKEN_LIMIT:
        return [segments]
    windows: list[list[DSegment]] = []
    step = WINDOW_SEGMENTS - WINDOW_OVERLAP
    start = 0
    while start < len(segments):
        windows.append(segments[start : start + WINDOW_SEGMENTS])
        if start + WINDOW_SEGMENTS >= len(segments):
            break
        start += step
    return windows


def build_user_message(
    window: list[DSegment],
    language: str,
    candidates: list[Candidate],
    enabled_rules: set[str] | None,
    window_no: int,
    window_total: int,
) -> str:
    rules = sorted((enabled_rules if enabled_rules is not None else set(JUDGED_RULES)) & set(JUDGED_RULES))
    indexes = {s.index for s in window}
    hints = [
        {"candidate_id": f"c{i}", "rule_code": c.rule_code, "segment_index": c.segment_index, "matched": c.matched_text}
        for i, c in enumerate((c for c in candidates if c.segment_index in indexes), start=1)
    ]
    return "\n".join(
        [
            f"Call language: {language}. Window {window_no} of {window_total}.",
            f"Enabled rules: {', '.join(rules) or 'none'}.",
            f"Evaluate V8 in this window: {'yes' if window_no == 1 else 'no'}.",
            "Transcript:",
            *(_line(s) for s in window),
            "Layer 1 hints (not verdicts):",
            json.dumps(hints, ensure_ascii=False),
        ]
    )


# ---- evidence verification ---------------------------------------------------------------------------------------


def snap_quote(quote: str, segment_text: str) -> str:
    """Prefer the segment's own spelling and casing so the web app can highlight the quote exactly."""
    m = re.search(re.escape(quote.strip()), segment_text, re.IGNORECASE)
    return segment_text[m.start() : m.end()] if m else quote.strip()


def verify_flags(
    violations: list[JudgeViolation],
    segments: list[DSegment],
    enabled_rules: set[str] | None,
    min_confidence: float = MIN_CONFIDENCE,
) -> tuple[list[VerifiedFlag], list[tuple[str, str]]]:
    by_index = {s.index: s for s in segments}
    roles_known = any(s.speaker == "agent" for s in segments)
    accepted: list[VerifiedFlag] = []
    rejected: list[tuple[str, str]] = []

    for v in violations:
        label = f"{v.rule_code}@{v.segment_index}"
        if v.rule_code not in JUDGED_RULES:
            rejected.append((label, "rule not judged by the LLM"))
            continue
        if enabled_rules is not None and v.rule_code not in enabled_rules:
            rejected.append((label, "rule disabled"))
            continue
        if v.confidence < min_confidence:
            rejected.append((label, f"confidence {v.confidence:.2f} below {min_confidence}"))
            continue
        if v.rule_code == "V8":  # absence: nothing to quote
            accepted.append(VerifiedFlag("V8", None, None, v.explanation, v.confidence))
            continue
        quote = (v.quote or "").strip()
        if v.segment_index is None or not quote:
            rejected.append((label, "no quote or segment"))
            continue
        if v.segment_index not in by_index:
            rejected.append((label, "segment index out of range"))
            continue
        needle = for_matching(quote)
        if len(needle) < 3:
            rejected.append((label, "quote too short"))
            continue
        best: tuple[float, int] | None = None
        for offset in (0, -1, 1):  # the referenced segment, then its neighbours
            j = v.segment_index + offset
            seg = by_index.get(j)
            if not seg:
                continue
            score = fuzz.partial_ratio(needle, for_matching(seg.text))
            if score >= FUZZY_THRESHOLD and (best is None or score > best[0]):
                best = (score, j)
        if best is None:
            rejected.append((label, "quote not found in the transcript"))  # an invented or paraphrased quote
            continue
        seg = by_index[best[1]]
        if roles_known and seg.speaker == "borrower":
            rejected.append((label, "quote is in borrower speech"))
            continue
        accepted.append(
            VerifiedFlag(
                v.rule_code, seg.index, snap_quote(quote, seg.text)[:MAX_QUOTE_CHARS], v.explanation, v.confidence
            )
        )
    return accepted, rejected


# ---- running the judge -------------------------------------------------------------------------------------------


def judge_call(
    llm: LLMService,
    segments: list[DSegment],
    language: str,
    candidates: list[Candidate],
    enabled_rules: set[str] | None = None,
) -> JudgeOutcome:
    system = build_system_prompt(enabled_rules)
    windows = split_windows(segments)
    out = JudgeOutcome(ok=True, windows=len(windows))
    roles_votes: list[bool] = []
    seen: set[tuple[str, int | None]] = set()
    for n, window in enumerate(windows, start=1):
        user = build_user_message(window, language, candidates, enabled_rules, n, len(windows))
        try:
            res: LLMOutcome[JudgeResult] = llm.complete(system, user, JudgeResult.model_validate)
        except LLMUnavailable as e:
            return JudgeOutcome(ok=False, windows=len(windows), error=str(e))
        out.provider, out.model = res.provider, res.model
        out.fallback_used = out.fallback_used or res.fallback_used
        out.cached = res.cached if n == 1 else (out.cached and res.cached)
        out.prompt_tokens += res.prompt_tokens or 0
        out.completion_tokens += res.completion_tokens or 0
        roles_votes.append(res.value.roles_look_correct)
        flags, rejected = verify_flags(res.value.violations, segments, enabled_rules)
        out.rejected.extend(rejected)
        for f in flags:
            if f.rule_code == "V8" and n > 1:
                continue
            key = (f.rule_code, f.segment_index)
            if key not in seen:  # windows overlap, so the same flag can come back twice
                seen.add(key)
                out.flags.append(f)
    out.roles_look_correct = sum(roles_votes) >= len(roles_votes) / 2 if roles_votes else True
    return out
