#!/usr/bin/env python3
"""Check that data/scripts/*.md and data/answer_keys/*.json agree, and write data/COVERAGE.md.

Usage:  python3 scripts/check_testset.py [--no-write]
Exit code 1 if any check fails. Standard library only (works on Python 3.9+).
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "data" / "scripts"
KEYS = ROOT / "data" / "answer_keys"
REPORT = ROOT / "data" / "COVERAGE.md"

N_CALLS = 30
MIN_WORDS, MAX_WORDS = 250, 450
RULES = [f"V{i}" for i in range(1, 10)]
MARKER = re.compile(r"\s*<<(V[2-9])>>\s*$")
HEADER = re.compile(r"^\[(.+)\]\s*$")
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
LOAN_REF = re.compile(r"^SF-PL-\d{6}$")


def parse_header(line: str) -> dict[str, str]:
    m = HEADER.match(line.strip())
    if not m:
        return {}
    out = {}
    for part in m.group(1).split("|"):
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip().lower()] = v.strip()
    return out


def parse_script(path: Path):
    """Return (header, spoken, translit_count) where spoken = [(speaker, text, marker_or_None)]."""
    header: dict[str, str] = {}
    spoken = []
    translit = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not header and line.startswith("["):
            header = parse_header(line)
            continue
        m = re.match(r"^(AGENT|BORROWER):\s*(.+)$", line)
        if m:
            text = m.group(2)
            mk = MARKER.search(text)
            marker = mk.group(1) if mk else None
            if mk:
                text = text[: mk.start()]
            spoken.append((m.group(1), text.strip(), marker))
        elif line.lstrip().startswith(">") and line.startswith("    "):
            translit += 1
    return header, spoken, translit


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().casefold()


def main() -> int:
    write = "--no-write" not in sys.argv
    errors: list[str] = []
    rows = []
    keys = {}
    for n in range(1, N_CALLS + 1):
        name = f"call_{n:02d}"
        sp, kp = SCRIPTS / f"{name}.md", KEYS / f"{name}.json"
        if not sp.exists():
            errors.append(f"{name}: script missing")
        if not kp.exists():
            errors.append(f"{name}: answer key missing")
        if not (sp.exists() and kp.exists()):
            continue
        key = json.loads(kp.read_text(encoding="utf-8"))
        keys[name] = key
        header, spoken, translit = parse_script(sp)
        e = lambda msg: errors.append(f"{name}: {msg}")  # noqa: E731

        if key.get("test_key") != name:
            e(f"test_key is {key.get('test_key')!r}")
        if key.get("split") not in ("dev", "test"):
            e("split must be dev or test")
        if key.get("language") not in ("hinglish", "marathi"):
            e("language must be hinglish or marathi")

        # header vs key
        if not header:
            e("missing [header] line")
        else:
            if header.get("time") != key.get("called_time_ist"):
                e(f"header time {header.get('time')} != key {key.get('called_time_ist')}")
            if header.get("language", "").lower() != key.get("language"):
                e("header language != key language")
            if (header.get("noise", "quiet").lower() != "quiet") != bool(key.get("noisy")):
                e("header noise != key noisy")
            if (header.get("requested time", "no").lower() == "yes") != bool(key.get("borrower_requested_time")):
                e("header 'Requested time' != key borrower_requested_time")
            if not LOAN_REF.match(header.get("loan", "")):
                e(f"bad loan ref {header.get('loan')!r}")

        # words
        words = sum(len(t.split()) for _, t, _ in spoken)
        if not MIN_WORDS <= words <= MAX_WORDS:
            e(f"{words} spoken words (need {MIN_WORDS}-{MAX_WORDS})")

        # script
        if not spoken or spoken[0][0] != "AGENT":
            e("call must open with an AGENT line")
        is_mr = key.get("language") == "marathi"
        for spk, text, _ in spoken:
            has_dev = bool(DEVANAGARI.search(text))
            if is_mr and not has_dev:
                e(f"Marathi line without Devanagari: {text[:40]!r}")
            if not is_mr and has_dev:
                e(f"Hinglish line contains Devanagari: {text[:40]!r}")
        if is_mr and translit != len(spoken):
            e(f"{translit} transliteration lines for {len(spoken)} spoken lines")
        if not is_mr and translit:
            e("Hinglish script should not have transliteration lines")

        # V1 consistency
        t = key.get("called_time_ist", "00:00")
        hh, mm = (int(x) for x in t.split(":"))
        minutes = hh * 60 + mm
        out_of_hours = minutes < 8 * 60 or minutes > 19 * 60
        exp = key.get("expected_violations", [])
        rules = [v["rule_code"] for v in exp]
        should_v1 = out_of_hours and not key.get("borrower_requested_time")
        if should_v1 != ("V1" in rules):
            e(f"V1 expectation inconsistent with time {t} / requested={key.get('borrower_requested_time')}")

        # clean / hard negative
        if bool(key.get("is_clean")) != (len(exp) == 0):
            e("is_clean does not match expected_violations")
        if key.get("hard_negative") and not key.get("is_clean"):
            e("hard_negative set on a call that has violations")

        # markers vs key
        marked = Counter(mk for _, _, mk in spoken if mk)
        expected_marked = Counter(r for r in rules if r != "V1")
        if marked != expected_marked:
            e(f"markers {dict(marked)} != expected rules {dict(expected_marked)}")
        for v in exp:
            if v["rule_code"] not in RULES:
                e(f"unknown rule {v['rule_code']}")
            if v.get("difficulty") not in ("easy", "hard"):
                e(f"{v['rule_code']}: difficulty must be easy or hard")
            if v.get("approx_time_s") is not None:
                e(f"{v['rule_code']}: approx_time_s must be null until label_times.py runs")
            hint = v.get("quote_hint")
            if v["rule_code"] in ("V1", "V8"):
                if hint is not None:
                    e(f"{v['rule_code']}: quote_hint must be null")
                if v["rule_code"] == "V8" and not (spoken and spoken[0][2] == "V8"):
                    e("V8 marker must be on the opening AGENT line")
            else:
                if not hint:
                    e(f"{v['rule_code']}: quote_hint missing")
                elif not any(mk == v["rule_code"] and norm(hint) in norm(text) for _, text, mk in spoken):
                    e(f"{v['rule_code']}: quote_hint {hint!r} not found in a line marked {v['rule_code']}")

        rows.append((name, key, words))

    # ---- coverage ----
    n = len(rows)
    viol_calls = [r for r in rows if not r[1]["is_clean"]]
    clean_calls = [r for r in rows if r[1]["is_clean"]]
    hard_neg = [r for r in clean_calls if r[1].get("hard_negative")]
    lang = Counter(r[1]["language"] for r in rows)
    noisy = sum(1 for r in rows if r[1]["noisy"])
    split = Counter(r[1]["split"] for r in rows)
    pos = {c: Counter() for c in RULES}  # rule -> counter of (split) / language
    pos_total, pos_dev, pos_test, pos_mr = Counter(), Counter(), Counter(), Counter()
    for _, k, _ in rows:
        for v in k["expected_violations"]:
            c = v["rule_code"]
            pos_total[c] += 1
            (pos_dev if k["split"] == "dev" else pos_test)[c] += 1
            if k["language"] == "marathi":
                pos_mr[c] += 1
    hard_cases = sum(1 for _, k, _ in rows for v in k["expected_violations"] if v["difficulty"] == "hard")
    instances = sum(pos_total.values())
    loans = Counter(parse_header(next((l for l in (SCRIPTS / f"{r[0]}.md").read_text(encoding="utf-8").splitlines() if l.startswith("[")), "")).get("loan") for r in rows)
    for loan, cnt in loans.items():
        if cnt > 1:
            errors.append(f"loan ref {loan} used {cnt} times")

    checks = [
        ("Calls", n, "30", n == N_CALLS),
        ("With at least 1 violation", len(viol_calls), "18", len(viol_calls) == 18),
        ("Fully compliant", len(clean_calls), "12", len(clean_calls) == 12),
        ("Hard negatives (clean)", len(hard_neg), ">= 4", len(hard_neg) >= 4),
        ("Hinglish", lang["hinglish"], "22", lang["hinglish"] == 22),
        ("Marathi", lang["marathi"], "8", lang["marathi"] == 8),
        ("Noisy recordings", noisy, "8", noisy == 8),
        ("dev split", split["dev"], "10", split["dev"] == 10),
        ("test split (held out)", split["test"], "20", split["test"] == 20),
        ("Violation instances", instances, "28", instances == 28),
    ]
    for c in RULES:
        want = 4 if c == "V1" else 3
        checks.append((f"{c} positives", pos_total[c], f">= {want}", pos_total[c] >= want))
        checks.append((f"{c} in dev", pos_dev[c], ">= 1", pos_dev[c] >= 1))
        checks.append((f"{c} in test", pos_test[c], ">= 2", pos_test[c] >= 2))
    for c in ("V2", "V4", "V5"):
        checks.append((f"{c} positives in Marathi", pos_mr[c], ">= 1", pos_mr[c] >= 1))
    checks.append(("Shortest script (spoken words)", min(r[2] for r in rows) if rows else 0, f"{MIN_WORDS}-{MAX_WORDS}", all(MIN_WORDS <= r[2] <= MAX_WORDS for r in rows)))
    for label, got, want, ok in checks:
        if not ok:
            errors.append(f"coverage: {label} is {got}, expected {want}")

    if write and rows:
        L = ["# Test-set coverage", "", "Generated by `scripts/check_testset.py`. Do not edit by hand.", ""]
        L += ["## Totals against plan.md Section 9.1", "", "| Check | Actual | Target | Result |", "|---|---|---|---|"]
        L += [f"| {a} | {b} | {c} | {'ok' if d else 'FAIL'} |" for a, b, c, d in checks]
        L += ["", f"Hard-difficulty violation instances: {hard_cases} of {instances}.", ""]
        L += ["## Calls", "", "| Call | Split | Language | Time (IST) | Noisy | Words | Expected violations | Note |", "|---|---|---|---|---|---|---|---|"]
        for name, k, w in rows:
            ev = ", ".join(f"{v['rule_code']}{'*' if v['difficulty'] == 'hard' else ''}" for v in k["expected_violations"]) or ("clean (hard negative)" if k.get("hard_negative") else "clean")
            L.append(f"| {name} | {k['split']} | {k['language']} | {k['called_time_ist']}{' (requested)' if k['borrower_requested_time'] else ''} | {'yes' if k['noisy'] else 'no'} | {w} | {ev} | {k.get('notes', '')} |")
        L += ["", "`*` = difficulty hard.", ""]
        REPORT.write_text("\n".join(L), encoding="utf-8")

    if errors:
        print(f"{len(errors)} problem(s):")
        for m in errors:
            print(" -", m)
        return 1
    print(f"OK: {n} scripts and keys agree; coverage report {'written' if write else 'not written'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
