from fastapi import FastAPI


def create_app() -> FastAPI:
    from .config import get_settings  # deferred so tests can monkeypatch before calling

    settings = get_settings()  # noqa: F841 – used for future lifespan/middleware config
    app = FastAPI(title="ting", version="0.1.0")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

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
