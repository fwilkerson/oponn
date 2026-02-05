#!/usr/bin/env python3
import os
import subprocess
import sys
from typing import List

import typer
from dotenv import load_dotenv
from tools.generate_migration import run_migration_generation

# Import tool logic directly
from tools.simulate_votes import simulate as run_simulation

app = typer.Typer(
    help="Oponn CLI: Nordic Terminal Voting Service Toolkit",
    add_completion=False,
    rich_markup_mode="rich",
)


def run_cmd(command: List[str], env: dict | None = None):
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
    """
    Prepares the environment for sub-commands.
    Loads .env and then overrides with .env.{env_name} if it exists.
    """
    load_dotenv(".env")
    env_file = f".env.{env_name}"
    if os.path.exists(env_file):
        load_dotenv(env_file, override=True)

    env = os.environ.copy()
    env["OPONN_ENV"] = env_name
    return env


# --- Service Control ---


@app.command()
def dev():
    """[bold cyan]START[/bold cyan] development server with hot-reload."""
    env = get_base_env("development")
    run_cmd(["uvicorn", "src.main:app", "--reload"], env=env)


@app.command()
def staging(workers: int = 2):
    """[bold yellow]START[/bold yellow] staging server (Gunicorn + LocalStack)."""
    env = get_base_env("staging")
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


def setup_localstack_kms():
    """Initializes a KMS key in LocalStack if it's running."""

    from rich import print as rprint

    try:
        import boto3

    except ImportError:
        rprint(
            "[yellow]Note:[/yellow] boto3 not installed, skipping LocalStack KMS setup."
        )

        return

    from botocore.exceptions import ClientError

    alias_name = "alias/oponn-local-key"
    try:
        rprint("[bold dim]Checking LocalStack KMS...[/bold dim]")

        # Use a short timeout so we don't hang if LocalStack isn't ready
        client = boto3.client(
            "kms",
            endpoint_url="http://localhost:4566",
            region_name="us-east-1",
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )

        # Check if our alias already exists
        try:
            client.describe_key(KeyId=alias_name)
            rprint(
                f"[bold green]INFO:[/bold green] Local KMS key already exists: [bold cyan]{alias_name}[/bold cyan]"
            )
            rprint(
                f"Ensure your .env has: [bold yellow]OPONN_KMS_KEY_ID={alias_name}[/bold yellow]\n"
            )
            return
        except ClientError:
            # Alias doesn't exist, proceed to create
            pass

        response = client.create_key(
            Description="Oponn Local Dev Key",
        )
        key_id = response["KeyMetadata"]["KeyId"]

        # Create the stable alias
        client.create_alias(AliasName=alias_name, TargetKeyId=key_id)

        rprint(
            f"\n[bold green]SUCCESS:[/bold green] Created LocalStack KMS Key and Alias: [bold cyan]{alias_name}[/bold cyan]"
        )
        rprint(
            f"Add this to your .env for a stable dev experience: [bold yellow]OPONN_KMS_KEY_ID={alias_name}[/bold yellow]\n"
        )

    except Exception as e:
        rprint(f"[red]Error:[/red] Failed to setup LocalStack KMS: {e}")
        rprint("[dim]Ensure LocalStack is running at http://localhost:4566[/dim]")


@app.command()
def infra(action: str = typer.Argument(..., help="up, down, purge")):
    """[bold yellow]MANAGE[/bold yellow] Postgres, Redis, and LocalStack (Docker)."""
    if action == "up":
        run_cmd(["docker-compose", "up", "-d"])
        # Give LocalStack a moment to start and then try to init the key
        setup_localstack_kms()
    elif action == "down":
        run_cmd(["docker-compose", "down"])
    elif action == "purge":
        run_cmd(["docker-compose", "down", "-v"])


# --- Database & Security ---


