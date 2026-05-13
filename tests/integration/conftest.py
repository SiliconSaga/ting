import os

import pytest
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def postgres_url():
    """Return a Postgres connection URL for the test session.

    In CI the runner provides a service container and exports
    TING_DATABASE_URL before pytest starts.  When that variable is
    already set we reuse it directly so testcontainers never tries to
    spin up a second container.  Locally (no env var) we launch one via
    testcontainers as before.
    """
    pre_set = os.environ.get("TING_DATABASE_URL")
    if pre_set:
        yield pre_set
        return
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql+psycopg://")


@pytest.fixture
def settings_env(monkeypatch, postgres_url):
    monkeypatch.setenv("TING_DATABASE_URL", postgres_url)
    monkeypatch.setenv("TING_VALKEY_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("TING_SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("TING_ENVIRONMENT", "test")
    from ting.config import get_settings
    from ting.db import _session_factory, get_engine
    from ting.valkey import get_valkey
    get_settings.cache_clear()
    get_engine.cache_clear()
    _session_factory.cache_clear()
    get_valkey.cache_clear()
    # Flush rate-limit and session keys so tests don't bleed into each other.
    # Use the same URL the rest of the suite sees — falls back to the local
    # default when no override is set so this works both locally and in CI.
    import redis
    vk = redis.from_url(
        os.environ.get("TING_VALKEY_URL", "redis://localhost:6379/0"),
        decode_responses=True,
    )
    for pattern in ("rl:*", "sess:*", "survey:*", "summary:*"):
        keys = vk.keys(pattern)
        if keys:
            vk.delete(*keys)
    yield
    get_settings.cache_clear()
    get_engine.cache_clear()
    _session_factory.cache_clear()
    get_valkey.cache_clear()
