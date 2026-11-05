from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from app import db
from app.detection.llm_judge import (
    PROMPT_VERSION,
    JudgeViolation,
    build_system_prompt,
    build_user_message,
    judge_call,
    snap_quote,
    split_windows,
    verify_flags,
)
from app.detection.merge import merge_flags, rules_only_flags
from app.detection.rules_engine import Layer1Result
from app.detection.types import Candidate, DSegment
from app.services.llm.base import LLMTransientError
from app.services.llm.cache import DbLlmCache
from app.services.llm.limiter import TokenLimiter
from app.services.llm.service import LLMService
from app.services.scoring import call_score, mean_score
from tests.fakes.llm_fake import FakeProvider, answer, flag

IST = timezone(timedelta(hours=5, minutes=30))
CALLED = datetime(2026, 11, 3, 12, 0, tzinfo=IST)


def seg(i: int, text: str, speaker: str = "agent") -> DSegment:
    return DSegment(i, speaker, i * 5.0, i * 5.0 + 4.0, text)  # type: ignore[arg-type]


def v(rule="V5", idx=1, quote="x", conf=0.9) -> JudgeViolation:
    return JudgeViolation(rule_code=rule, segment_index=idx, quote=quote, explanation="e", confidence=conf)


SEGS = [
    seg(0, "Namaste, main Rohit bol raha hoon Sahyog Finance se."),
    seg(1, "Haan ji boliye.", "borrower"),
    seg(2, "Kal tak nahi aaya toh main padosiyon ko bata dunga ki aap defaulter ho."),
    seg(3, "Arre aisa mat kijiye.", "borrower"),
    seg(4, "Theek hai, shukrawar tak payment kar dijiye."),
]


# ---- prompt ------------------------------------------------------------------------------------------------------


def test_system_prompt_has_all_nine_definitions_examples_and_rules_of_engagement():
    p = build_system_prompt()
    assert p.count("Flag when:") == 9 and p.count("Do NOT flag when:") == 9
    for code in [f"V{i}" for i in range(1, 10)]:
        assert f"{code}: " in p
    assert "Never report V1" in p and "VERBATIM" in p and "Devanagari" in p
    assert p.count("Transcript:") == 4  # four few-shot examples, including lawful-notice and compliant ones
    assert "legal notice" in p and '"violations": []' in p


def test_system_prompt_marks_disabled_rules():
    p = build_system_prompt(enabled_rules={"V2", "V4"})
    assert "V5: Public shaming or threat to inform others (DISABLED: do not report)" in p
    assert "V4: False legal threat\n" in p


def test_prompt_version_is_defined():
    assert PROMPT_VERSION


def test_user_message_format_and_hints():
    cands = [Candidate("V5", 2, "padosi", "weak"), Candidate("V4", 9, "police", "weak")]
    msg = build_user_message(SEGS, "hinglish", cands, {"V5", "V4", "V1"}, 1, 1)
    assert "[0] AGENT (00:00): Namaste" in msg and "[1] BORROWER (00:05): Haan ji boliye." in msg
    assert "Enabled rules: V4, V5." in msg and "Evaluate V8 in this window: yes" in msg
    hints = json.loads(msg.split("Layer 1 hints (not verdicts):\n")[1])
    assert hints == [
        {"candidate_id": "c1", "rule_code": "V5", "segment_index": 2, "matched": "padosi"}
    ]  # c4's segment is not in the window


def test_short_calls_are_one_window_and_long_calls_overlap():
    assert len(split_windows(SEGS)) == 1
    long = [seg(i, "Sir aapki EMI pending hai, kab tak ho payega, batayiye " * 4) for i in range(200)]
    wins = split_windows(long)
    assert len(wins) > 1 and all(len(w) <= 60 for w in wins)
    assert wins[1][0].index == 55  # 5 segments overlap
    assert wins[-1][-1].index == 199
    assert {s.index for w in wins for s in w} == set(range(200))
    assert "Evaluate V8 in this window: no" in build_user_message(wins[1], "hinglish", [], None, 2, len(wins))


# ---- evidence verification ---------------------------------------------------------------------------------------


def verified(violations, segs=SEGS, enabled=None):
    return verify_flags(violations, segs, enabled)


