import typer
from pathlib import Path

app = typer.Typer(no_args_is_help=True, help="Ting admin CLI")


@app.command()
def healthcheck() -> None:
    """Check DB / Valkey connectivity + print version."""
    from .config import get_settings

    s = get_settings()
    typer.echo(f"ting v0.1.0 environment={s.environment}")
    typer.echo(f"database_url={s.database_url}")
    typer.echo(f"valkey_url={s.valkey_url}")


@app.command()
def dev(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port"),
    reload: bool = typer.Option(True, "--reload/--no-reload"),
) -> None:
    """Boot uvicorn with hot reload for local development."""
    import uvicorn
    uvicorn.run("ting.app:app", host=host, port=port, reload=reload)


@app.command()
def migrate(direction: str = typer.Argument("up", help="up|down|head")) -> None:
    """Run Alembic migrations."""
    from alembic.config import Config
    from alembic import command

    cfg = Config("alembic.ini")
    if direction in ("up", "head"):
        command.upgrade(cfg, "head")
    elif direction == "down":
        command.downgrade(cfg, "-1")
    else:
        raise typer.BadParameter("direction must be up|down|head")


@app.command()
def seed(
    file: Path = typer.Argument(..., exists=True, dir_okay=False),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without writing"),
) -> None:
    """Load schools + cohort + surveys + questions + proposals from a YAML file."""
    from .services.seed_loader import load_seed, SeedError
    try:
        counts = load_seed(file, dry_run=dry_run)
    except SeedError as e:
        typer.echo(f"seed error: {e}", err=True)
        raise typer.Exit(1)
    label = "(dry-run) would write" if dry_run else "wrote"
    typer.echo(f"{label}: {counts}")


codes_app = typer.Typer(help="Code lifecycle (generate, export, retire)")
app.add_typer(codes_app, name="codes")


@codes_app.command("generate")
def codes_generate(
    cohort: str = typer.Option(..., "--cohort"),
    count: int = typer.Option(..., "--count"),
) -> None:
    """Generate access codes for a cohort. Prefix is derived from school_code + batch_number."""
    from .services.code_service import generate_codes
    out = generate_codes(cohort_name=cohort, count=count)
    typer.echo(f"generated {len(out)} codes for cohort={cohort}")
    for c in out:
        typer.echo(c)


