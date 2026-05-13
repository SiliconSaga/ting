from ting.config import Settings


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("TING_DATABASE_URL", "postgresql://u:p@h:5432/d")
    monkeypatch.setenv("TING_VALKEY_URL", "redis://h:6379/0")
    monkeypatch.setenv("TING_SESSION_SECRET", "x" * 32)
    s = Settings()
    assert str(s.database_url) == "postgresql://u:p@h:5432/d"
    assert str(s.valkey_url) == "redis://h:6379/0"
    assert s.session_secret == "x" * 32
    assert s.goatcounter_site_code is None
    assert s.base_url == "http://localhost:8000"
    assert s.environment == "dev"


def test_settings_optional_goatcounter(monkeypatch):
    monkeypatch.setenv("TING_DATABASE_URL", "postgresql://u:p@h:5432/d")
    monkeypatch.setenv("TING_VALKEY_URL", "redis://h:6379/0")
    monkeypatch.setenv("TING_SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("TING_GOATCOUNTER_SITE_CODE", "ting-test")
    s = Settings()
    assert s.goatcounter_site_code == "ting-test"
