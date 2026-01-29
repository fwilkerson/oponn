#!/usr/bin/env python3
import os
import subprocess
import sys

import typer

app = typer.Typer(help="Oponn Development Tool", add_completion=False)


def run_cmd(command: list[str], env: dict[str, str] | None = None):
    print(f"Running: {' '.join(command)}")
    try:
        _ = subprocess.run(command, check=True, env=env)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


@app.command()
def start():
    """Run the FastAPI application with reload (alias for dev)."""
    dev()


@app.command()
def dev():
    """Run the app in development mode (permissive defaults, reload)."""
    env = os.environ.copy()
    env["OPONN_ENV"] = "development"
    run_cmd([sys.executable, "-m", "uvicorn", "src.main:app", "--reload"], env=env)


@app.command()
def prod(
    workers: int = typer.Option(2, help="Number of Gunicorn workers"),
):
    """Run the app with Gunicorn in production mode (strict dependencies)."""
    # Default to local docker-compose PG if not set
    env = os.environ.copy()
    env["OPONN_ENV"] = "production"

    if "DATABASE_URL" not in env:
        env["DATABASE_URL"] = (
            "postgresql+asyncpg://oponn_user:oponn_password@localhost:5432/oponn_db"
        )
    if "REDIS_URL" not in env:
        env["REDIS_URL"] = "redis://localhost:6379"

    run_cmd(
        [
            "gunicorn",
            "-k",
            "uvicorn.workers.UvicornWorker",
            "-w",
            str(workers),
            "--bind",
            "0.0.0.0:8000",
            "src.main:app",
        ],
        env=env,
    )


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def test(
    ctx: typer.Context,
):
    """Run tests (supports all pytest arguments)."""
    command = [sys.executable, "-m", "pytest"]
    if ctx.args:
        command.extend(ctx.args)
    else:
        command.append("tests/")
    run_cmd(command)


@app.command()
def lint():
    """Lint and fix code with Ruff."""
    run_cmd(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "src/",
            "tests/",
            "tools/",
            "dev.py",
            "--fix",
        ]
    )


@app.command()
def lint_ui():
    """Lint HTML with djlint."""
    run_cmd(
        [
            sys.executable,
            "-m",
            "djlint",
            "templates/",
            "--check",
            "--profile",
            "jinja",
        ]
    )


@app.command()
def format():
    """Format code with Ruff."""
    run_cmd(
        [sys.executable, "-m", "ruff", "format", "src/", "tests/", "tools/", "dev.py"]
    )


@app.command()
def format_ui():
    """Format HTML/CSS/JS with djlint and beautifiers."""
    # Format templates with djlint
    run_cmd(
        [
            sys.executable,
            "-m",
            "djlint",
            "templates/",
            "--reformat",
            "--profile",
            "jinja",
        ]
    )
    # Format static assets with beautifiers
    run_cmd(
        [
            "css-beautify",
            "-r",
            "static/css/style.css",
        ]
    )
    run_cmd(
        [
            "js-beautify",
            "-r",
            "static/js/app.js",
        ]
    )


@app.command()
def typecheck():
    """Check types with basedpyright."""
    run_cmd(["basedpyright", "src", "tools", "dev.py"])


@app.command()
def simulate(
    ballot_id: str = typer.Argument(..., help="ID of the ballot to simulate votes for"),  # pyright: ignore[reportCallInDefaultInitializer]
    num_votes: int = typer.Argument(10, help="Number of votes to cast"),  # pyright: ignore[reportCallInDefaultInitializer]
):
    """Simulate votes for a specific ballot."""
    run_cmd([sys.executable, "tools/simulate_votes.py", ballot_id, str(num_votes)])


@app.command()
def services(
    action: str = typer.Argument(..., help="start or stop"),
):
    """Manage backend services (Postgres & Redis) via Docker Compose."""
    if action == "start":
        run_cmd(["docker-compose", "up", "-d"])
        print("Services started on ports 5432 (PG) and 6379 (Redis)")
    elif action == "stop":
        run_cmd(["docker-compose", "down"])
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)


@app.command()
def migrate():
    """Generate initial database migration using a temporary Postgres container."""
    run_cmd([sys.executable, "tools/generate_migration.py"])


@app.command()
def upgrade():
    """Apply database migrations."""
    env = os.environ.copy()
    if "DATABASE_URL" not in env:
        env["DATABASE_URL"] = (
            "postgresql+asyncpg://oponn_user:oponn_password@localhost:5432/oponn_db"
        )
    if "REDIS_URL" not in env:
        env["REDIS_URL"] = "redis://localhost:6379"

    run_cmd([sys.executable, "-m", "alembic", "upgrade", "head"], env=env)


if __name__ == "__main__":
    app()
