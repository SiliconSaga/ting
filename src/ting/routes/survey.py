# src/ting/routes/survey.py
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..auth import clear_session, resolve_session
from ..config import get_settings
from ..db import session_scope
from ..models import (
    Code,
    Cohort,
    Comment,
    Endorsement,
    MetricsEvent,
    Pledge,
    Proposal,
    Question,
    Response,
    Survey,
)
from ..question_types import PayloadError, validate_payload
from ..ratelimit import allow_write
from ..valkey import get_valkey

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


def _surveys_for_code(s, cohort_id: UUID, code_id: UUID) -> list[dict]:
    """Build a list of survey-summary dicts for the survey-picker page."""
    rows = list(s.scalars(
        select(Survey).where(Survey.cohort_id == cohort_id).order_by(Survey.display_order)
    ))
    answered = {
        qid for (qid,) in s.execute(
            select(Response.question_id).where(Response.code_id == code_id)
        ).all()
    }
    out = []
    for sv in rows:
        questions = list(s.scalars(
            select(Question).where(
                Question.survey_id == sv.survey_id,
                Question.display_order.is_not(None),
            )
        ))
        total = len(questions)
        done = sum(1 for q in questions if q.question_id in answered)
        out.append({
            "slug": sv.slug,
            "title": sv.title,
            "intro": sv.intro,
            "display_order": sv.display_order,
            "total": total,
            "answered": done,
        })
    return out


@router.get("/survey", response_class=HTMLResponse)
def survey_list(request: Request) -> HTMLResponse:
    """Picker: list of surveys available to this code, with progress per survey."""
    code_id = _require_code(request)
    with session_scope() as s:
        code = s.get(Code, code_id)
        if code is None:
            raise HTTPException(404)
        cohort = s.get(Cohort, code.cohort_id)
        if cohort is None or cohort.retired_at is not None:
            raise HTTPException(410, "cohort retired")
        surveys = _surveys_for_code(s, cohort.cohort_id, code_id)
        cohort_name = cohort.name

    return TEMPLATES.TemplateResponse(
        "survey/list.html",
        _ctx(
            request,
            surveys=surveys,
            cohort_name=cohort_name,
            breadcrumb=[{"label": "Your surveys"}],
        ),
    )


@router.get("/survey/{survey_slug}", response_class=HTMLResponse)
def survey_show(survey_slug: str, request: Request) -> HTMLResponse:
    """Render the questions of one specific survey."""
    code_id = _require_code(request)
    with session_scope() as s:
        code = s.get(Code, code_id)
        if code is None:
            raise HTTPException(404)
        cohort = s.get(Cohort, code.cohort_id)
        if cohort is None or cohort.retired_at is not None:
            raise HTTPException(410, "cohort retired")
        survey = s.scalar(
            select(Survey).where(
                Survey.cohort_id == cohort.cohort_id,
                Survey.slug == survey_slug,
            )
        )
        if survey is None:
            raise HTTPException(404, "survey not found in this cohort")
        questions = list(s.scalars(
            select(Question)
            .where(Question.survey_id == survey.survey_id, Question.display_order.is_not(None))
            .order_by(Question.display_order)
        ))
        existing = {r.question_id: r.payload for r in s.scalars(
            select(Response).where(Response.code_id == code_id)
        )}
        nav_surveys = _surveys_for_code(s, cohort.cohort_id, code_id)
        survey_data = {"slug": survey.slug, "title": survey.title, "intro": survey.intro}

    vk = get_valkey()
    started_key = f"survey:{code_id}:started"
    if not vk.exists(started_key):
        vk.setex(started_key, 24 * 3600, datetime.now(UTC).isoformat())

    return TEMPLATES.TemplateResponse(
        "survey/show.html",
        _ctx(
            request,
            survey=survey_data,
            questions=questions,
            existing=existing,
            nav_surveys=nav_surveys,
            breadcrumb=[
                {"label": "Your surveys", "href": "/survey"},
                {"label": survey_data["title"]},
            ],
        ),
    )


@router.post("/respond/{question_slug}")
async def respond(question_slug: str, request: Request) -> HTMLResponse:
    code_id = _require_code(request)
    if not allow_write(str(code_id)):
        raise HTTPException(429, "rate-limited")

    form = await request.form()
    payload: dict = {}
    survey_slug: str | None = None
    nav_surveys: list[dict] = []
    with session_scope() as s:
        q = s.scalar(select(Question).where(Question.slug == question_slug))
        if q is None:
            raise HTTPException(404, "question not found")

        try:
            payload, _ = validate_payload(q.type, form)
        except PayloadError as e:
            raise HTTPException(400, str(e)) from None

        stmt = pg_insert(Response).values(
            code_id=code_id, question_id=q.question_id, payload=payload,
        ).on_conflict_do_update(
            index_elements=["code_id", "question_id"],
            set_={"payload": payload, "updated_at": datetime.now(UTC)},
        )
        s.execute(stmt)

        # Recompute the survey tab strip for an HTMX out-of-band update.
        survey = s.get(Survey, q.survey_id)
        if survey is not None:
            survey_slug = survey.slug
            nav_surveys = _surveys_for_code(s, survey.cohort_id, code_id)

    # Body content is ignored by hx-swap="none"; the OOB nav update is the payload.
    return TEMPLATES.TemplateResponse(
        "survey/_tabs.html",
        {"request": request, "survey_slug": survey_slug, "nav_surveys": nav_surveys, "oob": True},
    )


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


