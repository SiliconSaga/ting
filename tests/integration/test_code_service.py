from pathlib import Path

import pytest

from ting.services.code_service import generate_codes, list_codes, mark_printed
from ting.services.seed_loader import load_seed

# Anchor to the repo root so the test passes regardless of pytest's cwd.
SEED = Path(__file__).resolve().parents[2] / "seeds" / "example.yaml"


@pytest.fixture(autouse=True)
def schema_only(settings_env):
    from ting.db import get_engine
    from ting.models import Base
    Base.metadata.create_all(get_engine())
    yield
    Base.metadata.drop_all(get_engine())


def test_generate_codes_count():
    load_seed(SEED)
    codes = generate_codes(cohort_name="MPE-2026-spring-pilot", count=10)
    assert len(codes) == 10
    # Prefix derived from school_code="MPE" + batch_number=1 => "MPE01"
    assert all(c.startswith("MPE01-") for c in codes)


def test_list_codes_filters_unprinted():
    load_seed(SEED)
    codes = generate_codes(cohort_name="MPE-2026-spring-pilot", count=3)
    # All three start unprinted
    assert len(list_codes(cohort_name="MPE-2026-spring-pilot", only_unprinted=True)) == 3
    # Mark one printed; verify only_unprinted filter excludes it
    mark_printed(code_strs=[codes[0]])
    assert len(list_codes(cohort_name="MPE-2026-spring-pilot", only_unprinted=True)) == 2
    # And the unfiltered list still has all three
    assert len(list_codes(cohort_name="MPE-2026-spring-pilot")) == 3
