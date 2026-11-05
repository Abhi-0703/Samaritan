"""The metric maths on hand-made examples. Every expected number here was worked out by hand."""

from __future__ import annotations

import pytest

from app.evaluation.keys import AnswerKey, Expected
from app.evaluation.metrics import (
    Counts,
    Predicted,
    match_call,
    prf,
    role_mapping_accuracy,
    slices,
    summarise,
)


def key(*expected: tuple, clean: bool = False, name="c1", split="test", language="hinglish", noisy=False) -> AnswerKey:
    return AnswerKey(
        name, split, language, "11:20", False, noisy, clean,
        tuple(Expected(r, t, hint, "easy") for r, t, hint in expected),
    )  # fmt: skip


def P(rule, start=None, quote=None):
    return Predicted(rule, start, quote)


# ---- strict matching ---------------------------------------------------------------------------------------------


def test_a_flag_within_five_seconds_is_a_strict_hit():
    m = match_call(key(("V5", 30.0, "x")), [P("V5", 33.0)])
    assert m.per_rule["V5"] == Counts(1, 0, 0) and m.rule_level_tp == 1 and m.failures == []


def test_the_five_second_boundary_is_inclusive_and_beyond_it_is_a_miss():
    assert match_call(key(("V5", 30.0, None)), [P("V5", 35.0)]).per_rule["V5"] == Counts(1, 0, 0)
    assert match_call(key(("V5", 30.0, None)), [P("V5", 25.0)]).per_rule["V5"] == Counts(1, 0, 0)
    m = match_call(key(("V5", 30.0, "hint")), [P("V5", 35.1, "later words")])
    assert m.per_rule["V5"] == Counts(0, 1, 1)  # strict: both a miss and a false alarm
    assert m.rule_level_tp == 1  # but the rule itself was found
    assert {f.kind for f in m.failures} == {"fn", "fp"}
    fn = next(f for f in m.failures if f.kind == "fn")
    assert "expected near 30 s" in fn.note and "35 s" in fn.note and "hint" in fn.note


def test_v1_and_v8_match_on_the_rule_alone():
    m = match_call(key(("V1", None, None), ("V8", None, None)), [P("V1", None), P("V8", 0.0)])
    assert m.per_rule["V1"] == Counts(1, 0, 0) and m.per_rule["V8"] == Counts(1, 0, 0) and m.unlabelled == 0
    # even a labelled time would not matter for them
    far = match_call(key(("V8", 90.0, None)), [P("V8", 0.0)])
    assert far.per_rule["V8"] == Counts(1, 0, 0)


def test_an_unlabelled_time_matches_on_rule_and_is_counted():
    m = match_call(key(("V5", None, "x")), [P("V5", 77.0)])
    assert m.per_rule["V5"] == Counts(1, 0, 0) and m.unlabelled == 1


def test_wrong_rule_is_one_miss_and_one_false_alarm_and_no_rule_level_hit():
    m = match_call(key(("V4", 10.0, None)), [P("V5", 10.0)])
    assert m.per_rule["V4"] == Counts(0, 0, 1) and m.per_rule["V5"] == Counts(0, 1, 0) and m.rule_level_tp == 0


def test_flags_on_a_clean_call_are_false_alarms_with_a_clear_note():
    m = match_call(key(clean=True), [P("V2", 12.0, "you are a cheat")])
    assert m.per_rule["V2"] == Counts(0, 1, 0)
    assert m.failures[0].kind == "fp" and m.failures[0].note.startswith("Flagged on a call that should be clean.")
    assert "you are a cheat" in m.failures[0].note


def test_a_missed_violation_names_the_hint():
    m = match_call(key(("V6", 20.0, "bhai ko bata denge")), [])
    assert m.per_rule["V6"] == Counts(0, 0, 1) and m.failures[0].note.startswith("Missed (“bhai ko bata denge”).")


def test_each_prediction_is_used_once_and_the_nearest_pair_wins():
    # expected at 10 and 14, one prediction at 12: one hit, one miss
    m = match_call(key(("V5", 10.0, None), ("V5", 14.0, None)), [P("V5", 12.0)])
    assert m.per_rule["V5"] == Counts(1, 0, 1)
    # expected at 10 and 40 with predictions at 38 and 12: each takes its own
    m = match_call(key(("V5", 10.0, None), ("V5", 40.0, None)), [P("V5", 38.0), P("V5", 12.0)])
    assert m.per_rule["V5"] == Counts(2, 0, 0)
    # the nearer expectation claims a shared prediction, even when the farther one is listed first
    m = match_call(key(("V5", 14.0, None), ("V5", 10.0, None)), [P("V5", 11.0)])
    assert m.per_rule["V5"] == Counts(1, 0, 1) and m.failures[0].note.endswith("Expected near 14 s.")


