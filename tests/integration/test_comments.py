# tests/integration/test_comments.py
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
    [code] = generate_codes(cohort_name="example-pilot", count=1, prefix="T")
    c = TestClient(create_app())
    c.get(f"/r/{code}", follow_redirects=False)  # redeem
    yield c


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
    from ting.config import get_settings; get_settings.cache_clear()
    for i in range(2):
        r = client.post("/proposal/retain-paras/comment",
                        data={"body": f"c{i}", "confirm_read": "true"})
        assert r.status_code == 200
    r = client.post("/proposal/retain-paras/comment",
                    data={"body": "c3", "confirm_read": "true"})
    assert r.status_code == 403
