# tests/integration/test_public_routes.py
import pytest
from pathlib import Path
from fastapi.testclient import TestClient


@pytest.fixture
def client(settings_env):
    from ting.app import create_app
    from ting.models import Base
    from ting.db import get_engine
    Base.metadata.create_all(get_engine())
    yield TestClient(create_app())
    Base.metadata.drop_all(get_engine())


def test_landing_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Enter your code" in r.text


def test_privacy_renders(client):
    r = client.get("/privacy")
    assert r.status_code == 200
    assert "No accounts" in r.text


def test_redeem_404(client):
    r = client.get("/r/NOPE-NOPE-NOPE", follow_redirects=False)
    assert r.status_code == 404


def test_redeem_happy_path(client):
    from ting.services.seed_loader import load_seed
    from ting.services.code_service import generate_codes
    load_seed(Path("seeds/example.yaml"))
    codes = generate_codes(cohort_name="MPE-2026-spring-pilot", count=1)
    r = client.get(f"/r/{codes[0]}", follow_redirects=False)
    assert r.status_code == 303
    assert "/survey" in r.headers["location"]
    assert "ting_session" in r.cookies
