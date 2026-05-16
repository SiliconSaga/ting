import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: F401
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import get_settings
from .routes.public import router as public_router
from .routes.sandbox import router as sandbox_router
from .routes.summary import router as summary_router
from .routes.survey import router as survey_router

_STATUS_COPY = {
    400: ("Something's off",
          "We couldn't make sense of that request. Try again, or head back to the start."),
    401: ("Sign in to continue",
          "This page needs an active session. Enter your code on the start page to continue."),
    404: ("We couldn't find that",
          "We couldn't find that code or page. Check the code you entered (codes "
          "look like ABCD-1234-WXYZ) or scan the QR from your envelope."),
    410: ("This cohort has ended",
          "This pilot cohort has closed. New codes will arrive in the next round; your past answers are preserved."),
    429: ("Slow down a moment",
          "Too many attempts in a short time. Wait a few minutes and try again."),
    500: ("Something went wrong on our end",
          "Unexpected error. Please try again. If it keeps happening, reach out at volunteer@frontstate.org."),
}


def _error_copy(status_code: int) -> tuple[str, str]:
    return _STATUS_COPY.get(status_code, ("Error", "An unexpected error occurred."))


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="ting", version="0.1.0")
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.exception_handler(StarletteHTTPException)
    async def html_or_json_http_handler(request: Request, exc: StarletteHTTPException):
        accept = request.headers.get("accept", "")
        # JSON for fetch/HTMX/CLI; HTML for browser top-level navigation.
        if "text/html" not in accept:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        label, message = _error_copy(exc.status_code)
        return templates.TemplateResponse(
            "public/error.html",
            {
                "request": request,
                "status_code": exc.status_code,
                "status_label": label,
                "message": message,
                "show_privacy": True,
                "goatcounter_site_code": settings.goatcounter_site_code,
                "breadcrumb": [{"label": f"Error {exc.status_code}"}],
            },
            status_code=exc.status_code,
        )

    app.include_router(public_router)
    app.include_router(survey_router)
    app.include_router(summary_router)
    app.include_router(sandbox_router)
    return app


# Module-level singleton for uvicorn: `uvicorn ting.app:app`.
# Tests import this module before pytest's monkeypatch sets env vars, so
# we only construct the app when configuration is actually present. In
# production, k8s injects TING_DATABASE_URL via the ting-secrets Secret;
# if that env var is missing OR the resulting Settings fail validation,
# we let the error propagate so uvicorn fails loudly instead of serving
# a degraded healthz-only app that looks healthy to k8s probes.
if "TING_DATABASE_URL" in os.environ:
    app = create_app()
else:
    app = None  # type: ignore[assignment]
