import time

from ting.ratelimit import allow_redemption, allow_write, ip_hash


def test_ip_hash_stable(settings_env):
    h1 = ip_hash("192.0.2.1")
    h2 = ip_hash("192.0.2.1")
    assert h1 == h2
    assert h1 != ip_hash("192.0.2.2")


def test_redemption_limit(settings_env, monkeypatch):
    monkeypatch.setenv("TING_RATE_LIMIT_REDEMPTION_PER_HOUR", "3")
    from ting.config import get_settings
    get_settings.cache_clear()
    ip = f"test-{time.time()}"
    for i in range(3):
        assert allow_redemption(ip) is True, f"attempt {i+1} should pass"
    assert allow_redemption(ip) is False  # 4th blocked


def test_write_limit(settings_env, monkeypatch):
    monkeypatch.setenv("TING_RATE_LIMIT_WRITES_PER_5MIN", "2")
    from ting.config import get_settings
    get_settings.cache_clear()
    code_id = f"code-{time.time()}"
    assert allow_write(code_id) is True
    assert allow_write(code_id) is True
    assert allow_write(code_id) is False
