import pytest
from ting.services.code_service import generate_codes, list_codes, retire_cohort
from ting.services.seed_loader import load_seed
from pathlib import Path


@pytest.fixture(autouse=True)
def schema_only(settings_env):
    from ting.models import Base
    from ting.db import get_engine
    Base.metadata.create_all(get_engine())
    yield
    Base.metadata.drop_all(get_engine())


def test_generate_codes_count():
    load_seed(Path("seeds/example.yaml"))
    codes = generate_codes(cohort_name="example-pilot", count=10, prefix="EX")
    assert len(codes) == 10
    assert all(c.startswith("EX-") for c in codes)


def test_list_codes_filters_unprinted():
    load_seed(Path("seeds/example.yaml"))
    generate_codes(cohort_name="example-pilot", count=3, prefix="EX")
    unprinted = list_codes(cohort_name="example-pilot", only_unprinted=True)
    assert len(unprinted) == 3
