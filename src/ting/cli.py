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
    """Load proposals + questions + cohort from a YAML file."""
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
    prefix: str = typer.Option("MPE", "--prefix"),
) -> None:
    from .services.code_service import generate_codes
    out = generate_codes(cohort_name=cohort, count=count, prefix=prefix or None)
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


if __name__ == "__main__":
    app()
