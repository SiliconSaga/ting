# tests/integration/test_comments.py
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ting.config import get_settings


@pytest.fixture
def client(settings_env):
    from ting.app import create_app
    from ting.db import get_engine
    from ting.models import Base
    Base.metadata.create_all(get_engine())
    from ting.services.code_service import generate_codes
    from ting.services.seed_loader import load_seed
    load_seed(Path("seeds/example.yaml"))
    [code] = generate_codes(cohort_name="MPE-2026-spring-pilot", count=1)
    with TestClient(create_app()) as c:
        c.get(f"/r/{code}", follow_redirects=False)  # redeem
        yield c
    Base.metadata.drop_all(get_engine())


def test_post_comment_requires_confirm_read(client):
    r = client.post("/proposal/retain-paras/comment", data={"body": "hello"})
    assert r.status_code == 400


def test_post_comment_ok(client):
    r = client.post("/proposal/retain-paras/comment",
                    data={"body": "hello", "confirm_read": "true"})
    assert r.status_code == 200
    r2 = client.get("/proposal/retain-paras")
    assert "hello" in r2.text


def test_comment_cap(client, monkeypatch):
    monkeypatch.setenv("TING_MAX_COMMENTS_PER_CODE", "2")
    get_settings.cache_clear()
    for i in range(2):
        r = client.post("/proposal/retain-paras/comment",
                        data={"body": f"c{i}", "confirm_read": "true"})
        assert r.status_code == 200
    r = client.post("/proposal/retain-paras/comment",
                    data={"body": "c3", "confirm_read": "true"})
    assert r.status_code == 403
