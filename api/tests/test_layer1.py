from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.detection.masking import mask_pii
from app.detection.roles import map_roles
from app.detection.rules_engine import (
    check_introduction,
    find_candidates,
    is_outside_permitted_hours,
    run_layer1,
)
from app.detection.types import DSegment

IST = timezone(timedelta(hours=5, minutes=30))


def seg(i: int, text: str, speaker: str = "agent", start: float | None = None) -> DSegment:
    s = i * 5.0 if start is None else start
    return DSegment(i, speaker, s, s + 4.0, text)  # type: ignore[arg-type]


def rules_hit(text: str, language: str = "hinglish", speaker: str = "agent") -> dict[str, str]:
    return {c.rule_code: c.strength for c in find_candidates([seg(0, text, speaker)], language)}


# ---- V1 ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "hh,mm,ss,expected",
    [
        (7, 59, 59, True),
        (8, 0, 0, False),
        (12, 0, 0, False),
        (19, 0, 0, False),
        (19, 0, 1, True),
        (21, 40, 0, True),
        (0, 5, 0, True),
    ],
)
def test_v1_window_boundaries_in_ist(hh, mm, ss, expected):
    assert is_outside_permitted_hours(datetime(2026, 11, 3, hh, mm, ss, tzinfo=IST), False) is expected


def test_v1_converts_from_utc_to_ist():
    # 14:30 UTC is 20:00 IST: outside hours. 03:00 UTC is 08:30 IST: inside.
    assert is_outside_permitted_hours(datetime(2026, 11, 3, 14, 30, tzinfo=UTC), False)
    assert not is_outside_permitted_hours(datetime(2026, 11, 3, 3, 0, tzinfo=UTC), False)


def test_v1_borrower_requested_time_is_never_a_violation():
    assert not is_outside_permitted_hours(datetime(2026, 11, 3, 20, 30, tzinfo=IST), True)


# ---- V8 ----------------------------------------------------------------------------------------------------------


def test_v8_passes_with_name_and_lender_hinglish():
    segs = [seg(0, "Namaste, main Rohit Patil bol raha hoon Sahyog Finance se.")]
    assert not check_introduction(segs, "hinglish").missing


def test_v8_passes_when_name_and_lender_are_in_different_segments():
    segs = [seg(0, "Hello, mera naam Imran hai."), seg(1, "Sahyog Finance ki taraf se call hai.", start=20)]
    assert not check_introduction(segs, "hinglish").missing


def test_v8_passes_in_marathi_devanagari():
    segs = [seg(0, "नमस्कार, मी रोहित पाटील बोलतोय सहयोग फायनान्स मधून.")]
    assert not check_introduction(segs, "marathi").missing


def test_v8_passes_with_latin_lender_in_marathi_call():
    segs = [seg(0, "नमस्कार, मी स्नेहा कुलकर्णी बोलतेय Sahyog Finance कडून.")]
    assert not check_introduction(segs, "marathi").missing


@pytest.mark.parametrize(
    "text",
    [
        "Haan hello, Dinesh Bhosale bol rahe ho? Loan ke baare mein baat karni hai.",  # no name, no lender
        "Namaste, main Rohit bol raha hoon.",  # name but no lender
        "Sahyog Finance se call hai, aapki EMI pending hai.",  # lender but no name
    ],
)
def test_v8_fails_without_both_name_and_lender(text):
    assert check_introduction([seg(0, text)], "hinglish").missing


def test_v8_ignores_an_introduction_after_60_seconds():
    segs = [seg(0, "EMI pending hai."), seg(1, "Main Rohit bol raha hoon Sahyog Finance se.", start=75)]
    assert check_introduction(segs, "hinglish").missing


def test_v8_ignores_borrower_speech_when_roles_are_known():
    segs = [
        seg(0, "Haan boliye.", "agent"),
        seg(1, "Main Anil bol raha hoon Sahyog Finance mein kaam karta hoon", "borrower"),
    ]
    assert check_introduction(segs, "hinglish").missing


