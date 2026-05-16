"""Sandbox routes — no-persistence preview of every registered question type.

Visitors land on `/sandbox` and can interact with one widget per type.
Interactions emit two things:

  1. A local status label on the widget itself (instant client-side feedback).
  2. An HTMX OOB swap to a sticky activity log that lists every emit, so a
     human tester sees the running history and a future Playwright test
     has a stable place to assert against.

Nothing reaches the database. The `/sandbox/echo` endpoint validates the
payload using the same `validate_payload` helper that `/respond` uses, then
returns an HTML fragment. If a widget's wire format ever drifts from what
the real handler expects, the sandbox breaks loudly.

Discoverability is intentionally subtle (footer link); robots.txt also
disallows /sandbox so search engines don't index it as if it were the real
survey.
"""
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from ..config import get_settings
from ..question_types import QUESTION_TYPES, PayloadError, validate_payload

router = APIRouter()
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _ctx(request: Request, **extra) -> dict:
    s = get_settings()
    return {"request": request, "goatcounter_site_code": s.goatcounter_site_code, **extra}


@router.get("/sandbox", response_class=HTMLResponse)
def sandbox_index(request: Request) -> HTMLResponse:
    # Wrap each sample dict in a SimpleNamespace so the existing partials
    # (which use `q.slug`, `q.payload`, `q.question_id`, etc.) render
    # without modification.
    sections = [
        {
            "type": qt,
            "q": SimpleNamespace(**qt.sandbox_sample),
        }
        for qt in QUESTION_TYPES.values()
    ]
    return TEMPLATES.TemplateResponse(
        "sandbox/index.html",
        _ctx(
            request,
            sections=sections,
            existing={},
            sandbox=True,
            breadcrumb=[{"label": "Sandbox"}],
        ),
    )


@router.post("/sandbox/echo")
async def sandbox_echo(request: Request) -> HTMLResponse:
    form = await request.form()
    question_slug = str(form.get("question_slug", "")).strip()
    question_type = str(form.get("question_type", "")).strip()
    if not question_slug or not question_type:
        raise HTTPException(400, "missing question_slug or question_type")
    if question_type not in QUESTION_TYPES:
        raise HTTPException(400, f"unknown question type: {question_type!r}")

    try:
        _, summary = validate_payload(question_type, form)
    except PayloadError as e:
        raise HTTPException(400, str(e)) from None

    now = datetime.now(UTC).strftime("%H:%M:%S")
    return TEMPLATES.TemplateResponse(
        "sandbox/_log_entry.html",
        {
            "request": request,
            "timestamp": now,
            "question_slug": question_slug,
            "question_type": question_type,
            "summary": summary,
            "oob": True,
        },
    )


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt() -> PlainTextResponse:
    # The sandbox is public so anyone can poke at the widgets, but search
    # engines indexing it would confuse visitors about what ting is.
    return PlainTextResponse("User-agent: *\nDisallow: /sandbox\n")
