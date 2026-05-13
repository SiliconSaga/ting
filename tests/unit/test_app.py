from fastapi.testclient import TestClient

from ting.app import create_app


def test_root_returns_200(monkeypatch):
    monkeypatch.setenv("TING_DATABASE_URL", "postgresql://u:p@h:5432/d")
    monkeypatch.setenv("TING_VALKEY_URL", "redis://h:6379/0")
    monkeypatch.setenv("TING_SESSION_SECRET", "x" * 32)
    app = create_app()
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
