"""Unit tests for the question_types registry + validator."""
import pytest

from ting.question_types import QUESTION_TYPES, PayloadError, validate_payload


def test_registry_has_expected_types():
    assert set(QUESTION_TYPES) == {
        "ranking", "nps", "likert", "checkboxes", "radio", "short_text", "long_text",
    }


def test_registry_entries_point_at_real_partials():
    # Every registered type's `partial` must exist on disk so the sandbox
    # page doesn't 500 with a TemplateNotFound when new types are added.
    from pathlib import Path
    templates_dir = Path("src/ting/templates")
    for qt in QUESTION_TYPES.values():
        assert (templates_dir / qt.partial).is_file(), qt.partial


def test_validate_ranking_happy():
    payload, summary = validate_payload("ranking", {"order": "a,b,c"})
    assert payload == {"order": ["a", "b", "c"]}
    assert "Order:" in summary
    assert "a" in summary and "c" in summary


def test_validate_ranking_empty_order_rejected():
    with pytest.raises(PayloadError):
        validate_payload("ranking", {"order": ""})


def test_validate_ranking_strips_blanks():
    payload, _ = validate_payload("ranking", {"order": "a, ,b,,c"})
    assert payload == {"order": ["a", "b", "c"]}


def test_validate_ranking_trims_whitespace_around_tokens():
    payload, summary = validate_payload("ranking", {"order": " a , b ,c ,  d "})
    assert payload == {"order": ["a", "b", "c", "d"]}
    # The display summary should use the trimmed tokens too.
    assert summary == "Order: a > b > c > d"


def test_validate_nps_happy():
    payload, summary = validate_payload("nps", {"score": "7"})
    assert payload == {"score": 7}
    assert "7" in summary


def test_validate_nps_out_of_range():
    with pytest.raises(PayloadError):
        validate_payload("nps", {"score": "11"})
    with pytest.raises(PayloadError):
        validate_payload("nps", {"score": "-1"})


def test_validate_nps_non_numeric():
    with pytest.raises(PayloadError):
        validate_payload("nps", {"score": "seven"})


def test_validate_likert_happy():
    payload, summary = validate_payload("likert", {"score": "4"})
    assert payload == {"score": 4}
    assert "Agree" in summary
    assert "(4)" in summary


def test_validate_likert_out_of_range():
    with pytest.raises(PayloadError):
        validate_payload("likert", {"score": "0"})
    with pytest.raises(PayloadError):
        validate_payload("likert", {"score": "6"})


def test_validate_checkboxes_happy():
    payload, summary = validate_payload("checkboxes", {"selected": ["Email", "Texts"]})
    assert payload == {"selected": ["Email", "Texts"]}
    assert "Email" in summary and "Texts" in summary


def test_validate_checkboxes_empty_is_valid():
    # Zero selections is a legitimate answer ("none of these apply").
    payload, summary = validate_payload("checkboxes", {"selected": []})
    assert payload == {"selected": []}
    assert summary == "Nothing selected"


def test_validate_checkboxes_single_string_coerced():
    # A plain dict may hold a lone string rather than a list.
    payload, _ = validate_payload("checkboxes", {"selected": "Email"})
    assert payload == {"selected": ["Email"]}


def test_validate_radio_happy():
    payload, summary = validate_payload("radio", {"choice": "Email"})
    assert payload == {"choice": "Email"}
    assert "Email" in summary


def test_validate_radio_empty_rejected():
    with pytest.raises(PayloadError):
        validate_payload("radio", {"choice": ""})


def test_validate_short_text_happy():
    payload, summary = validate_payload("short_text", {"text": "  smaller classes  "})
    assert payload == {"text": "smaller classes"}
    assert "smaller classes" in summary


def test_validate_short_text_empty_ok():
    payload, summary = validate_payload("short_text", {"text": "   "})
    assert payload == {"text": ""}
    assert summary == "(empty)"


def test_validate_short_text_over_cap_rejected():
    with pytest.raises(PayloadError):
        validate_payload("short_text", {"text": "x" * 201})


def test_validate_long_text_happy():
    payload, _ = validate_payload("long_text", {"text": "a longer thought"})
    assert payload == {"text": "a longer thought"}


def test_validate_long_text_over_cap_rejected():
    with pytest.raises(PayloadError):
        validate_payload("long_text", {"text": "x" * 2001})


def test_validate_unknown_type():
    with pytest.raises(PayloadError):
        validate_payload("essay", {"text": "hello"})
