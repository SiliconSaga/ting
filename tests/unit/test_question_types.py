"""Unit tests for the question_types registry + validator."""
import pytest

from ting.question_types import QUESTION_TYPES, PayloadError, validate_payload


def test_registry_has_expected_types():
    assert set(QUESTION_TYPES) == {"ranking", "nps", "likert"}


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


def test_validate_unknown_type():
    with pytest.raises(PayloadError):
        validate_payload("freetext", {"text": "hello"})
