import os
import subprocess
import sys
from testcontainers.postgres import PostgresContainer  # type: ignore


def generate_migration():
    # Use a fixed version of postgres for consistency
    with PostgresContainer("postgres:16-alpine") as postgres:
        # asyncpg requires postgresql+asyncpg:// scheme
        db_url = postgres.get_connection_url().replace("psycopg2", "asyncpg")
        os.environ["DATABASE_URL"] = db_url

        print(f"Postgres container started at {db_url}")

        # Run the alembic revision command using the current python executable
        # This ensures we are using the same environment.
        command = [
            sys.executable,
            "-m",
            "alembic",
            "revision",
            "--autogenerate",
            "-m",
            "initial_schema",
        ]

        print(f"Running: {' '.join(command)}")
        result = subprocess.run(command, env=os.environ, capture_output=True, text=True)

        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        if result.returncode != 0:
            sys.exit(result.returncode)


if __name__ == "__main__":
    generate_migration()