def test_v8_uses_all_speech_when_roles_are_unknown():
    segs = [seg(0, "Namaste main Rohit bol raha hoon Sahyog Finance se", "unknown")]
    assert not check_introduction(segs, "hinglish").missing


# ---- V2 to V7, V9 lexicon matching -------------------------------------------------------------------------------


def test_strong_and_weak_strengths():
    assert rules_hit("Tum chor ho, loan lekar bhaagne wale log hote ho") == {"V2": "weak"}
    assert rules_hit("Tu madarchod hai")["V2"] == "strong"
    assert rules_hit("Kal police aa jayegi aur jail bhej denge")["V4"] == "strong"
    assert rules_hit("Police ko inform kar sakte hain")["V4"] == "weak"


def test_devanagari_hindi_and_marathi():
    assert rules_hit("कल पुलिस आएगी और जेल भेज देंगे")["V4"] == "strong"
    assert rules_hit("उद्या पोलीस तुमच्या दारात येतील आणि तुम्हाला तुरुंगात जावं लागेल", "marathi")["V4"] == "strong"
    assert rules_hit("आम्ही तुमच्या ऑफिसमध्ये सगळ्यांना सांगू", "marathi")["V5"] == "strong"  # needs prefix matching
    assert rules_hit("आत्ताच्या आत्ता पैसे भरा, नाहीतर ही शेवटची वेळ आहे", "marathi")["V9"] == "strong"


def test_v5_threat_to_inform_others():
    assert rules_hit("Main padosiyon ko bata dunga ki aap defaulter ho")["V5"] == "strong"
    assert rules_hit("society mein sabko pata chal jayega")["V5"] == "strong"


def test_v7_impersonation():
    assert rules_hit("Main high court ka advocate bol raha hoon")["V7"] == "strong"
    assert rules_hit("Main court se bol raha hoon")["V7"] == "strong"
    assert rules_hit("Main RBI ke recovery cell se bol raha hoon")["V7"] == "strong"
    assert rules_hit("Legal department se baat kar rahe hain")["V7"] == "weak"


def test_v3_force():
    assert rules_hit("Kal tak nahi aaya toh haath-pair tod denge")["V3"] == "strong"
    assert rules_hit("Hum ghar aake baat karenge")["V3"] == "weak"
    assert rules_hit("recovery wale bhej dunga tere ghar pe")["V3"] == "strong"


def test_v9_pressure():
    assert rules_hit("Abhi ke abhi payment karo, warna ye aakhri mauka hai")["V9"] == "strong"
    assert rules_hit("Please aaj hi payment kar dijiye")["V9"] == "weak"


def test_punctuation_and_case_do_not_matter():
    assert "V4" in rules_hit("POLICE!!! aa jayegi...")
    assert "V4" in rules_hit("पुलिस, आएगी।")


@pytest.mark.parametrize(
    "text",
    [
        "Namaste, main Rohit Patil bol raha hoon Sahyog Finance se.",
        "Sir, aapke personal loan ki EMI das din se pending hai, 5500 rupaye. Kab tak ho payega?",
        "Agreement ke hisaab se company legal notice bhej sakti hai.",
        "Pending EMI ki reporting credit bureau ko di jaati hai.",
        "Aap shukrawar tak payment kar dijiye, main date note kar leta hoon.",
        "Kya aapke office ka number wahi hai jo humare record mein hai?",  # V5 bait that is allowed (weak only)
        "Dhanyavaad, aapka din accha rahe.",
        "तुमच्या हप्त्याची तारीख सांगाल का? मी नोंदवून ठेवते.",
    ],
)
def test_polite_compliant_agent_lines_produce_no_strong_candidates(text):
    hits = rules_hit(text)
    assert "strong" not in hits.values(), hits


def test_latin_words_need_word_boundaries():
    assert "V5" not in rules_hit("Shruti ji ko call kijiye")  # "hr" inside "Shruti"
    assert "V5" in rules_hit("HR ko bata dunga")
    assert "V2" not in rules_hit("Aapki chori hui cheez wapas mil gayi")  # "chor" inside "chori"


