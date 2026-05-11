# tests/integration/test_survey_routes.py
import pytest
from pathlib import Path
from fastapi.testclient import TestClient


@pytest.fixture
def client(settings_env):
    from ting.app import create_app
    from ting.models import Base
    from ting.db import get_engine
    Base.metadata.create_all(get_engine())
    return TestClient(create_app())


def _redeem(client) -> str:
    from ting.services.seed_loader import load_seed
    from ting.services.code_service import generate_codes
    load_seed(Path("seeds/example.yaml"))
    [code] = generate_codes(cohort_name="example-pilot", count=1, prefix="T")
    r = client.get(f"/r/{code}", follow_redirects=False)
    assert r.status_code == 303
    return code


def test_survey_renders_after_redeem(client):
    _redeem(client)
    r = client.get("/survey")
    assert r.status_code == 200
    assert "Your input" in r.text


def test_respond_likert_persists(client):
    _redeem(client)
    r = client.post("/respond/agree-supp-funding", data={"score": 4})
    assert r.status_code == 200
    # Re-render and check radio is checked
    r2 = client.get("/survey")
    assert 'value="4" checked' in r2.text


def test_respond_unauth(client):
    r = client.post("/respond/agree-supp-funding", data={"score": 4})
    assert r.status_code == 401
