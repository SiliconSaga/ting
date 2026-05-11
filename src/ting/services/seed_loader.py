from pathlib import Path
from typing import Any
import yaml
from sqlalchemy import select

from ..db import session_scope
from ..models import Cohort, Proposal, Question, Bulletin


class SeedError(Exception):
    pass


def load_seed(path: Path, dry_run: bool = False) -> dict[str, int]:
    data = yaml.safe_load(path.read_text())
    _validate(data)

    counts = {"cohort": 0, "proposals": 0, "questions": 0, "bulletins": 0}

    if dry_run:
        return counts

    with session_scope() as s:
        # Cohort upsert by name
        cdata = data["cohort"]
        cohort = s.scalar(select(Cohort).where(Cohort.name == cdata["name"]))
        if cohort is None:
            cohort = Cohort(name=cdata["name"], description=cdata.get("description"))
            s.add(cohort)
            s.flush()
        else:
            cohort.description = cdata.get("description", cohort.description)
        counts["cohort"] = 1

        # Proposals upsert by slug
        for p in data.get("proposals", []):
            prop = s.scalar(select(Proposal).where(Proposal.slug == p["slug"]))
            if prop is None:
                prop = Proposal(slug=p["slug"], title=p["title"], body=p.get("body", ""), status=p.get("status", "active"))
                s.add(prop)
            else:
                prop.title = p["title"]
                prop.body = p.get("body", prop.body)
                prop.status = p.get("status", prop.status)
            counts["proposals"] += 1
        s.flush()

        # Questions upsert by slug
        for q in data.get("questions", []):
            ques = s.scalar(select(Question).where(Question.slug == q["slug"]))
            if ques is None:
                ques = Question(
                    slug=q["slug"], type=q["type"], prompt=q["prompt"],
                    payload=q.get("payload", {}), display_order=q.get("display_order"),
                    cohort_id=cohort.cohort_id,
                )
                s.add(ques)
            else:
                ques.type = q["type"]
                ques.prompt = q["prompt"]
                ques.payload = q.get("payload", {})
                ques.display_order = q.get("display_order")
                ques.cohort_id = cohort.cohort_id
            counts["questions"] += 1

        # Bulletins append
        for b in data.get("bulletins", []):
            s.add(Bulletin(body=b["body"], posted_by=b.get("posted_by", "seed")))
            counts["bulletins"] += 1

    return counts


def _validate(data: Any) -> None:
    if not isinstance(data, dict):
        raise SeedError("Top-level YAML must be a mapping")
    if "cohort" not in data or not isinstance(data["cohort"], dict) or "name" not in data["cohort"]:
        raise SeedError("cohort.name is required")
    for q in data.get("questions", []):
        if q.get("type") not in ("ranking", "nps", "likert"):
            raise SeedError(f"question {q.get('slug')}: invalid type {q.get('type')!r}")