def test_exact_quote_is_accepted_and_snapped_to_the_segments_own_spelling():
    segs = [seg(0, "Main Padosiyon ko BATA dunga")]
    ok, rej = verified([v(idx=0, quote="padosiyon ko bata dunga")], segs)
    assert not rej and ok[0].quote == "Padosiyon ko BATA dunga" and ok[0].segment_index == 0


def test_small_spelling_differences_are_tolerated():
    ok, rej = verified([v(idx=2, quote="main padosiyon ko bata dunga ki aap defaulter ho")])
    assert ok and not rej


def test_paraphrase_and_invented_quote_are_rejected():
    ok, rej = verified([v(idx=2, quote="main aapke bacchon ko school se utha lunga")])
    assert not ok and rej[0][1] == "quote not found in the transcript"


def test_quote_in_a_neighbouring_segment_is_accepted_and_the_index_corrected():
    ok, _ = verified([v(idx=3, quote="main padosiyon ko bata dunga")])  # idx 3 is borrower; the quote is in segment 2
    assert ok and ok[0].segment_index == 2


def test_quote_two_segments_away_is_rejected():
    _, rej = verified([v(idx=4, quote="main padosiyon ko bata dunga")])
    assert rej and rej[0][1] == "quote not found in the transcript"


def test_low_confidence_is_dropped():
    ok, rej = verified([v(idx=2, quote="padosiyon ko bata dunga", conf=0.59)])
    assert not ok and "below" in rej[0][1]
    assert verified([v(idx=2, quote="padosiyon ko bata dunga", conf=0.6)])[0]


def test_quote_is_capped_at_200_characters():
    long_text = "Dekhiye " + "padosiyon ko bata dunga " * 20
    ok, _ = verified([v(idx=0, quote=long_text.strip())], [seg(0, long_text)])
    assert ok and len(ok[0].quote) == 200


def test_v8_needs_no_quote_but_other_rules_do():
    ok, _ = verified([v("V8", None, None, 0.8)])
    assert ok[0].rule_code == "V8" and ok[0].segment_index is None
    _, rej = verified([v("V5", None, None)])
    assert rej[0][1] == "no quote or segment"
    _, rej = verified([v("V5", 2, "")])
    assert rej[0][1] == "no quote or segment"


def test_v1_from_the_llm_is_ignored_and_unknown_rules_too():
    _, rej = verified([v("V1", None, None), v("V99", 2, "padosiyon ko bata dunga")])
    assert [r[1] for r in rej] == ["rule not judged by the LLM"] * 2


def test_disabled_rules_are_rejected():
    _, rej = verified([v("V5", 2, "padosiyon ko bata dunga")], enabled={"V2"})
    assert rej[0][1] == "rule disabled"


def test_borrower_speech_is_not_a_violation_when_roles_are_known():
    segs = [seg(0, "Main Rohit bol raha hoon Sahyog Finance se"), seg(1, "Tum chor ho", "borrower")]
    _, rej = verified([v("V2", 1, "Tum chor ho")], segs)
    assert rej[0][1] == "quote is in borrower speech"
    unknown = [seg(0, "Hello", "unknown"), seg(1, "Tum chor ho", "unknown")]
    assert verified([v("V2", 1, "Tum chor ho")], unknown)[0]


def test_out_of_range_index_and_tiny_quotes_are_rejected():
    assert verified([v(idx=99, quote="padosiyon ko bata dunga")])[1][0][1] == "segment index out of range"
    assert verified([v(idx=2, quote="ko")])[1][0][1] == "quote too short"


def test_devanagari_quote_is_verified():
    segs = [seg(0, "आम्ही तुमच्या ऑफिसमध्ये सगळ्यांना सांगू की तुम्ही कर्ज बुडवताय.")]
    ok, rej = verified([v(idx=0, quote="ऑफिसमध्ये सगळ्यांना सांगू")], segs)
    assert ok and not rej and ok[0].quote == "ऑफिसमध्ये सगळ्यांना सांगू"


def test_snap_quote_falls_back_to_the_models_text():
    assert snap_quote("  hello there ", "completely different") == "hello there"


# ---- judge_call --------------------------------------------------------------------------------------------------


