from __future__ import annotations

import pytest

from app.detection.masking import mask_pii
from app.detection.normalise import for_matching, has_devanagari, normalise


def test_normalise_casefold_whitespace_and_zero_width():
    assert normalise("  Hello​   WORLD\t\n") == "hello world"
    assert normalise("ǅ") == "ǆ"  # casefold on special letters


def test_normalise_nfc_makes_equivalent_devanagari_forms_equal():
    composed = "क़"  # U+0958
    decomposed = "क़"  # ka + nukta
    assert normalise(composed) == normalise(decomposed)


def test_for_matching_strips_punctuation_but_keeps_devanagari_vowel_signs():
    assert for_matching("Police!!, aa jayegi.") == "police aa jayegi"
    assert for_matching("पुलिस आएगी।") == "पुलिस आएगी"
    assert for_matching("ऑफिसमध्ये, सगळ्यांना सांगू") == "ऑफिसमध्ये सगळ्यांना सांगू"
    assert for_matching("₹12,500 (EMI)") == "12 500 emi"


def test_has_devanagari():
    assert has_devanagari("main hoon पोलीस") and not has_devanagari("hello")


# ---- masking ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["9876543210", "+91 98765 43210", "98765-43210", "91 9876543210", "+919876543210", "9 8 7 6 5 4 3 2 1 0"],
)
def test_phone_numbers_are_masked(text):
    r = mask_pii(f"mera number {text} hai")
    assert "[PHONE]" in r.text and not any(ch.isdigit() for ch in r.text.replace("[PHONE]", "")), r.text


def test_aadhaar_pan_and_account():
    r = mask_pii("aadhaar 1234 5678 9012, PAN ABCDE1234F, account 123456789012345")
    assert "[AADHAAR]" in r.text and "[PAN]" in r.text and "[ACCOUNT]" in r.text
    assert "1234" not in r.text and "ABCDE" not in r.text and "123456789" not in r.text


def test_lowercase_pan_is_masked_too():
    assert "[PAN]" in mask_pii("pan abcde1234f hai").text


@pytest.mark.parametrize(
    "text",
    [
        "5500 rupaye",
        "₹12,500",
        "1,20,000 baaki hain",
        "EMI 4200 hai",
        "do hazaar paanch sau",
        "paanch hazaar rupaye",
        "28 din se pending",
        "loan 2024 mein liya",
        "SF-PL-204871",
        "chaudah EMI baaki hain",
        "10 tarikh ko",
    ],
)
def test_ordinary_amounts_and_references_are_not_masked(text):
    r = mask_pii(text)
    assert r.text == text and not r.changed


def test_spoken_digit_runs_in_hindi_latin():
    r = mask_pii("Likh lijiye. Nau aath saat chhah paanch chaar teen do ek shunya.")
    assert r.text == "Likh lijiye. [PHONE]." and r.counts["[PHONE]"] == 1


def test_spoken_digit_runs_in_english():
    assert mask_pii("it is nine eight seven six five four three two one zero ok").text == "it is [PHONE] ok"


def test_spoken_digit_runs_in_devanagari_hindi_and_marathi():
    assert "[PHONE]" in mask_pii("नौ आठ सात छह पांच चार तीन दो एक शून्य").text
    assert "[PHONE]" in mask_pii("नऊ आठ सात सहा पाच चार तीन दोन एक शून्य").text


def test_spoken_run_length_picks_the_tag():
    assert mask_pii("ek do teen char paanch chhah").text == "[ACCOUNT]"  # 6 words
    assert mask_pii("ek do teen char paanch chhah saat aath nau ek do teen").text == "[AADHAAR]"  # 12 words


def test_short_digit_word_sequences_are_left_alone():
    for text in ["ek do teen", "main do din mein dunga", "I have one two three four five", "teen char din baad"]:
        assert mask_pii(text).text == text


def test_runs_are_masked_inside_a_longer_sentence_and_punctuation_survives():
    r = mask_pii("Mera number nau aath saat chhah paanch chaar teen do ek shunya hai, note kar lo.")
    assert r.text == "Mera number [PHONE] hai, note kar lo."


def test_masking_is_idempotent():
    once = mask_pii("call 9876543210 or nau aath saat chhah paanch chaar teen do ek shunya").text
    assert mask_pii(once).text == once


def test_marathi_text_around_numbers_is_untouched():
    r = mask_pii("तुमचा हप्ता 4800 रुपये आहे, नंबर 9876543210")
    assert r.text == "तुमचा हप्ता 4800 रुपये आहे, नंबर [PHONE]"
