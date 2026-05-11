from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .config import get_settings
from .routes.public import router as public_router
from .routes.survey import router as survey_router
from .routes.summary import router as summary_router


def create_app() -> FastAPI:
    settings = get_settings()  # noqa: F841
    app = FastAPI(title="ting", version="0.1.0")
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    app.include_router(public_router)
    app.include_router(survey_router)
    app.include_router(summary_router)
    return app


# Module-level singleton for uvicorn: `uvicorn ting.app:app`
# Guarded so test collection (where env vars are unset) doesn't fail on import.
try:
    app = create_app()
except Exception:  # ValidationError if required env vars missing
    app = FastAPI(title="ting", version="0.1.0")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:  # type: ignore[misc]
        return {"status": "ok"}
