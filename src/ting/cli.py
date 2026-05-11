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


if __name__ == "__main__":
    app()
