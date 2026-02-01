import os
import subprocess
import sys
from typing import Optional
from testcontainers.postgres import PostgresContainer


def run_migration_generation(message: Optional[str] = None):
    """
    Generates an Alembic migration by comparing current models
    against a fresh temporary Postgres container.
    """
    msg = message or "auto_migration"

    with PostgresContainer("postgres:16-alpine") as postgres:
        db_url = postgres.get_connection_url().replace("psycopg2", "asyncpg")

        # Inject the temp DB URL into environment for Alembic
        env = os.environ.copy()
        env["DATABASE_URL"] = db_url

        print(f"Ephemeral Postgres started: {db_url}")

        # 1. Bring temp DB to current HEAD
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"], env=env, check=True
        )

        # 2. Generate new revision
        print(f"Generating revision: {msg}")
        subprocess.run(
            [sys.executable, "-m", "alembic", "revision", "--autogenerate", "-m", msg],
            env=env,
            check=True,
        )


if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) > 1 else None
    run_migration_generation(msg)
