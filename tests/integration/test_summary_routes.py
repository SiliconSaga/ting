# tests/integration/test_summary_routes.py
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(settings_env):
    from ting.app import create_app
    from ting.db import get_engine
    from ting.models import Base
    Base.metadata.create_all(get_engine())
    from ting.services.seed_loader import load_seed
    load_seed(Path("seeds/example.yaml"))
    with TestClient(create_app()) as c:
        yield c
    Base.metadata.drop_all(get_engine())


def test_summary_renders(client):
    r = client.get("/summary")
    assert r.status_code == 200
    assert "MPE-2026-spring-pilot" in r.text
    assert "Priorities" in r.text


def test_summary_grade_floor(client):
    r = client.get("/summary?grade=2")
    assert r.status_code == 200
    # No codes => slice too small or empty summary
    assert "slice-too-small" in r.text.lower() or "Slice too small" in r.text or "0 respondents" in r.text
