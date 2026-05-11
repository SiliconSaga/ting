import pytest
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def postgres_url():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql+psycopg://")


@pytest.fixture
def settings_env(monkeypatch, postgres_url):
    monkeypatch.setenv("TING_DATABASE_URL", postgres_url)
    monkeypatch.setenv("TING_VALKEY_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("TING_SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("TING_ENVIRONMENT", "test")
    from ting.config import get_settings
    from ting.db import get_engine, _session_factory
    get_settings.cache_clear()
    get_engine.cache_clear()
    _session_factory.cache_clear()
    yield
    get_settings.cache_clear()
    get_engine.cache_clear()
    _session_factory.cache_clear()
