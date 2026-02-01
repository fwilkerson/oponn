#!/usr/bin/env python3
import os
import subprocess
import sys
from typing import Optional, List

import typer
from dotenv import load_dotenv

# Import tool logic directly
from tools.generate_keyset import generate_master_keyset
from tools.simulate_votes import simulate as run_simulation
from tools.generate_migration import run_migration_generation

app = typer.Typer(
    help="Oponn CLI: Nordic Terminal Voting Service Toolkit",
    add_completion=False,
    rich_markup_mode="rich",
)


def run_cmd(command: List[str], env: Optional[dict] = None):
    """Executes a shell command with consistent environment handling."""
    if env is None:
        load_dotenv()
        env = os.environ.copy()

    try:
        subprocess.run(command, check=True, env=env)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        sys.exit(0)


def get_base_env(env_name: str = "development") -> dict:
    load_dotenv()
    env = os.environ.copy()
    env["OPONN_ENV"] = env_name

    if "DATABASE_URL" not in env:
        env["DATABASE_URL"] = (
            "postgresql+asyncpg://oponn_user:oponn_password@localhost:5432/oponn_db"
        )
    if "REDIS_URL" not in env:
        env["REDIS_URL"] = "redis://localhost:6379"
    return env


# --- Service Control ---


@app.command()
def dev():
    """[bold cyan]START[/bold cyan] development server with hot-reload."""
    env = get_base_env("development")
    run_cmd(["uvicorn", "src.main:app", "--reload"], env=env)


@app.command()
def prod(workers: int = 2):
    """[bold magenta]START[/bold magenta] production server (Gunicorn)."""
    env = get_base_env("production")
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


@app.command()
def infra(action: str = typer.Argument(..., help="up, down, purge")):
    """[bold yellow]MANAGE[/bold yellow] Postgres & Redis (Docker)."""
    if action == "up":
        run_cmd(["docker-compose", "up", "-d"])
    elif action == "down":
        run_cmd(["docker-compose", "down"])
    elif action == "purge":
        run_cmd(["docker-compose", "down", "-v"])


# --- Database & Security ---


@app.command()
def db(
    action: str = typer.Argument(..., help="migrate, upgrade"),
    message: Optional[str] = typer.Option(
        None, "--message", "-m", help="Migration message"
    ),
):
    """[bold blue]MANAGE[/bold blue] database migrations."""
    env = get_base_env()
    if action == "migrate":
        run_migration_generation(message)
    elif action == "upgrade":
        run_cmd(["alembic", "upgrade", "head"], env=env)


@app.command()
def keyset():
    """[bold green]GENERATE[/bold green] a new master keyset."""
    print(generate_master_keyset())


@app.command()
def simulate(ballot_id: str, votes: int = 10):
    """[bold white]SIMULATE[/bold white] voting traffic."""
    run_simulation(ballot_id, votes)


# --- Quality Assurance ---


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def test(ctx: typer.Context):
    """[bold green]RUN[/bold green] tests (accepts pytest args)."""
    env = get_base_env("testing")
    cmd = [sys.executable, "-m", "pytest"] + ctx.args
    run_cmd(cmd, env=env)


@app.command()
def lint(fix: bool = True):
    """[bold white]LINT[/bold white] & format Python and Templates."""
    flags = ["--fix"] if fix else []
    run_cmd(
        [sys.executable, "-m", "ruff", "check", "src", "tests", "tools", "manage.py"]
        + flags
    )
    run_cmd(
        [sys.executable, "-m", "ruff", "format", "src", "tests", "tools", "manage.py"]
    )

    dj_flags = ["--reformat"] if fix else ["--check"]
    run_cmd(
        [sys.executable, "-m", "djlint", "templates", "--profile", "jinja"] + dj_flags
    )


@app.command()
def check():
    """[bold red]FULL CHECK[/bold red]: Lint, Typecheck, and Test."""
    lint(fix=False)
    run_cmd(["basedpyright", "src", "tests", "tools", "manage.py"])
    env = get_base_env("testing")
    run_cmd([sys.executable, "-m", "pytest"], env=env)


if __name__ == "__main__":
    app()
