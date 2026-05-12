# tests/integration/test_pledges.py
import pytest
from pathlib import Path
from fastapi.testclient import TestClient


@pytest.fixture
def client(settings_env):
    from ting.app import create_app
    from ting.models import Base
    from ting.db import get_engine
    Base.metadata.create_all(get_engine())
    from ting.services.seed_loader import load_seed
    from ting.services.code_service import generate_codes
    load_seed(Path("seeds/example.yaml"))
    [code] = generate_codes(cohort_name="MPE-2026-spring-pilot", count=1)
    c = TestClient(create_app())
    c.get(f"/r/{code}", follow_redirects=False)
    yield c


def test_pledge_upserts(client):
    r = client.post("/proposal/retain-paras/pledge",
                    data={"amount_dollars": "25", "hours_per_week": "2"})
    assert r.status_code == 200
    # Re-submit and confirm it replaces (not duplicates) — check summary
    r = client.post("/proposal/retain-paras/pledge",
                    data={"amount_dollars": "50", "hours_per_week": "3"})
    assert r.status_code == 200
    r2 = client.get("/summary")
    assert "$50" in r2.text or "50/mo" in r2.text


def test_pledge_negative_rejected(client):
    r = client.post("/proposal/retain-paras/pledge",
                    data={"amount_dollars": "-1", "hours_per_week": "0"})
    assert r.status_code == 400
