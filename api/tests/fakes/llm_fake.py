"""A scripted LLM provider for tests: it returns canned responses and records every call."""

from __future__ import annotations

import json

from app.services.llm.base import LLMResponse


class FakeProvider:
    def __init__(self, name: str = "fake", model: str = "fake-1", responses: list | None = None) -> None:
        self.name, self.model = name, model
        self.responses = list(responses or [])
        self.calls: list[tuple[str, str]] = []
        self.on_call = None  # optional hook, called before each response

    def complete_json(self, system: str, user: str) -> LLMResponse:
        self.calls.append((system, user))
        if self.on_call:
            self.on_call()
        item = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(item, Exception):
            raise item
        text = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
        return LLMResponse(text, 400, 80)


def answer(violations: list[dict] | None = None, roles_look_correct: bool = True) -> dict:
    return {"roles_look_correct": roles_look_correct, "violations": violations or []}


def flag(rule: str, idx: int | None, quote: str | None, confidence: float = 0.9, why: str = "because") -> dict:
    return {"rule_code": rule, "segment_index": idx, "quote": quote, "explanation": why, "confidence": confidence}
