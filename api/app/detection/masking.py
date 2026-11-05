"""PII masking (plan.md Section 6.1 step 2). Applied before anything is stored or sent to an LLM.

Replaces phone numbers, Aadhaar-like and account-like digit runs, PAN numbers and runs of spoken digit words
(English, Hindi in Latin and Devanagari, Marathi) with [PHONE], [AADHAAR], [ACCOUNT] and [PAN]. Ordinary amounts such as
"5500", "12,500" or "do hazaar paanch sau" are left alone.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from app.detection.normalise import for_matching

_PHONE = re.compile(r"(?<![\d])(?:\+?91[ -]?)?[6-9](?:[ -]?\d){9}(?![\d])")
_AADHAAR = re.compile(r"(?<!\d)\d{4}[ -]?\d{4}[ -]?\d{4}(?!\d)")
_PAN = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]{5}\d{4}[A-Za-z](?![A-Za-z0-9])")
_ACCOUNT = re.compile(r"(?<!\d)\d{9,}(?!\d)")
_TOKEN = re.compile(r"\S+")
_TRAILING_PUNCT = re.compile(r"[\s.,;:!?)\]\"'।॥]+$")

# Spoken digits. A word counts only inside a run, so ordinary "do" or "one" in a sentence is never masked.
DIGIT_WORDS: frozenset[str] = frozenset(
    {
        # English
        "zero", "oh", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
        # Hindi and Hinglish in Latin script, common spellings
        "shunya", "sunya", "ek", "do", "teen", "tin", "char", "chaar", "paanch", "panch", "paach", "chhe", "chhah",
        "chah", "chhey", "che", "chheh", "saat", "sat", "aath", "ath", "nau", "nao",
        # Marathi in Latin script
        "don", "saha", "naoo",
        # Devanagari: Hindi and Marathi
        "शून्य", "ज़ीरो", "जीरो", "एक", "दो", "दोन", "तीन", "चार", "पाँच", "पांच", "पाच", "छह", "छः", "छे", "सहा",
        "सात", "आठ", "नौ", "नऊ",
    }
)  # fmt: skip
# "do", "one" and "sat" are also ordinary words; requiring six in a row is what keeps them safe.
MIN_SPOKEN_RUN = 6


@dataclass
class MaskResult:
    text: str
    counts: Counter = field(default_factory=Counter)

    @property
    def changed(self) -> bool:
        return sum(self.counts.values()) > 0


def _mask_spoken_runs(text: str, counts: Counter) -> str:
    tokens = list(_TOKEN.finditer(text))
    is_digit = [for_matching(m.group()) in DIGIT_WORDS for m in tokens]
    out: list[str] = []
    cursor = 0
    i = 0
    while i < len(tokens):
        if not is_digit[i]:
            i += 1
            continue
        j = i
        while j < len(tokens) and is_digit[j]:
            j += 1
        if j - i >= MIN_SPOKEN_RUN:
            first, last = tokens[i], tokens[j - 1]
            tag = "[PHONE]" if j - i == 10 else "[AADHAAR]" if j - i == 12 else "[ACCOUNT]"
            tail = _TRAILING_PUNCT.search(last.group())
            out.append(text[cursor : first.start()])
            out.append(tag + (tail.group() if tail else ""))
            cursor = last.end()
            counts[tag] += 1
        i = j
    out.append(text[cursor:])
    return "".join(out)


def mask_pii(text: str) -> MaskResult:
    counts: Counter = Counter()

    def sub(tag: str, pattern: re.Pattern[str], value: str) -> str:
        def repl(_: re.Match[str]) -> str:
            counts[tag] += 1
            return tag

        return pattern.sub(repl, value)

    text = sub("[PHONE]", _PHONE, text)
    text = sub("[AADHAAR]", _AADHAAR, text)
    text = sub("[PAN]", _PAN, text)
    text = sub("[ACCOUNT]", _ACCOUNT, text)
    text = _mask_spoken_runs(text, counts)
    return MaskResult(text, counts)