def test_a_labelled_expectation_beats_an_unlabelled_one_for_a_shared_flag():
    m = match_call(key(("V5", None, None), ("V5", 30.0, None)), [P("V5", 31.0)])
    assert m.per_rule["V5"] == Counts(1, 0, 1) and m.unlabelled == 0  # the labelled one took the flag


def test_extra_flags_beyond_the_expected_count_are_false_alarms():
    m = match_call(key(("V5", 30.0, None)), [P("V5", 30.0), P("V5", 90.0, "other")])
    assert m.per_rule["V5"] == Counts(1, 1, 0) and m.failures[0].note.startswith("Not in the answer key.")


def test_a_flag_with_no_time_cannot_be_a_strict_hit_for_a_timed_rule():
    m = match_call(key(("V5", 30.0, None)), [P("V5", None)])
    assert m.per_rule["V5"] == Counts(0, 1, 1) and m.rule_level_tp == 1


# ---- precision, recall, F1 ---------------------------------------------------------------------------------------


def test_prf_by_hand():
    r = prf(Counts(tp=3, fp=1, fn=2))
    assert (r.precision, r.recall) == (0.75, 0.6) and r.f1 == pytest.approx(2 * 0.75 * 0.6 / 1.35)
    perfect = prf(Counts(4, 0, 0))
    assert (perfect.precision, perfect.recall, perfect.f1) == (1.0, 1.0, 1.0)


def test_undefined_ratios_are_zero_not_an_error():
    for c in (Counts(0, 0, 0), Counts(0, 3, 0), Counts(0, 0, 3)):
        r = prf(c)
        assert r.f1 == 0.0
    assert prf(Counts(0, 0, 3)).precision == 0.0 and prf(Counts(0, 3, 0)).recall == 0.0


# ---- summaries ---------------------------------------------------------------------------------------------------


def test_summary_over_several_calls():
    keys = {
        "a": key(("V5", 10.0, None), ("V1", None, None), name="a"),
        "b": key(("V4", 50.0, None), name="b"),
        "c": key(clean=True, name="c"),
        "d": key(clean=True, name="d"),
    }
    matches = [
        match_call(keys["a"], [P("V5", 12.0), P("V1")]),  # 2 strict hits
        match_call(keys["b"], [P("V4", 70.0)]),  # right rule, wrong moment: strict FP + FN, rule-level hit
        match_call(keys["c"], [P("V9", 5.0)]),  # false alarm on a clean call
        match_call(keys["d"], []),
    ]
    s = summarise(matches, keys)
    assert s.n_calls == 4
    assert (s.overall.precision, s.overall.recall) == (2 / 4, 2 / 3)  # tp 2, fp 2, fn 1
    assert s.rule_level_recall == 1.0  # all three expected violations were found by rule
    assert s.timestamp_accuracy == 2 / 3  # two of the three rule-level hits were also on time
    assert (s.clean_calls_flagged, s.clean_calls_total) == (1, 2)
    assert s.per_rule["V4"] == Counts(0, 1, 1) and s.per_rule["V9"] == Counts(0, 1, 0)


def test_summary_of_nothing_is_all_zero():
    s = summarise([], {})
    assert s.n_calls == 0 and s.overall.f1 == 0 and s.timestamp_accuracy == 0 and s.clean_calls_total == 0


def test_slices_follow_the_split_language_and_noise():
    keys = {
        "a": key(name="a", split="dev", language="hinglish", noisy=False),
        "b": key(name="b", split="test", language="marathi", noisy=True),
        "c": key(name="c", split="test", language="hinglish", noisy=True),
    }
    s = slices(keys)
    assert s["all"] == ["a", "b", "c"] and s["dev"] == ["a"] and s["test"] == ["b", "c"]
    assert s["hinglish"] == ["a", "c"] and s["marathi"] == ["b"]
    assert s["noisy"] == ["b", "c"] and s["not_noisy"] == ["a"]


def test_role_mapping_accuracy():
    assert role_mapping_accuracy([(1, 1), (2, 1), (1, 1), (None, 1)]) == 0.5
    assert role_mapping_accuracy([]) == 0.0