@router.get("/proposal/{slug}", response_class=HTMLResponse)
def proposal_detail(slug: str, request: Request) -> HTMLResponse:
    code_id = _require_code(request)
    with session_scope() as s:
        p = s.scalar(select(Proposal).where(Proposal.slug == slug))
        if p is None:
            raise HTTPException(404)
        comments = list(s.scalars(
            select(Comment).where(Comment.proposal_id == p.proposal_id, Comment.hidden_at.is_(None))
            .order_by(Comment.created_at.desc())
        ))
        my_endorsements = {
            e.comment_id for e in s.scalars(
                select(Endorsement).where(Endorsement.code_id == code_id)
            )
        }
        existing_pledge = s.scalar(
            select(Pledge).where(Pledge.code_id == code_id, Pledge.proposal_id == p.proposal_id)
        )
        comment_count = s.scalar(
            select(func.count(Comment.comment_id)).where(Comment.author_code_id == code_id)
        ) or 0
    return TEMPLATES.TemplateResponse(
        "survey/proposal.html",
        _ctx(request, proposal=p, comments=comments, my_endorsements=my_endorsements,
             existing_pledge=existing_pledge, comment_count=comment_count),
    )


@router.post("/proposal/{slug}/comment")
async def post_comment(
    slug: str, request: Request, body: str = Form(...), confirm_read: bool = Form(False),
) -> JSONResponse:
    code_id = _require_code(request)
    if not allow_write(str(code_id)):
        raise HTTPException(429)
    if not confirm_read:
        raise HTTPException(400, "must confirm you've read existing comments")
    if not body.strip():
        raise HTTPException(400, "empty body")

    s_cfg = get_settings()
    with session_scope() as s:
        p = s.scalar(select(Proposal).where(Proposal.slug == slug))
        if p is None:
            raise HTTPException(404)
        cnt = s.scalar(
            select(func.count(Comment.comment_id)).where(Comment.author_code_id == code_id)
        ) or 0
        if cnt >= s_cfg.max_comments_per_code:
            raise HTTPException(403, f"comment cap reached ({s_cfg.max_comments_per_code})")
        s.add(Comment(proposal_id=p.proposal_id, author_code_id=code_id, body=body.strip()))
        s.add(MetricsEvent(event="comment_posted", code_id=code_id))
    return JSONResponse({"ok": True})


@router.post("/comment/{comment_id}/endorse")
def toggle_endorse(comment_id: UUID, request: Request) -> JSONResponse:
    code_id = _require_code(request)
    if not allow_write(str(code_id)):
        raise HTTPException(429)
    with session_scope() as s:
        existing = s.scalar(
            select(Endorsement).where(Endorsement.code_id == code_id, Endorsement.comment_id == comment_id)
        )
        if existing is None:
            s.add(Endorsement(code_id=code_id, comment_id=comment_id))
            s.add(MetricsEvent(event="endorsement_toggled", code_id=code_id))
            return JSONResponse({"endorsed": True})
        else:
            s.delete(existing)
            return JSONResponse({"endorsed": False})


@router.post("/proposal/{slug}/pledge")
async def post_pledge(slug: str, request: Request,
                      amount_dollars: Decimal = Form(0), hours_per_week: Decimal = Form(0)) -> JSONResponse:
    code_id = _require_code(request)
    if not allow_write(str(code_id)):
        raise HTTPException(429)
    if amount_dollars < 0 or hours_per_week < 0:
        raise HTTPException(400, "non-negative values only")
    with session_scope() as s:
        p = s.scalar(select(Proposal).where(Proposal.slug == slug))
        if p is None:
            raise HTTPException(404)
        stmt = pg_insert(Pledge).values(
            code_id=code_id, proposal_id=p.proposal_id,
            amount_dollars=amount_dollars, hours_per_week=hours_per_week,
        ).on_conflict_do_update(
            index_elements=["code_id", "proposal_id"],
            set_={"amount_dollars": amount_dollars, "hours_per_week": hours_per_week,
                  "updated_at": datetime.now(UTC)},
        )
        s.execute(stmt)
        s.add(MetricsEvent(event="pledge_added", code_id=code_id))
    return JSONResponse({"ok": True})
