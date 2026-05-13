from ting.valkey import get_valkey


def test_valkey_ping(monkeypatch):
    monkeypatch.setenv("TING_DATABASE_URL", "postgresql://u:p@h:5432/d")
    monkeypatch.setenv("TING_VALKEY_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("TING_SESSION_SECRET", "x" * 32)
    from ting.config import get_settings
    get_settings.cache_clear()
    vk = get_valkey()
    assert vk.ping() is True
