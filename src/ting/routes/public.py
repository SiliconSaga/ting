# src/ting/routes/public.py
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import select
from datetime import datetime, UTC

from ..codes import normalize_code
from ..auth import mint_session
from ..ratelimit import allow_redemption
from ..db import session_scope
from ..models import Code, Cohort
from ..config import get_settings


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
    return TEMPLATES.TemplateResponse("public/landing.html", _ctx(request))


@router.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse("public/privacy.html", _ctx(request))


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
        secure=settings.environment != "dev",
        max_age=24 * 3600,
    )
    return resp
