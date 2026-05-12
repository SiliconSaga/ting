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
    [code] = generate_codes(cohort_name="MPE-2026-spring-pilot", count=1)
    r = client.get(f"/r/{code}", follow_redirects=False)
    assert r.status_code == 303
    return code


def test_survey_list_renders_after_redeem(client):
    _redeem(client)
    r = client.get("/survey")
    assert r.status_code == 200
    assert "Your surveys" in r.text
    # The picker lists both surveys from seeds/example.yaml
    assert "General priorities and trust" in r.text
    assert "Safety + security reaction" in r.text


def test_survey_show_renders(client):
    _redeem(client)
    r = client.get("/survey/spring-pilot-general")
    assert r.status_code == 200
    assert "General priorities and trust" in r.text
    # nav strip shows the other survey too
    assert "Safety + security reaction" in r.text


def test_respond_likert_persists(client):
    _redeem(client)
    r = client.post("/respond/agree-supp-funding", data={"score": 4})
    assert r.status_code == 200
    # Re-render the specific survey page and check the radio is checked
    r2 = client.get("/survey/spring-pilot-general")
    assert 'value="4" checked' in r2.text


def test_respond_unauth(client):
    r = client.post("/respond/agree-supp-funding", data={"score": 4})
    assert r.status_code == 401