def test_agent_speech_only_when_roles_are_known():
    segs = [seg(0, "Aap chor ho", "borrower"), seg(1, "Theek hai sir", "agent")]
    assert find_candidates(segs, "hinglish") == []


def test_unknown_roles_scan_everything():
    segs = [seg(0, "Aap chor ho", "unknown")]
    assert [c.rule_code for c in find_candidates(segs, "hinglish")] == ["V2"]


def test_language_filter_keeps_marathi_patterns_out_of_hinglish_calls():
    assert "V4" not in rules_hit("पोलीस येतील", language="hinglish")
    assert "V4" in rules_hit("पोलीस येतील", language="marathi")


def test_one_candidate_per_rule_and_segment_and_strong_wins():
    cands = find_candidates([seg(0, "police aur kal police aa jayegi, jail bhej denge")], "hinglish")
    v4 = [c for c in cands if c.rule_code == "V4"]
    assert len(v4) == 1 and v4[0].strength == "strong"


def test_disabled_rules_are_skipped():
    segs = [seg(0, "Aap chor ho aur kal police aa jayegi")]
    assert {c.rule_code for c in find_candidates(segs, "hinglish", enabled_rules={"V4"})} == {"V4"}


# ---- layer 1 together --------------------------------------------------------------------------------------------


def test_run_layer1_combines_v1_v8_and_candidates():
    segs = [
        seg(0, "Haan hello, Dinesh bol rahe ho?"),
        seg(1, "Kal tak nahi aaya toh padosiyon ko bata dunga", start=30),
    ]
    r = run_layer1(segs, "hinglish", datetime(2026, 11, 3, 21, 40, tzinfo=IST), False)
    assert r.v1_outside_hours and r.v8_missing_intro and {c.rule_code for c in r.candidates} == {"V5"}


def test_run_layer1_respects_disabled_v1_and_v8():
    segs = [seg(0, "Haan hello")]
    r = run_layer1(segs, "hinglish", datetime(2026, 11, 3, 21, 40, tzinfo=IST), False, enabled_rules={"V2"})
    assert not r.v1_outside_hours and not r.v8_missing_intro


# ---- roles -------------------------------------------------------------------------------------------------------


def test_roles_picks_the_agent_by_vocabulary():
    segs = [
        (2, 0.0, "Haan ji boliye."),
        (1, 3.0, "Namaste, main Rohit bol raha hoon Sahyog Finance se. Aapki EMI pending hai."),
        (2, 9.0, "Agle hafte tak kar dunga, thoda time dijiye."),
        (1, 14.0, "Payment kab tak ho payega?"),
    ]
    m = map_roles(segs)
    assert m.agent_speaker_id == 1 and m.label(1) == "agent" and m.label(2) == "borrower"


def test_roles_agent_can_be_the_first_or_the_second_speaker():
    segs = [
        (1, 0.0, "Haan boliye, paisa nahi hai abhi."),
        (2, 3.0, "Main Pooja bol rahi hoon Sahyog Finance se, EMI overdue hai."),
    ]
    assert map_roles(segs).agent_speaker_id == 2


def test_roles_tie_goes_to_the_first_speaker():
    segs = [(1, 0.0, "Haan."), (2, 2.0, "Theek hai.")]
    assert map_roles(segs).agent_speaker_id == 1


def test_roles_single_speaker_or_none_is_unknown():
    assert map_roles([(1, 0.0, "EMI pending hai"), (1, 4.0, "payment kab")]).agent_speaker_id is None
    assert map_roles([(None, 0.0, "EMI pending hai")]).label(None) == "unknown"
    assert map_roles([]).agent_speaker_id is None


def test_roles_with_three_speaker_ids_marks_the_rest_as_borrower():
    segs = [
        (1, 0.0, "Haan."),
        (2, 2.0, "Main Rohit bol raha hoon Sahyog Finance se, EMI pending."),
        (3, 5.0, "Paisa nahi hai."),
    ]
    m = map_roles(segs)
    assert m.agent_speaker_id == 2 and m.label(1) == "borrower" and m.label(3) == "borrower"


