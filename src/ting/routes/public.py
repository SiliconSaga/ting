# src/ting/routes/public.py
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from ..auth import mint_session
from ..codes import normalize_code
from ..config import get_settings
from ..db import session_scope
from ..models import Code, Cohort
from ..ratelimit import allow_redemption

router = APIRouter()
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _ctx(request: Request, **extra) -> dict:
    s = get_settings()
    return {
        "request": request,
        "goatcounter_site_code": s.goatcounter_site_code,
        **extra,
    }


@router.get("/", response_class=HTMLResponse)
def landing(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse("public/landing.html", _ctx(request, breadcrumb=[]))


@router.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(
        "public/privacy.html",
        _ctx(request, breadcrumb=[{"label": "Privacy"}]),
    )


@router.get("/about", response_class=HTMLResponse)
def about(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(
        "public/about.html",
        _ctx(request, breadcrumb=[{"label": "About"}]),
    )


@router.get("/cohort/{cohort_name}", response_class=HTMLResponse)
def cohort_info(cohort_name: str, request: Request) -> HTMLResponse:
    """Public-facing context page for a cohort (no code required)."""
    from sqlalchemy import select

    from ..db import session_scope
    from ..models import Cohort, School, Survey

    with session_scope() as s:
        cohort = s.scalar(select(Cohort).where(Cohort.name == cohort_name))
        if cohort is None:
            from fastapi import HTTPException
            raise HTTPException(404, "cohort not found")
        school = s.scalar(select(School).where(School.school_code == cohort.school_code))
        surveys = list(s.scalars(
            select(Survey).where(Survey.cohort_id == cohort.cohort_id).order_by(Survey.display_order)
        ))
        cohort_data = {
            "name": cohort.name,
            "description": cohort.description,
            "school_code": cohort.school_code,
            "batch_number": cohort.batch_number,
            "created_at": cohort.created_at,
            "expires_at": cohort.expires_at,
            "retired_at": cohort.retired_at,
        }
        school_data = {
            "code": school.school_code,
            "name": school.name,
            "district": school.district,
        } if school else None
        survey_data = [
            {"slug": sv.slug, "title": sv.title, "intro": sv.intro}
            for sv in surveys
        ]

    return TEMPLATES.TemplateResponse(
        "public/cohort.html",
        _ctx(
            request,
            cohort=cohort_data,
            school=school_data,
            surveys=survey_data,
            breadcrumb=[{"label": cohort_name}],
        ),
    )


@router.post("/r/")
def redeem_form(request: Request, code: str = Form(...)) -> RedirectResponse:
    return RedirectResponse(url=f"/r/{normalize_code(code)}?src=manual", status_code=303)


@router.get("/r/{code_str}")
def redeem(request: Request, code_str: str, src: str = "manual") -> RedirectResponse:
    code_str = normalize_code(code_str)
    client_ip = request.client.host if request.client else "0.0.0.0"
    if not allow_redemption(client_ip):
        raise HTTPException(status_code=429, detail="too many code attempts")

    with session_scope() as s:
        code = s.scalar(select(Code).where(Code.code_str == code_str))
        if code is None:
            raise HTTPException(status_code=404, detail="code not found")
        cohort = s.scalar(select(Cohort).where(Cohort.cohort_id == code.cohort_id))
        if cohort is None or cohort.retired_at is not None:
            raise HTTPException(status_code=410, detail="cohort retired")
        if code.first_used_at is None:
            code.first_used_at = datetime.now(UTC)
        code_id = code.code_id

    sid = mint_session(code_id)
    resp = RedirectResponse(url=f"/survey?src={src}", status_code=303)
    settings = get_settings()
    resp.set_cookie(
        "ting_session", sid,
        httponly=True, samesite="lax",
        secure=settings.environment not in ("dev", "test"),
        max_age=24 * 3600,
    )
    return resp
