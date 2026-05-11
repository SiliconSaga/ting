# src/ting/routes/summary.py
import json
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from ..services.summary_service import build_summary
from ..valkey import get_valkey
from ..config import get_settings


router = APIRouter()
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


SUMMARY_CACHE_TTL = 60


@router.get("/summary", response_class=HTMLResponse)
def summary(request: Request, cohort: str = "example-pilot", grade: int | None = None, print: bool = False) -> HTMLResponse:
    cache_key = f"summary:{cohort}:{grade or 'all'}"
    vk = get_valkey()
    cached = vk.get(cache_key)
    if cached:
        data = json.loads(cached)
    else:
        data = build_summary(cohort_name=cohort, grade_filter=grade)
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