def service(provider, session=None, fallback=None):
    cache = DbLlmCache(db.session_scope) if session is not None else None
    limiters = {p.name: TokenLimiter(1000, 10_000_000, sleep=lambda s: None) for p in (provider, fallback) if p}
    return LLMService(provider, fallback, limiters, cache, PROMPT_VERSION, sleep=lambda s: None)


def test_judge_returns_verified_flags_and_usage():
    p = FakeProvider(responses=[answer([flag("V5", 2, "padosiyon ko bata dunga")])])
    out = judge_call(service(p), SEGS, "hinglish", [], None)
    assert out.ok and [(f.rule_code, f.segment_index) for f in out.flags] == [("V5", 2)]
    assert out.provider == "fake" and out.prompt_tokens == 400 and out.windows == 1 and out.roles_look_correct


def test_judge_discards_invented_evidence_and_records_why():
    p = FakeProvider(responses=[answer([flag("V4", 2, "kal police aa jayegi")])])
    out = judge_call(service(p), SEGS, "hinglish", [], None)
    assert out.ok and out.flags == [] and out.rejected[0][1] == "quote not found in the transcript"


def test_judge_sends_the_candidates_as_hints_and_the_system_prompt():
    p = FakeProvider(responses=[answer()])
    judge_call(service(p), SEGS, "hinglish", [Candidate("V5", 2, "padosi", "weak")], None)
    system, user = p.calls[0]
    assert "Flag when:" in system and '"matched": "padosi"' in user


def test_judge_reports_unavailable_llm_without_raising():
    p = FakeProvider(responses=[LLMTransientError("down")])
    out = judge_call(service(p), SEGS, "hinglish", [], None)
    assert not out.ok and out.flags == [] and out.error


def test_judge_roles_look_correct_false_is_passed_through():
    p = FakeProvider(responses=[answer(roles_look_correct=False)])
    assert judge_call(service(p), SEGS, "hinglish", [], None).roles_look_correct is False


def test_judge_uses_the_cache(session):
    p = FakeProvider(responses=[answer([flag("V5", 2, "padosiyon ko bata dunga")])])
    svc = service(p, session)
    judge_call(svc, SEGS, "hinglish", [], None)
    second = judge_call(svc, SEGS, "hinglish", [], None)
    assert len(p.calls) == 1 and second.cached and second.flags


def test_long_calls_use_several_requests_dedupe_the_overlap_and_take_v8_from_window_one_only():
    long = [seg(i, "Sir aapki EMI pending hai, kab tak ho payega, batayiye " * 4) for i in range(120)]
    long[57] = seg(57, "Main padosiyon ko bata dunga ki aap defaulter ho " * 3)  # inside the overlap of windows 1 and 2
    reply = answer([flag("V5", 57, "Main padosiyon ko bata dunga ki aap defaulter ho"), flag("V8", None, None, 0.8)])
    p = FakeProvider(responses=[reply])
    out = judge_call(service(p), long, "hinglish", [], None)
    assert out.windows == len(p.calls) > 1
    assert [f.rule_code for f in out.flags].count("V5") == 1  # same flag from both windows, kept once
    assert [f.rule_code for f in out.flags].count("V8") == 1  # only window 1 may decide V8


# ---- merge -------------------------------------------------------------------------------------------------------


def merged(judge, layer1, segs=SEGS, enabled=None, called=CALLED):
    return merge_flags(segs, layer1, judge, called, enabled)


def judge_with(*flags, ok=True):
    from app.detection.llm_judge import JudgeOutcome, VerifiedFlag

    return JudgeOutcome(ok=ok, flags=[VerifiedFlag(*f) for f in flags])


def test_candidate_confirmed_by_the_llm_is_both_and_llm_only_is_llm():
    layer1 = Layer1Result(candidates=[Candidate("V5", 2, "padosi", "weak")])
    judge = judge_with(
        ("V5", 2, "padosiyon ko bata dunga", "threat", 0.9), ("V9", 4, "payment kar dijiye", "pressure", 0.7)
    )
    out = {f.rule_code: f for f in merged(judge, layer1)}
    assert out["V5"].detected_by == "both" and out["V5"].start_s == 10.0 and out["V5"].quote
    assert out["V9"].detected_by == "llm"


