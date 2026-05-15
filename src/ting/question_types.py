"""Question-type registry.

Single source of truth for: which question types ting renders, which partial
template each one uses, what sandbox sample data they need, and how to
validate a posted payload. Used by `/respond` (the real path) and `/sandbox`
(the no-persistence preview page). Adding a new question type means a new
entry here, a new partial, and a new dispatch arm in `survey/show.html`.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class QuestionType:
    slug: str           # internal id used in DB + form fields ("ranking", "nps", "likert")
    label: str          # human-readable label for sandbox section headers
    description: str    # short blurb for sandbox visitors
    partial: str        # Jinja partial path under templates/
    sandbox_sample: dict  # data shape matching real DB rows enough to render the partial


# Sample-data slugs are namespaced under "sandbox-" so a future grep can
# spot them and confirm nothing real persists them. They are NEVER inserted
# into the DB — the sandbox echo endpoint validates but discards.
_RANKING_SAMPLE = {
    "question_id": UUID("00000000-0000-0000-0000-000000000001"),
    "slug": "sandbox-ranking",
    "type": "ranking",
    "prompt": "Rank these in order of importance to your family",
    "payload": {
        "proposal_slugs": [
            "sample-after-school-programs",
            "sample-classroom-resources",
            "sample-building-maintenance",
            "sample-family-events",
        ],
    },
}

_NPS_SAMPLE = {
    "question_id": UUID("00000000-0000-0000-0000-000000000002"),
    "slug": "sandbox-nps",
    "type": "nps",
    "prompt": "How likely are you to recommend this sandbox to a fellow tester?",
    "payload": {"subject": "this sandbox page"},
}

_LIKERT_SAMPLE = {
    "question_id": UUID("00000000-0000-0000-0000-000000000003"),
    "slug": "sandbox-likert",
    "type": "likert",
    "prompt": "Read the statement, then pick how strongly you agree",
    "payload": {"statement": "The sandbox makes it easy to try the widgets."},
}


QUESTION_TYPES: dict[str, QuestionType] = {
    "ranking": QuestionType(
        slug="ranking",
        label="Ranking",
        description="Drag items into your preferred order. Most important at the top.",
        partial="survey/_ranking.html",
        sandbox_sample=_RANKING_SAMPLE,
    ),
    "nps": QuestionType(
        slug="nps",
        label="NPS (0-10)",
        description="Pick a number from 0 to 10. Higher means more likely.",
        partial="survey/_nps.html",
        sandbox_sample=_NPS_SAMPLE,
    ),
    "likert": QuestionType(
        slug="likert",
        label="Likert (agree/disagree)",
        description="Pick how strongly you agree with the statement.",
        partial="survey/_likert.html",
        sandbox_sample=_LIKERT_SAMPLE,
    ),
}


class PayloadError(ValueError):
    """Raised when a posted form payload fails type-specific validation."""


def validate_payload(question_type: str, form: Mapping[str, Any]) -> tuple[dict, str]:
    """Validate + canonicalize a posted answer for a question of `question_type`.

    Returns `(payload_dict, human_summary)`:
    - `payload_dict` is what `/respond` writes to `Response.payload` (and what
      `/sandbox/echo` validates but discards).
    - `human_summary` is the short text the sandbox log shows ("chose 7",
      "moved 'X' up").

    Raises `PayloadError` with a short message on bad input.
    """
    if question_type == "ranking":
        raw_order = form.get("order", "")
        order = [x for x in str(raw_order).split(",") if x.strip()]
        if not order:
            raise PayloadError("ranking: order is empty")
        return {"order": order}, "Order: " + " > ".join(order)

    if question_type == "nps":
        try:
            score = int(form.get("score", -1))
        except (TypeError, ValueError):
            raise PayloadError("nps: score must be an integer") from None
        if not 0 <= score <= 10:
            raise PayloadError("nps: score out of range (0-10)")
        return {"score": score}, f"Chose {score}/10"

    if question_type == "likert":
        try:
            score = int(form.get("score", -1))
        except (TypeError, ValueError):
            raise PayloadError("likert: score must be an integer") from None
        if not 1 <= score <= 5:
            raise PayloadError("likert: score out of range (1-5)")
        labels = {1: "Strongly disagree", 2: "Disagree", 3: "Neutral", 4: "Agree", 5: "Strongly agree"}
        return {"score": score}, f"{labels[score]} ({score})"

    raise PayloadError(f"unknown question type: {question_type!r}")
