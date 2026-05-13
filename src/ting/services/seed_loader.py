from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select

from ..db import session_scope
from ..models import Bulletin, Cohort, Proposal, Question, School, Survey


class SeedError(Exception):
    pass


def load_seed(path: Path, dry_run: bool = False) -> dict[str, int]:
    data = yaml.safe_load(path.read_text())
    _validate(data)

    counts: dict[str, int] = {
        "schools": 0, "cohort": 0, "proposals": 0,
        "surveys": 0, "questions": 0, "bulletins": 0,
    }

    if dry_run:
        return counts

    with session_scope() as s:
        # Schools upsert by code
        for sc in data.get("schools", []):
            school = s.scalar(select(School).where(School.school_code == sc["code"]))
            if school is None:
                school = School(
                    school_code=sc["code"],
                    name=sc["name"],
                    district=sc["district"],
                )
                s.add(school)
            else:
                school.name = sc["name"]
                school.district = sc["district"]
            counts["schools"] += 1
        s.flush()

        # Cohort upsert by name
        cdata = data["cohort"]
        # Validate school_code exists
        school_code = cdata["school_code"]
        school = s.scalar(select(School).where(School.school_code == school_code))
        if school is None:
            raise SeedError(f"cohort references unknown school_code: {school_code!r}")

        cohort = s.scalar(select(Cohort).where(Cohort.name == cdata["name"]))
        if cohort is None:
            cohort = Cohort(
                name=cdata["name"],
                description=cdata.get("description"),
                school_code=school_code,
                batch_number=int(cdata["batch_number"]),
                expires_at=cdata.get("expires_at"),
            )
            s.add(cohort)
            s.flush()
        else:
            cohort.description = cdata.get("description", cohort.description)
            cohort.school_code = school_code
            cohort.batch_number = int(cdata["batch_number"])
            cohort.expires_at = cdata.get("expires_at", cohort.expires_at)
        counts["cohort"] = 1

        # Proposals upsert by slug
        for p in data.get("proposals", []):
            prop = s.scalar(select(Proposal).where(Proposal.slug == p["slug"]))
            if prop is None:
                prop = Proposal(
                    slug=p["slug"], title=p["title"],
                    body=p.get("body", ""), status=p.get("status", "active"),
                )
                s.add(prop)
            else:
                prop.title = p["title"]
                prop.body = p.get("body", prop.body)
                prop.status = p.get("status", prop.status)
            counts["proposals"] += 1
        s.flush()

        # Surveys upsert by slug; questions inside each survey upsert by slug
        for sv in data.get("surveys", []):
            survey = s.scalar(select(Survey).where(Survey.slug == sv["slug"]))
            if survey is None:
                survey = Survey(
                    slug=sv["slug"],
                    title=sv["title"],
                    intro=sv.get("intro", ""),
                    cohort_id=cohort.cohort_id,
                    display_order=sv.get("display_order", 0),
                )
                s.add(survey)
                s.flush()
            else:
                survey.title = sv["title"]
                survey.intro = sv.get("intro", survey.intro)
                survey.cohort_id = cohort.cohort_id
                survey.display_order = sv.get("display_order", survey.display_order)
            counts["surveys"] += 1

            for q in sv.get("questions", []):
                ques = s.scalar(select(Question).where(Question.slug == q["slug"]))
                if ques is None:
                    ques = Question(
                        slug=q["slug"], type=q["type"], prompt=q["prompt"],
                        payload=q.get("payload", {}),
                        display_order=q.get("display_order"),
                        survey_id=survey.survey_id,
                    )
                    s.add(ques)
                else:
                    ques.type = q["type"]
                    ques.prompt = q["prompt"]
                    ques.payload = q.get("payload", {})
                    ques.display_order = q.get("display_order")
                    ques.survey_id = survey.survey_id
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
    cohort = data["cohort"]
    if "school_code" not in cohort:
        raise SeedError("cohort.school_code is required")
    if "batch_number" not in cohort:
        raise SeedError("cohort.batch_number is required")
    for sv in data.get("surveys", []):
        if "slug" not in sv:
            raise SeedError("survey missing slug")
        if "title" not in sv:
            raise SeedError(f"survey {sv.get('slug')}: title is required")
        for q in sv.get("questions", []):
            if q.get("type") not in ("ranking", "nps", "likert"):
                raise SeedError(f"question {q.get('slug')}: invalid type {q.get('type')!r}")
