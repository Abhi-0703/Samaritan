"""Answer keys: data/answer_keys/call_NN.json (plan.md Section 9.2, plus the optional fields in D-002 and D-023)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.config import API_DIR

REPO_DIR = API_DIR.parent
KEYS_DIR = REPO_DIR / "data" / "answer_keys"
SCRIPTS_DIR = REPO_DIR / "data" / "scripts"
AUDIO_DIR = REPO_DIR / "data" / "audio"
REPORTS_DIR = REPO_DIR / "eval" / "reports"


@dataclass(frozen=True)
class Expected:
    rule_code: str
    approx_time_s: float | None
    quote_hint: str | None
    difficulty: str


@dataclass(frozen=True)
class AnswerKey:
    test_key: str
    split: str  # dev | test
    language: str
    called_time_ist: str  # "HH:MM"
    borrower_requested_time: bool
    noisy: bool
    is_clean: bool
    expected: tuple[Expected, ...] = field(default_factory=tuple)
    hard_negative: bool = False
    agent_speaker_id: int | None = None  # human label from label_times.py; the role-mapping ground truth


def parse_key(data: dict) -> AnswerKey:
    return AnswerKey(
        test_key=data["test_key"],
        split=data["split"],
        language=data["language"],
        called_time_ist=data["called_time_ist"],
        borrower_requested_time=bool(data["borrower_requested_time"]),
        noisy=bool(data["noisy"]),
        is_clean=bool(data["is_clean"]),
        expected=tuple(
            Expected(v["rule_code"], v.get("approx_time_s"), v.get("quote_hint"), v.get("difficulty", "easy"))
            for v in data["expected_violations"]
        ),
        hard_negative=bool(data.get("hard_negative", False)),
        agent_speaker_id=data.get("agent_speaker_id"),
    )


def load_keys(directory: Path = KEYS_DIR) -> list[AnswerKey]:
    files = sorted(directory.glob("call_*.json"))
    if not files:
        raise FileNotFoundError(f"No answer keys found in {directory}.")
    return [parse_key(json.loads(f.read_text(encoding="utf-8"))) for f in files]


def key_path(test_key: str, directory: Path = KEYS_DIR) -> Path:
    return directory / f"{test_key}.json"