@codes_app.command("export")
def codes_export(
    cohort: str = typer.Option(..., "--cohort"),
    format: str = typer.Option("csv", "--format", help="csv|html"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    only_unprinted: bool = typer.Option(False, "--only-unprinted"),
    out: Path = typer.Option(Path("-"), "--out", help="- = stdout"),
) -> None:
    from .services.code_service import list_codes, export_csv, export_html, mark_printed
    rows = list_codes(cohort_name=cohort, only_unprinted=only_unprinted)
    if format == "csv":
        text = export_csv(codes=rows)
    elif format == "html":
        text = export_html(codes=rows, base_url=base_url)
    else:
        raise typer.BadParameter("format must be csv|html")
    if str(out) == "-":
        typer.echo(text)
    else:
        out.write_text(text)
        typer.echo(f"wrote {len(rows)} codes to {out}")
    mark_printed(code_strs=[r.code_str for r in rows])


@app.command("cohort")
def cohort(action: str, name: str) -> None:
    """Cohort actions. Supports: retire <name>."""
    from .services.code_service import retire_cohort
    if action == "retire":
        retire_cohort(cohort_name=name)
        typer.echo(f"retired cohort {name}")
    else:
        raise typer.BadParameter(f"unknown cohort action: {action}")


@app.command()
def report(
    cohort: str = typer.Option(..., "--cohort"),
    out: Path = typer.Option(Path("summary.html"), "--out"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
) -> None:
    """Save the printable /summary page as HTML (then browser-print to PDF)."""
    import httpx
    r = httpx.get(f"{base_url.rstrip('/')}/summary?cohort={cohort}&print=true", timeout=30)
    r.raise_for_status()
    out.write_text(r.text)
    typer.echo(f"wrote {out}")


bulletins_app = typer.Typer(help="Admin broadcast bulletins")
app.add_typer(bulletins_app, name="bulletin")


@bulletins_app.command("post")
def bulletin_post(
    body: str = typer.Option(..., "--body"),
    posted_by: str = typer.Option("admin", "--as"),
) -> None:
    from .db import session_scope
    from .models import Bulletin
    with session_scope() as s:
        s.add(Bulletin(body=body, posted_by=posted_by))
    typer.echo("bulletin posted")


school_app = typer.Typer(help="School management")
app.add_typer(school_app, name="school")


@school_app.command("add")
def school_add(
    code: str = typer.Option(..., "--code", help="3-char school code e.g. MPE"),
    name: str = typer.Option(..., "--name"),
    district: str = typer.Option(..., "--district"),
) -> None:
    """Add or update a school record."""
    from .db import session_scope
    from .models import School
    from sqlalchemy import select
    with session_scope() as s:
        school = s.scalar(select(School).where(School.school_code == code))
        if school is None:
            s.add(School(school_code=code, name=name, district=district))
            typer.echo(f"added school {code}")
        else:
            school.name = name
            school.district = district
            typer.echo(f"updated school {code}")


survey_app = typer.Typer(help="Survey management")
app.add_typer(survey_app, name="survey")


@survey_app.command("add")
def survey_add(
    cohort: str = typer.Option(..., "--cohort"),
    slug: str = typer.Option(..., "--slug"),
    title: str = typer.Option(..., "--title"),
    intro: str = typer.Option("", "--intro"),
    display_order: int = typer.Option(0, "--display-order"),
) -> None:
    """Add or update a survey for a cohort."""
    from .db import session_scope
    from .models import Cohort, Survey
    from sqlalchemy import select
    with session_scope() as s:
        c = s.scalar(select(Cohort).where(Cohort.name == cohort))
        if c is None:
            typer.echo(f"error: cohort {cohort!r} not found", err=True)
            raise typer.Exit(1)
        sv = s.scalar(select(Survey).where(Survey.slug == slug))
        if sv is None:
            s.add(Survey(slug=slug, title=title, intro=intro,
                         cohort_id=c.cohort_id, display_order=display_order))
            typer.echo(f"added survey {slug}")
        else:
            sv.title = title
            sv.intro = intro
            sv.cohort_id = c.cohort_id
            sv.display_order = display_order
            typer.echo(f"updated survey {slug}")


@app.command()
def snapshot() -> None:
    """For each active cohort x survey pair, capture a summary snapshot (idempotent per minute)."""
    from datetime import timedelta
    from sqlalchemy import select, func
    from .db import session_scope
    from .models import Cohort, Survey, SummarySnapshot
    from .services.summary_service import build_summary
    from .models.base import utcnow

    saved = 0
    skipped = 0

    with session_scope() as s:
        cohorts = list(s.scalars(select(Cohort).where(Cohort.retired_at.is_(None))))
        for cohort in cohorts:
            surveys = list(s.scalars(select(Survey).where(Survey.cohort_id == cohort.cohort_id)))
            for sv in surveys:
                # Check if a snapshot was taken within the last 60 seconds
                cutoff = utcnow() - timedelta(seconds=60)
                recent = s.scalar(
                    select(func.count(SummarySnapshot.snapshot_id))
                    .where(
                        SummarySnapshot.cohort_id == cohort.cohort_id,
                        SummarySnapshot.survey_id == sv.survey_id,
                        SummarySnapshot.captured_at >= cutoff,
                    )
                )
                if recent:
                    skipped += 1
                    continue
                payload = build_summary(cohort_name=cohort.name, survey_slug=sv.slug)
                s.add(SummarySnapshot(
                    cohort_id=cohort.cohort_id,
                    survey_id=sv.survey_id,
                    payload=payload,
                ))
                saved += 1

    typer.echo(f"snapshot: saved={saved} skipped={skipped}")


demo_app = typer.Typer(help="Demo data population")
app.add_typer(demo_app, name="demo")


@demo_app.command("populate")
def demo_populate(
    cohort: str = typer.Option(..., "--cohort"),
    count: int = typer.Option(..., "--count"),
) -> None:
    """Generate N codes and synthesize realistic responses across all surveys in the cohort."""
    import random
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from .db import session_scope
    from .models import Cohort, Survey, Question, Response, Comment, Endorsement, Pledge, Proposal
    from .services.code_service import generate_codes
    from datetime import UTC

    CANNED_COMMENTS = [
        "We strongly support keeping staff in-house.",
        "HVAC has been a long-standing issue — please address it.",
        "Transparent budget process is most important to us.",
        "More community engagement before decisions are made.",
        "We appreciate the board's efforts but need faster action.",
        "Cost savings should not come at the expense of our children.",
        "Staff retention directly impacts student outcomes.",
        "We trust the school administration to make good choices.",
        "Parent input should be formal, not just advisory.",
        "Supplemental funding could bridge the gap responsibly.",
    ]

    with session_scope() as s:
        c = s.scalar(select(Cohort).where(Cohort.name == cohort))
        if c is None:
            typer.echo(f"error: cohort {cohort!r} not found", err=True)
            raise typer.Exit(1)

        surveys = list(s.scalars(select(Survey).where(Survey.cohort_id == c.cohort_id)))
        if not surveys:
            typer.echo(f"error: no surveys found for cohort {cohort!r}", err=True)
            raise typer.Exit(1)

        proposals = list(s.scalars(select(Proposal)))

    # Generate codes (outside the session to avoid detached-instance issues)
    code_strs = generate_codes(cohort_name=cohort, count=count)
    typer.echo(f"generated {len(code_strs)} codes")

    with session_scope() as s:
        from .models import Code
        c = s.scalar(select(Cohort).where(Cohort.name == cohort))
        codes = list(s.scalars(select(Code).where(
            Code.cohort_id == c.cohort_id,
            Code.code_str.in_(code_strs),
        )))
        surveys = list(s.scalars(select(Survey).where(Survey.cohort_id == c.cohort_id)))
        proposals = list(s.scalars(select(Proposal)))

        comments_added: list[Comment] = []

        for code in codes:
            # Synthesize responses per survey
            for sv in surveys:
                questions = list(s.scalars(
                    select(Question).where(Question.survey_id == sv.survey_id)
                ))
                for q in questions:
                    payload: dict = {}
                    if q.type == "ranking":
                        slugs = list(q.payload.get("proposal_slugs", []))
                        # mild positional bias: shuffle then swap first two with 30% chance
                        random.shuffle(slugs)
                        if len(slugs) >= 2 and random.random() < 0.3:
                            slugs[0], slugs[1] = slugs[1], slugs[0]
                        payload = {"order": slugs}
                    elif q.type == "nps":
                        subject = q.payload.get("subject", "")
                        subj_lower = subject.lower()
                        if any(k in subj_lower for k in ("board", "district", "admin")):
                            score = max(0, min(10, int(random.gauss(6, 2))))
                        else:
                            score = max(0, min(10, int(random.gauss(8, 1.5))))
                        payload = {"score": score}
                    elif q.type == "likert":
                        score = max(1, min(5, round(random.gauss(3.5, 1))))
                        payload = {"score": score}

                    stmt = pg_insert(Response).values(
                        code_id=code.code_id,
                        question_id=q.question_id,
                        payload=payload,
                    ).on_conflict_do_nothing()
                    s.execute(stmt)

            # Random comments (0-2 per code)
            if proposals:
                n_comments = random.randint(0, 2)
                for _ in range(n_comments):
                    body = random.choice(CANNED_COMMENTS)
                    prop = random.choice(proposals)
                    cm = Comment(proposal_id=prop.proposal_id, author_code_id=code.code_id, body=body)
                    s.add(cm)
                    s.flush()
                    comments_added.append(cm)

        s.flush()

        # Endorsements: each code endorses 0-3 existing comments
        for code in codes:
            if not comments_added:
                break
            n_endorse = random.randint(0, min(3, len(comments_added)))
            sample = random.sample(comments_added, n_endorse)
            for cm in sample:
                if cm.author_code_id == code.code_id:
                    continue  # skip self-endorsements
                from sqlalchemy.exc import IntegrityError
                try:
                    s.add(Endorsement(code_id=code.code_id, comment_id=cm.comment_id))
                    s.flush()
                except Exception:
                    s.rollback()

        # Pledges: 30% of codes pledge
        for code in codes:
            if random.random() > 0.3:
                continue
            if not proposals:
                continue
            prop = random.choice(proposals)
            # exponential dollars 5-100
            dollars = min(100.0, max(5.0, random.expovariate(1 / 25)))
            # uniform hours 0.5-4
            hours = round(random.uniform(0.5, 4.0), 1)
            stmt = pg_insert(Pledge).values(
                code_id=code.code_id,
                proposal_id=prop.proposal_id,
                amount_dollars=round(dollars, 2),
                hours_per_week=hours,
            ).on_conflict_do_nothing()
            s.execute(stmt)

    typer.echo(f"demo populate: {count} codes with synthetic responses for cohort={cohort}")


if __name__ == "__main__":
    app()