def test_adjacent_segment_counts_as_confirmation():
    layer1 = Layer1Result(candidates=[Candidate("V5", 3, "x", "weak")])
    judge = judge_with(("V5", 2, "q", "e", 0.9))
    assert merged(judge, layer1)[0].detected_by == "both"


def test_candidate_the_llm_did_not_return_is_dropped():
    layer1 = Layer1Result(candidates=[Candidate("V4", 2, "police", "strong")])
    assert merged(judge_with(), layer1) == []


def test_v1_is_metadata_and_never_depends_on_the_llm():
    late = datetime(2026, 11, 3, 21, 40, tzinfo=IST)
    out = merged(judge_with(), Layer1Result(v1_outside_hours=True), called=late)
    assert [(f.rule_code, f.detected_by, f.segment_index, f.start_s, f.confidence) for f in out] == [
        ("V1", "metadata", None, None, 1.0)
    ]
    assert "21:40 IST" in out[0].explanation


def test_v8_follows_the_llm_when_available():
    layer1 = Layer1Result(v8_missing_intro=True)
    assert merged(judge_with(), layer1) == []  # the LLM saw an introduction (or judged it fine): Layer 1 loses
    both = merged(judge_with(("V8", None, None, "no intro", 0.8)), layer1)[0]
    assert (both.rule_code, both.detected_by, both.start_s, both.quote) == ("V8", "both", 0.0, None)
    llm_only = merged(judge_with(("V8", None, None, "no intro", 0.8)), Layer1Result())[0]
    assert llm_only.detected_by == "llm"


def test_without_an_llm_layer1_results_are_kept_including_weak_and_v8():
    layer1 = Layer1Result(
        v8_missing_intro=True, candidates=[Candidate("V4", 2, "police", "weak"), Candidate("V5", 2, "padosi", "strong")]
    )
    for judge in (None, judge_with(ok=False)):
        out = merged(judge, layer1)
        assert {f.rule_code for f in out} == {"V4", "V5", "V8"} and all(f.detected_by == "rules" for f in out)
        assert {f.rule_code: f.confidence for f in out}["V5"] > {f.rule_code: f.confidence for f in out}["V4"]


def test_rules_only_is_every_layer1_hit():
    layer1 = Layer1Result(v1_outside_hours=True, candidates=[Candidate("V9", 4, "warna", "weak")])
    out = rules_only_flags(SEGS, layer1, datetime(2026, 11, 3, 7, 0, tzinfo=IST))
    assert {f.rule_code for f in out} == {"V1", "V9"}


def test_same_rule_on_adjacent_segments_collapses_to_one_violation():
    judge = judge_with(("V4", 2, "a police", "e", 0.7), ("V4", 3, "b police", "e", 0.95), ("V4", 4, "c", "e", 0.6))
    out = [f for f in merged(judge, Layer1Result()) if f.rule_code == "V4"]
    assert len(out) == 1 and out[0].confidence == 0.95


def test_disabled_rules_are_filtered_out():
    judge = judge_with(("V5", 2, "q", "e", 0.9), ("V2", 2, "q", "e", 0.9))
    assert [f.rule_code for f in merged(judge, Layer1Result(), enabled={"V2"})] == ["V2"]


def test_flags_are_ordered_by_time_with_metadata_first():
    judge = judge_with(("V9", 4, "q", "e", 0.9), ("V5", 2, "q", "e", 0.9))
    out = merged(judge, Layer1Result(v1_outside_hours=True), called=datetime(2026, 11, 3, 21, 0, tzinfo=IST))
    assert [f.rule_code for f in out] == ["V1", "V5", "V9"]


# ---- scoring -----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sev,expected",
    [
        ([], 100),
        (["critical"], 70),
        (["high"], 85),
        (["medium"], 95),
        (["critical", "high", "medium"], 50),
        (["critical"] * 4, 0),
        (["critical"] * 10, 0),
    ],
)
def test_call_score(sev, expected):
    assert call_score(sev) == expected


def test_mean_score_ignores_missing():
    assert mean_score([100, 50, None]) == 75 and mean_score([None]) is None and mean_score([]) is None
