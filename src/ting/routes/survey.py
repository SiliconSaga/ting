# src/ting/routes/survey.py
from datetime import datetime, UTC
from uuid import UUID

from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..auth import resolve_session, clear_session
from ..db import session_scope
from ..models import Cohort, Code, Question, Response, MetricsEvent
from ..valkey import get_valkey
from ..ratelimit import allow_write
from ..config import get_settings


router = APIRouter()
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _require_code(request: Request) -> UUID:
    sid = request.cookies.get("ting_session")
    if not sid:
        raise HTTPException(status_code=401, detail="no session")
    code_id = resolve_session(sid)
    if code_id is None:
        raise HTTPException(status_code=401, detail="session expired")
    return code_id


def _ctx(request: Request, **extra) -> dict:
    s = get_settings()
    return {"request": request, "goatcounter_site_code": s.goatcounter_site_code, **extra}


@router.get("/survey", response_class=HTMLResponse)
def survey_index(request: Request) -> HTMLResponse:
    code_id = _require_code(request)
    with session_scope() as s:
        code = s.get(Code, code_id)
        if code is None:
            raise HTTPException(404)
        cohort = s.get(Cohort, code.cohort_id)
        if cohort is None or cohort.retired_at is not None:
            raise HTTPException(410, "cohort retired")
        questions = list(s.scalars(
            select(Question).where(Question.cohort_id == cohort.cohort_id, Question.display_order.is_not(None))
            .order_by(Question.display_order)
        ))
        existing = {r.question_id: r.payload for r in s.scalars(
            select(Response).where(Response.code_id == code_id)
        )}

    # Stash survey_started in Valkey for duration tracking
    vk = get_valkey()
    started_key = f"survey:{code_id}:started"
    if not vk.exists(started_key):
        vk.setex(started_key, 24 * 3600, datetime.now(UTC).isoformat())

    return TEMPLATES.TemplateResponse(
        "survey/index.html",
        _ctx(request, questions=questions, existing=existing, code=code),
    )


@router.post("/respond/{question_slug}")
async def respond(question_slug: str, request: Request) -> JSONResponse:
    code_id = _require_code(request)
    if not allow_write(str(code_id)):
        raise HTTPException(429, "rate-limited")

    form = await request.form()
    payload: dict = {}
    with session_scope() as s:
        q = s.scalar(select(Question).where(Question.slug == question_slug))
        if q is None:
            raise HTTPException(404, "question not found")

        if q.type == "ranking":
            raw_order = form.get("order", "")
            order = [x for x in str(raw_order).split(",") if x.strip()]
            payload = {"order": order}
        elif q.type == "nps":
            score = int(form.get("score", -1))
            if not 0 <= score <= 10:
                raise HTTPException(400, "score out of range")
            payload = {"score": score}
        elif q.type == "likert":
            score = int(form.get("score", -1))
            if not 1 <= score <= 5:
                raise HTTPException(400, "score out of range")
            payload = {"score": score}
        else:
            raise HTTPException(400, "unknown question type")

        stmt = pg_insert(Response).values(
            code_id=code_id, question_id=q.question_id, payload=payload,
        ).on_conflict_do_update(
            index_elements=["code_id", "question_id"],
            set_={"payload": payload, "updated_at": datetime.now(UTC)},
        )
        s.execute(stmt)

    return JSONResponse({"ok": True})


@router.post("/survey/complete")
def survey_complete(request: Request) -> JSONResponse:
    code_id = _require_code(request)
    vk = get_valkey()
    started_iso = vk.get(f"survey:{code_id}:started")
    duration_seconds = None
    if started_iso:
        started = datetime.fromisoformat(started_iso)
        duration_seconds = int((datetime.now(UTC) - started).total_seconds())
    with session_scope() as s:
        s.add(MetricsEvent(event="survey_completed", code_id=code_id, duration_seconds=duration_seconds))
    return JSONResponse({"ok": True, "duration_seconds": duration_seconds})


@router.post("/logout")
def logout(request: Request) -> HTMLResponse:
    sid = request.cookies.get("ting_session")
    if sid:
        clear_session(sid)
    resp = HTMLResponse('<a href="/">Signed out. Back to start</a>')
    resp.delete_cookie("ting_session")
    return resp
