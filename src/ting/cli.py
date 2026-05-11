import typer

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
def dev() -> None:
    """Boot the app via uvicorn against dev-tier services (hot reload)."""
    import subprocess
    import sys

    subprocess.run(
        [sys.executable, "-m", "uvicorn", "ting.app:app", "--reload", "--port", "8000"],
        check=True,
    )


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


if __name__ == "__main__":
    app()
