"""Loading and compiling the YAML lexicons (plan.md Section 6.2). Edit the YAML; no code change is needed."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.detection.normalise import WORD_CLASS, for_matching, has_devanagari

LEXICON_DIR = Path(__file__).resolve().parent / "lexicons"
RULE_FILES = ["V2", "V3", "V4", "V5", "V6", "V7", "V9"]


@dataclass(frozen=True)
class Pattern:
    rule: str
    source: str  # the text or regex as written in the YAML
    regex: re.Pattern[str]
    lang: str  # hinglish | marathi | both
    strength: str  # strong | weak

    def applies_to(self, language: str) -> bool:
        return self.lang in ("both", language)


def compile_pattern(rule: str, entry: dict[str, Any], default_strength: str = "weak") -> Pattern:
    lang = entry.get("lang", "both")
    strength = entry.get("strength", default_strength)
    if lang not in ("hinglish", "marathi", "both") or strength not in ("strong", "weak"):
        raise ValueError(f"Bad lexicon entry in {rule}: {entry}")
    if "regex" in entry:
        source = entry["regex"]
        # Applied to punctuation-free text, so write your own word boundaries.
        regex = re.compile(source, re.IGNORECASE | re.UNICODE)
    elif "text" in entry:
        source = entry["text"]
        needle = re.escape(for_matching(source))
        # Latin words need a boundary on both sides ("hr" must not match "shruti").
        # Devanagari words take suffixes in Hindi and Marathi ("ऑफिसमध्ये"), so only the start is anchored.
        tail = "" if has_devanagari(source) else f"(?!{WORD_CLASS})"
        regex = re.compile(f"(?<!{WORD_CLASS}){needle}{tail}", re.UNICODE)
    else:
        raise ValueError(f"Lexicon entry needs `text` or `regex`: {entry}")
    return Pattern(rule, source, regex, lang, strength)


@lru_cache
def load_lexicons() -> dict[str, tuple[Pattern, ...]]:
    out: dict[str, tuple[Pattern, ...]] = {}
    for code in RULE_FILES:
        data = yaml.safe_load((LEXICON_DIR / f"{code.lower()}.yaml").read_text(encoding="utf-8"))
        if data["rule"] != code:
            raise ValueError(f"{code.lower()}.yaml declares rule {data['rule']}")
        out[code] = tuple(compile_pattern(code, e) for e in data["patterns"])
    return out


@lru_cache
def load_intro_patterns() -> tuple[Pattern, ...]:
    data = yaml.safe_load((LEXICON_DIR / "v8.yaml").read_text(encoding="utf-8"))
    return tuple(compile_pattern("V8", e) for e in data["intro_patterns"])
