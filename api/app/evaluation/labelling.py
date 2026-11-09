"""Time-labelling (plan.md Section 9.2): the person who made the recordings says which transcript segment holds each
expected violation, and which speaker is the agent. Answer keys get `approx_time_s` and `agent_speaker_id` from it.
The prompts are injected, so the logic is testable without a terminal."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from app.evaluation.metrics import RULE_ONLY


def _mmss(seconds: float) -> str:
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def start_of(segment: dict) -> float:
    """Gnani's raw segments say `start_time`; normalised ones say `start_s`."""
    return float(segment["start_time"] if "start_time" in segment else segment["start_s"])


def transcript_lines(segments: list[dict]) -> list[str]:
    return [
        f"[{i:>3}] {_mmss(start_of(s))}  speaker {s.get('speaker_id')}: {s['text']}" for i, s in enumerate(segments)
    ]


def label_call(
    key: dict, segments: list[dict], ask: Callable[[str], str], show: Callable[[str], None] = print
) -> tuple[dict, bool]:
    """Returns the updated key and whether anything changed. A blank answer skips that question."""
    key = json.loads(json.dumps(key))  # never mutate the caller's copy
    changed = False
    for line in transcript_lines(segments):
        show(line)

    speakers = sorted({s["speaker_id"] for s in segments if s.get("speaker_id") is not None})
    if key.get("agent_speaker_id") is None and speakers:
        while True:
            answer = ask(f"Which speaker is the agent? {speakers} (Enter to skip): ").strip()
            if not answer:
                break
            if answer.isdigit() and int(answer) in speakers:
                key["agent_speaker_id"] = int(answer)
                changed = True
                break
            show("Please answer with one of the speaker numbers shown.")

    for v in key["expected_violations"]:
        if v["approx_time_s"] is not None or v["rule_code"] in RULE_ONLY:
            continue
        hint = f' (hint: "{v["quote_hint"]}")' if v.get("quote_hint") else ""
        while True:
            answer = ask(f"{key['test_key']} {v['rule_code']}{hint}: which segment number? (Enter to skip): ").strip()
            if not answer:
                break
            if answer.isdigit() and int(answer) < len(segments):
                v["approx_time_s"] = round(start_of(segments[int(answer)]), 1)
                changed = True
                break
            show(f"Please answer with a number from 0 to {len(segments) - 1}.")
    return key, changed


def save_key(path: Path, key: dict) -> None:
    path.write_text(json.dumps(key, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
