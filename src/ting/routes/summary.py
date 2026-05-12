# src/ting/routes/summary.py
import json
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import select

from ..db import session_scope
from ..models import Cohort, Survey
from ..services.summary_service import build_summary
from ..valkey import get_valkey
from ..config import get_settings


router = APIRouter()
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


SUMMARY_CACHE_TTL = 60


def _first_survey_slug(cohort_name: str) -> str | None:
    with session_scope() as s:
        cohort = s.scalar(select(Cohort).where(Cohort.name == cohort_name))
        if cohort is None:
            return None
        sv = s.scalar(
            select(Survey)
            .where(Survey.cohort_id == cohort.cohort_id)
            .order_by(Survey.display_order)
        )
        return sv.slug if sv else None


@router.get("/summary", response_class=HTMLResponse)
def summary(
    request: Request,
    cohort: str = "MPE-2026-spring-pilot",
    survey: str | None = None,
    grade: int | None = None,
    print: bool = False,
) -> HTMLResponse:
    # Default to first survey in cohort if not provided
    if survey is None:
        survey = _first_survey_slug(cohort) or ""

    cache_key = f"summary:{cohort}:{survey}:{grade or 'all'}"
    vk = get_valkey()
    cached = vk.get(cache_key)
    if cached:
        data = json.loads(cached)
    else:
        data = build_summary(cohort_name=cohort, survey_slug=survey, grade_filter=grade)
        vk.setex(cache_key, SUMMARY_CACHE_TTL, json.dumps(data, default=str))

    s = get_settings()
    return TEMPLATES.TemplateResponse(
        "summary/index.html",
        {
            "request": request,
            "data": data,
            "print_mode": print,
            "goatcounter_site_code": s.goatcounter_site_code,
        },
    )