def test_roles_marathi():
    segs = [
        (1, 0.0, "हो, बोला. पगार उशिरा झाला."),
        (2, 3.0, "नमस्कार, मी स्नेहा बोलतेय. तुमचा हप्ता थकलेला आहे."),
        (1, 9.0, "या महिन्याच्या शेवटी भरतो."),
    ]
    assert map_roles(segs).agent_speaker_id == 2


# ---- the dev split, end to end (plan.md Section 9.3: tune on dev only) ------------------------------------------

SCRIPTS = Path(__file__).resolve().parents[2] / "data" / "scripts"
DEV = {
    "call_01": [],
    "call_02": ["V2", "V9"],
    "call_05": ["V4"],
    "call_06": [],
    "call_09": [],
    "call_11": ["V3", "V7"],
    "call_16": ["V5"],
    "call_20": [],
    "call_22": [],
    "call_26": [],
}  # V6 (call_20) is left to the LLM; V8 and V1 are checked below
DEV_TIMES = {"call_16": "16:20", "call_26": "20:15", "call_22": "19:00"}


def load_script(name: str) -> tuple[list[DSegment], str, str]:
    lines = (SCRIPTS / f"{name}.md").read_text(encoding="utf-8").splitlines()
    header = re.search(r"Time: (\d\d:\d\d).*Language: (\w+)", next(ln for ln in lines if ln.startswith("[")))
    assert header
    segs: list[DSegment] = []
    t = 0.0
    for ln in lines:
        m = re.match(r"^(AGENT|BORROWER):\s*(.+?)(?:\s*<<V\d>>)?$", ln)
        if m:
            text = mask_pii(m.group(2)).text
            segs.append(DSegment(len(segs), m.group(1).lower(), t, t + 6.0, text))  # type: ignore[arg-type]
            t += 6.5
    return segs, header.group(2).lower(), header.group(1)


@pytest.mark.skipif(not SCRIPTS.exists(), reason="data/scripts not present")
@pytest.mark.parametrize("name,expected", sorted(DEV.items()))
def test_dev_scripts_layer1_finds_expected_rules_and_no_strong_noise(name, expected):
    segs, language, hhmm = load_script(name)
    hh, mm = map(int, hhmm.split(":"))
    r = run_layer1(segs, language, datetime(2026, 11, 3, hh, mm, tzinfo=IST), False)
    found = {c.rule_code for c in r.candidates}
    assert set(expected) <= found, f"{name}: expected {expected}, found {found}"
    if not expected:  # clean dev calls: nothing strong may fire
        assert not [c for c in r.candidates if c.strength == "strong"], r.candidates


@pytest.mark.skipif(not SCRIPTS.exists(), reason="data/scripts not present")
def test_dev_scripts_v1_and_v8():
    for name, expect_v1 in [("call_26", True), ("call_22", False), ("call_01", False), ("call_16", False)]:
        segs, language, hhmm = load_script(name)
        hh, mm = map(int, hhmm.split(":"))
        r = run_layer1(segs, language, datetime(2026, 11, 3, hh, mm, tzinfo=IST), False)
        assert r.v1_outside_hours is expect_v1, name
    seg16, lang16, _ = load_script("call_16")
    assert check_introduction(seg16, lang16).missing  # the agent never introduces himself
    for clean in ["call_01", "call_02", "call_05", "call_06", "call_09", "call_11", "call_20", "call_22", "call_26"]:
        s, lang, _ = load_script(clean)
        assert not check_introduction(s, lang).missing, clean


@pytest.mark.skipif(not SCRIPTS.exists(), reason="data/scripts not present")
def test_dev_script_roles_are_mapped_correctly_when_labels_are_hidden():
    for name in ["call_01", "call_02", "call_05", "call_09", "call_11", "call_20"]:
        segs, _, _ = load_script(name)
        # hide the real labels: speaker id 1 = whoever speaks first
        ids = []
        first = segs[0].speaker
        for s in segs:
            ids.append((1 if s.speaker == first else 2, s.start_s, s.text))
        m = map_roles(ids)
        agent_first = segs[0].speaker == "agent"
        assert m.agent_speaker_id == (1 if agent_first else 2), name
