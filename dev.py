#!/usr/bin/env python3
import subprocess
import sys

import typer

app = typer.Typer(help="Oponn Development Tool", add_completion=False)


def run_cmd(command: list[str]):
    print(f"Running: {' '.join(command)}")
    try:
        _ = subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


@app.command()
def start():
    """Run the FastAPI application with reload."""
    run_cmd(["uvicorn", "src.main:app", "--reload"])


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
def format():
    """Format code with Ruff."""
    run_cmd(
        [sys.executable, "-m", "ruff", "format", "src/", "tests/", "tools/", "dev.py"]
    )


@app.command()
def typecheck():
    """Check types with basedpyright."""
    run_cmd(["basedpyright", "src", "tools", "dev.py"])


@app.command()
def simulate(
    ballot_id: int = typer.Argument(..., help="ID of the ballot to simulate votes for"),  # pyright: ignore[reportCallInDefaultInitializer]
    num_votes: int = typer.Argument(10, help="Number of votes to cast"),  # pyright: ignore[reportCallInDefaultInitializer]
):
    """Simulate votes for a specific ballot."""
    run_cmd([sys.executable, "tools/simulate_votes.py", str(ballot_id), str(num_votes)])


@app.command()
def migrate():
    """Generate initial database migration using a temporary Postgres container."""
    run_cmd([sys.executable, "tools/generate_migration.py"])


if __name__ == "__main__":
    app()
