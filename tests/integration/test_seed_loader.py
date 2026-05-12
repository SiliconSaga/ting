import pytest
from pathlib import Path
from ting.services.seed_loader import load_seed, SeedError
from ting.db import session_scope
from ting.models import School, Cohort, Proposal, Survey, Question, Bulletin


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
        assert s.query(School).filter_by(school_code="MPE").count() == 1
        assert s.query(Cohort).filter_by(name="MPE-2026-spring-pilot").count() == 1
        assert s.query(Survey).count() == 2
        assert s.query(Proposal).count() == 4
        assert s.query(Question).count() == 9
        assert s.query(Bulletin).count() == 1


def test_load_seed_idempotent():
    load_seed(Path("seeds/example.yaml"))
    load_seed(Path("seeds/example.yaml"))
    with session_scope() as s:
        # Cohort + proposals + surveys + questions deduped by slug/name; bulletins append.
        assert s.query(School).filter_by(school_code="MPE").count() == 1
        assert s.query(Cohort).filter_by(name="MPE-2026-spring-pilot").count() == 1
        assert s.query(Survey).count() == 2
        assert s.query(Proposal).count() == 4
        assert s.query(Question).count() == 9
        assert s.query(Bulletin).count() == 2  # appended


def test_load_seed_validation_error(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("cohort: {}\n")  # missing name
    with pytest.raises(SeedError):
        load_seed(bad)


def test_load_seed_missing_school_code(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("cohort:\n  name: foo\n  batch_number: 1\n")
    with pytest.raises(SeedError):
        load_seed(bad)
