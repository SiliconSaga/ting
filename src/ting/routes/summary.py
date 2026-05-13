# src/ting/routes/summary.py
import json
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from ..config import get_settings
from ..db import session_scope
from ..models import Cohort, Survey
from ..services.summary_service import build_summary
from ..valkey import get_valkey

router = APIRouter()
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


SUMMARY_CACHE_TTL = 60


def _available_cohorts_and_surveys() -> tuple[list[dict], str | None]:
    """Return [{cohort, surveys: [{slug, title}]}, ...] and the default cohort name."""
    with session_scope() as s:
        cohorts = list(s.scalars(
            select(Cohort).where(Cohort.retired_at.is_(None)).order_by(Cohort.name)
        ))
        out = []
        for c in cohorts:
            svs = list(s.scalars(
                select(Survey).where(Survey.cohort_id == c.cohort_id).order_by(Survey.display_order)
            ))
            out.append({
                "name": c.name,
                "school_code": c.school_code,
                "batch_number": c.batch_number,
                "surveys": [{"slug": sv.slug, "title": sv.title} for sv in svs],
            })
        default = out[0]["name"] if out else None
        return out, default


@router.get("/summary", response_class=HTMLResponse)
def summary(
    request: Request,
    cohort: str | None = None,
    survey: str | None = None,
    grade: int | None = None,
    print: bool = False,
) -> HTMLResponse:
    nav, default_cohort = _available_cohorts_and_surveys()

    if cohort is None:
        cohort = default_cohort or ""
    if survey is None:
        for c in nav:
            if c["name"] == cohort and c["surveys"]:
                survey = c["surveys"][0]["slug"]
                break
        survey = survey or ""

    # `grade or 'all'` would treat grade=0 (Kindergarten) as unfiltered;
    # check for None explicitly so each grade slice gets its own cache.
    grade_key = "all" if grade is None else str(grade)
    cache_key = f"summary:{cohort}:{survey}:{grade_key}"
    vk = get_valkey()
    cached = vk.get(cache_key)
    if cached:
        data = json.loads(cached)
    else:
        data = build_summary(cohort_name=cohort, survey_slug=survey, grade_filter=grade)
        vk.setex(cache_key, SUMMARY_CACHE_TTL, json.dumps(data, default=str))

    s = get_settings()
    breadcrumb = [{"label": "Survey results"}]
    if cohort:
        breadcrumb.append({"label": cohort, "href": f"/cohort/{cohort}"})

    return TEMPLATES.TemplateResponse(
        "summary/index.html",
        {
            "request": request,
            "data": data,
            "print_mode": print,
            "goatcounter_site_code": s.goatcounter_site_code,
            "nav": nav,
            "selected_cohort": cohort,
            "selected_survey": survey,
            "breadcrumb": breadcrumb,
        },
    )