@app.command()
def db(
    action: str = typer.Argument(..., help="migrate, upgrade"),
    env: str = typer.Option(
        "", "--env", "-e", help="The environment configuration to use"
    ),
    message: str | None = typer.Option(
        None, "--message", "-m", help="Migration message"
    ),
):
    """[bold blue]MANAGE[/bold blue] database migrations."""

    if action == "migrate":
        run_migration_generation(message)
    elif action == "upgrade":
        run_cmd(["alembic", "upgrade", "head"], env=get_base_env(env))


@app.command()
def simulate(ballot_id: str, votes: int = 10):
    """[bold white]SIMULATE[/bold white] voting traffic."""
    run_simulation(ballot_id, votes)


# --- Quality Assurance ---


@app.command()
def bootstrap():
    """[bold cyan]INITIALIZE[/bold cyan] development environment (Git, Pre-commit)."""
    from rich import print as rprint

    rprint("[bold blue]Setting up Git configuration...[/bold blue]")
    try:
        subprocess.run(["git", "config", "core.ignorecase", "false"], check=True)
        rprint("  - [green]SUCCESS:[/green] core.ignorecase set to false")
    except Exception as e:
        rprint(f"  - [red]ERROR:[/red] Failed to set git config: {e}")

    rprint("\n[bold blue]Installing pre-commit hooks...[/bold blue]")
    try:
        run_cmd(["pre-commit", "install"])
        rprint("  - [green]SUCCESS:[/green] pre-commit installed")
    except Exception:
        rprint("  - [red]ERROR:[/red] Failed to install pre-commit")


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def test(ctx: typer.Context):
    """[bold green]RUN[/bold green] tests in a Linux Docker container for OS parity."""
    from rich import print as rprint

    rprint("[bold yellow]Building Linux Test Image...[/bold yellow]")
    run_cmd(["docker", "build", "-t", "oponn-test", "-f", "Dockerfile.test", "."])

    rprint("[bold green]Running tests in Linux Container...[/bold green]")
    # Use host network to allow the container to reach Postgres/Redis started on host by Testcontainers
    cmd = [
        "docker",
        "run",
        "--rm",
        "-e",
        "OPONN_IN_DOCKER=true",
        "-e",
        "TESTCONTAINERS_HOST_OVERRIDE=host.docker.internal",
        "-v",
        "/var/run/docker.sock:/var/run/docker.sock",
        "-v",
        f"{os.getcwd()}:/app",
        "--network",
        "host",
        "oponn-test",
        "python3",
        "-m",
        "pytest",
    ] + ctx.args
    run_cmd(cmd)


@app.command()
def lint(
    files: List[str] | None = typer.Argument(None, help="Specific files to lint"),
    fix: bool = True,
):
    """[bold white]LINT[/bold white] & format Python and Templates."""
    flags = ["--fix"] if fix else []

    # If no files provided, default to project directories
    targets = files if files else ["src", "tests", "tools", "manage.py", "templates"]

    # 1. Python Checks (Ruff)
    # Filter for .py files or directories
    py_targets = [
        t for t in targets if t.endswith(".py") or os.path.isdir(t) and t != "templates"
    ]
    if py_targets:
        run_cmd([sys.executable, "-m", "ruff", "check"] + py_targets + flags)
        run_cmd([sys.executable, "-m", "ruff", "format"] + py_targets)

    # 2. Template Checks (djLint)
    # Filter for .html files or the templates directory
    html_targets = [t for t in targets if t.endswith(".html") or t == "templates"]
    if html_targets:
        dj_flags = ["--reformat"] if fix else ["--check"]
        run_cmd(
            [sys.executable, "-m", "djlint"]
            + html_targets
            + ["--profile", "jinja"]
            + dj_flags
        )


@app.command()
def check():
    """[bold red]FULL CHECK[/bold red]: Lint, Typecheck, and Test."""
    lint(None, fix=False)
    run_cmd(["basedpyright", "src", "tests", "tools", "manage.py"])
    env = get_base_env("testing")
    run_cmd([sys.executable, "-m", "pytest"], env=env)


if __name__ == "__main__":
    app()
