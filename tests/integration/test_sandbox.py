"""Integration tests for the sandbox page + echo endpoint.

These exercise the full app stack (templates, routing, validation) without
touching the survey persistence path.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(settings_env):
    from ting.app import create_app
    from ting.db import get_engine
    from ting.models import Base
    Base.metadata.create_all(get_engine())
    with TestClient(create_app()) as c:
        yield c
    Base.metadata.drop_all(get_engine())


def test_sandbox_index_renders(client):
    r = client.get("/sandbox")
    assert r.status_code == 200
    # Hero + intro
    assert "Sandbox" in r.text
    # Section per registered question type — keyed off the data-testid the
    # template emits, so this test breaks loudly if the iteration ever
    # silently drops a type.
    for slug in ("ranking", "nps", "likert"):
        assert f'data-testid="section-{slug}"' in r.text
    # Activity log container + reset button
    assert 'id="sandbox-log"' in r.text
    assert 'data-testid="sandbox-reset"' in r.text
    # noindex hint
    assert 'name="robots"' in r.text


def test_sandbox_index_no_real_respond_urls(client):
    """In sandbox mode the widgets must POST to /sandbox/echo, not /respond."""
    body = client.get("/sandbox").text
    assert "/sandbox/echo" in body
    # The fully-qualified real path must not appear (data attributes
    # holding the slug name are fine, but `hx-post="/respond/...` would
    # indicate the sandbox flag failed to thread through a partial).
    assert 'hx-post="/respond/' not in body


def test_robots_disallows_sandbox(client):
    r = client.get("/robots.txt")
    assert r.status_code == 200
    assert "Disallow: /sandbox" in r.text


def test_echo_ranking(client):
    r = client.post(
        "/sandbox/echo",
        data={"question_slug": "sandbox-ranking", "question_type": "ranking",
              "order": "alpha,beta,gamma"},
    )
    assert r.status_code == 200
    # OOB swap target so the log gets prepended
    assert 'hx-swap-oob="afterbegin"' in r.text
    assert 'data-testid="log-entry"' in r.text
    assert "Order:" in r.text
    assert "alpha" in r.text and "gamma" in r.text


def test_echo_nps(client):
    r = client.post(
        "/sandbox/echo",
        data={"question_slug": "sandbox-nps", "question_type": "nps", "score": "8"},
    )
    assert r.status_code == 200
    assert "8" in r.text


def test_echo_likert(client):
    r = client.post(
        "/sandbox/echo",
        data={"question_slug": "sandbox-likert", "question_type": "likert", "score": "5"},
    )
    assert r.status_code == 200
    assert "Strongly agree" in r.text


def test_echo_unknown_type_rejected(client):
    r = client.post(
        "/sandbox/echo",
        data={"question_slug": "x", "question_type": "freetext", "text": "hi"},
    )
    assert r.status_code == 400


def test_echo_bad_nps_score_rejected(client):
    r = client.post(
        "/sandbox/echo",
        data={"question_slug": "x", "question_type": "nps", "score": "42"},
    )
    assert r.status_code == 400


def test_echo_missing_fields_rejected(client):
    r = client.post("/sandbox/echo", data={})
    assert r.status_code == 400


def test_partials_respect_sandbox_false_in_real_survey(client):
    """When a real respondent loads /survey/<slug>, the partials must
    point at /respond/<slug>, not /sandbox/echo. Smoke-tests that the
    sandbox flag default is False everywhere outside the sandbox route."""
    import re
    from pathlib import Path

    from ting.services.code_service import generate_codes
    from ting.services.seed_loader import load_seed

    load_seed(Path("seeds/example.yaml"))
    [code] = generate_codes(cohort_name="MPE-2026-spring-pilot", count=1)
    r = client.get(f"/r/{code}", follow_redirects=False)
    assert r.status_code == 303
    # Pick whichever survey the seed produces first; we just need a page
    # that includes the partials.
    surveys = client.get("/survey").text
    # Pull a survey slug from the picker's HTML — they're rendered as
    # links like `/survey/<slug>`.
    match = re.search(r'href="/survey/([\w-]+)"', surveys)
    assert match, "survey picker did not render any survey link"
    slug = match.group(1)
    page = client.get(f"/survey/{slug}").text
    assert "/respond/" in page
    assert "/sandbox/echo" not in page
