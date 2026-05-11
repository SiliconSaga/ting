import pytest
from pathlib import Path
from ting.services.seed_loader import load_seed, SeedError
from ting.db import session_scope
from ting.models import Cohort, Proposal, Question, Bulletin


@pytest.fixture(autouse=True)
def schema_only(settings_env):
    from ting.models import Base
    from ting.db import get_engine
    Base.metadata.create_all(get_engine())
    yield
    Base.metadata.drop_all(get_engine())


def test_load_example_seed():
    load_seed(Path("seeds/example.yaml"))
    with session_scope() as s:
        assert s.query(Cohort).filter_by(name="example-pilot").count() == 1
        assert s.query(Proposal).count() == 2
        assert s.query(Question).count() == 3
        assert s.query(Bulletin).count() == 1


def test_load_seed_idempotent():
    load_seed(Path("seeds/example.yaml"))
    load_seed(Path("seeds/example.yaml"))
    with session_scope() as s:
        # Cohort + proposals + questions deduped by slug/name; bulletins append.
        assert s.query(Cohort).filter_by(name="example-pilot").count() == 1
        assert s.query(Proposal).count() == 2
        assert s.query(Question).count() == 3
        assert s.query(Bulletin).count() == 2  # appended


def test_load_seed_validation_error(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("cohort: {}\n")  # missing name
    with pytest.raises(SeedError):
        load_seed(bad)
