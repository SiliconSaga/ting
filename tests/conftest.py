"""
Root test conftest — shared fixtures and setup for all test layers.
"""
import pytest


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Clear get_settings LRU cache before each test so monkeypatch env vars take effect."""
    from ting.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
