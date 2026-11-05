"""Text normalisation used by every later step (plan.md Section 6.0).

NFC, remove zero-width characters, casefold, collapse whitespace; punctuation is stripped for matching only, and the
original text is kept for display. Devanagari vowel signs are marks, not letters, so they must survive stripping.
"""

from __future__ import annotations

import re
import unicodedata

_ZERO_WIDTH = re.compile("[​‌‍⁠﻿]")
_SPACES = re.compile(r"\s+")

# Letters, combining marks (Devanagari matras), numbers and spaces survive; punctuation and symbols are dropped.
_KEEP_CATEGORIES = ("L", "M", "N", "Z")

# A "word character" for boundaries: \w misses Devanagari vowel signs, so name the block explicitly
# (U+0900-U+0963 and U+0966-U+097F leave out the danda and double danda).
WORD_CLASS = r"[\wऀ-ॣ०-ॿ]"


def normalise(text: str) -> str:
    """NFC, zero-width removal, casefold, collapsed whitespace. Punctuation is kept."""
    text = unicodedata.normalize("NFC", text)
    text = _ZERO_WIDTH.sub("", text)
    return _SPACES.sub(" ", text.casefold()).strip()


def for_matching(text: str) -> str:
    """normalise() plus punctuation and symbols replaced by spaces, so "police." and "police" match alike."""
    text = normalise(text)
    out = [ch if unicodedata.category(ch)[0] in _KEEP_CATEGORIES else " " for ch in text]
    return _SPACES.sub(" ", "".join(out)).strip()


def has_devanagari(text: str) -> bool:
    return any("ऀ" <= ch <= "ॿ" for ch in text)
