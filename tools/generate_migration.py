import os
import subprocess
import sys

from testcontainers.postgres import (
    PostgresContainer,
)


def generate_migration():
    # Get message from command line or use default
    message = sys.argv[1] if len(sys.argv) > 1 else "auto_migration"

    # Use a fixed version of postgres for consistency
    with PostgresContainer("postgres:16-alpine") as postgres:
        # asyncpg requires postgresql+asyncpg:// scheme
        db_url = postgres.get_connection_url().replace("psycopg2", "asyncpg")
        os.environ["DATABASE_URL"] = db_url

        print(f"Postgres container started at {db_url}")

        # 1. Upgrade the fresh container to the current head
        upgrade_command = [sys.executable, "-m", "alembic", "upgrade", "head"]
        print(f"Running: {' '.join(upgrade_command)}")
        upgrade_result = subprocess.run(
            upgrade_command, env=os.environ, capture_output=True, text=True
        )
        if upgrade_result.returncode != 0:
            print(upgrade_result.stderr, file=sys.stderr)
            sys.exit(upgrade_result.returncode)

        # 2. Run the alembic revision command
        revision_command = [
            sys.executable,
            "-m",
            "alembic",
            "revision",
            "--autogenerate",
            "-m",
            message,
        ]

        print(f"Running: {' '.join(revision_command)}")
        result = subprocess.run(
            revision_command, env=os.environ, capture_output=True, text=True
        )

        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        if result.returncode != 0:
            sys.exit(result.returncode)


if __name__ == "__main__":
    generate_migration()
