from pathlib import Path

import pytest

from ting.services.code_service import generate_codes, list_codes
from ting.services.seed_loader import load_seed


@pytest.fixture(autouse=True)
def schema_only(settings_env):
    from ting.db import get_engine
    from ting.models import Base
    Base.metadata.create_all(get_engine())
    yield
    Base.metadata.drop_all(get_engine())


def test_generate_codes_count():
    load_seed(Path("seeds/example.yaml"))
    codes = generate_codes(cohort_name="MPE-2026-spring-pilot", count=10)
    assert len(codes) == 10
    # Prefix derived from school_code="MPE" + batch_number=1 => "MPE01"
    assert all(c.startswith("MPE01-") for c in codes)


def test_list_codes_filters_unprinted():
    load_seed(Path("seeds/example.yaml"))
    generate_codes(cohort_name="MPE-2026-spring-pilot", count=3)
    unprinted = list_codes(cohort_name="MPE-2026-spring-pilot", only_unprinted=True)
    assert len(unprinted) == 3
