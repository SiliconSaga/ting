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

_CHECKBOXES_SAMPLE = {
    "question_id": UUID("00000000-0000-0000-0000-000000000004"),
    "slug": "sandbox-checkboxes",
    "type": "checkboxes",
    "prompt": "Which updates would you want? (select all that apply)",
    "payload": {
        "options": ["Newsletter", "Volunteer events", "Budget updates", "Meeting reminders"],
    },
}

_RADIO_SAMPLE = {
    "question_id": UUID("00000000-0000-0000-0000-000000000005"),
    "slug": "sandbox-radio",
    "type": "radio",
    "prompt": "How do you mostly hear school news?",
    "payload": {
        "options": ["Email", "Text message", "Social media", "Word of mouth"],
    },
}

_SHORT_TEXT_SAMPLE = {
    "question_id": UUID("00000000-0000-0000-0000-000000000006"),
    "slug": "sandbox-short-text",
    "type": "short_text",
    "prompt": "In a few words, what's your top priority this year?",
    "payload": {"placeholder": "e.g. smaller class sizes"},
}

_LONG_TEXT_SAMPLE = {
    "question_id": UUID("00000000-0000-0000-0000-000000000007"),
    "slug": "sandbox-long-text",
    "type": "long_text",
    "prompt": "Anything else you'd like to share?",
    "payload": {"placeholder": "Longer thoughts welcome..."},
}

# Character caps for the free-text types, shared by the partials (maxlength
# attribute) and validate_payload (server-side enforcement).
SHORT_TEXT_MAX = 200
LONG_TEXT_MAX = 2000


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
    "checkboxes": QuestionType(
        slug="checkboxes",
        label="Checkboxes (select any)",
        description="Tick zero or more options. Good for 'select all that apply'.",
        partial="survey/_checkboxes.html",
        sandbox_sample=_CHECKBOXES_SAMPLE,
    ),
    "radio": QuestionType(
        slug="radio",
        label="Radio buttons (select one)",
        description="Pick exactly one option from a list.",
        partial="survey/_radio.html",
        sandbox_sample=_RADIO_SAMPLE,
    ),
    "short_text": QuestionType(
        slug="short_text",
        label="Short text",
        description=f"A single-line answer, up to {SHORT_TEXT_MAX} characters.",
        partial="survey/_short_text.html",
        sandbox_sample=_SHORT_TEXT_SAMPLE,
    ),
    "long_text": QuestionType(
        slug="long_text",
        label="Long text",
        description=f"A free-form paragraph, up to {LONG_TEXT_MAX} characters.",
        partial="survey/_long_text.html",
        sandbox_sample=_LONG_TEXT_SAMPLE,
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
        order = [x.strip() for x in str(raw_order).split(",") if x.strip()]
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

    if question_type == "checkboxes":
        # Multi-value field: Starlette FormData exposes getlist(); a plain
        # dict (used by unit tests) may hold a single string or a list.
        if hasattr(form, "getlist"):
            raw = form.getlist("selected")
        else:
            v = form.get("selected", [])
            raw = v if isinstance(v, list) else [v]
        # De-duplicate (order-preserving) — checkbox semantics are a set, and
        # a client could post a value twice.
        selected: list[str] = []
        for x in raw:
            v = str(x).strip()
            if v and v not in selected:
                selected.append(v)
        # Zero selections is a valid answer ("none of these apply").
        summary = "Selected: " + ", ".join(selected) if selected else "Nothing selected"
        return {"selected": selected}, summary

    if question_type == "radio":
        choice = str(form.get("choice", "")).strip()
        if not choice:
            raise PayloadError("radio: no option chosen")
        return {"choice": choice}, f"Chose {choice}"

    if question_type in ("short_text", "long_text"):
        text = str(form.get("text", "")).strip()
        cap = SHORT_TEXT_MAX if question_type == "short_text" else LONG_TEXT_MAX
        if len(text) > cap:
            raise PayloadError(f"{question_type}: text exceeds {cap} characters")
        if not text:
            return {"text": ""}, "(empty)"
        preview = text if len(text) <= 60 else text[:60] + "..."
        return {"text": text}, f'Entered "{preview}" ({len(text)} chars)'

    raise PayloadError(f"unknown question type: {question_type!r}")
