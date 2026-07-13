"""Apply PostgreSQL init schema and pending migrations (tests, CI, local)."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg2

from barekat.db.migrate import apply_migrations


def apply_init_sql(database_url: str | None = None) -> None:
    init_sql = Path(__file__).resolve().parents[1] / "docker" / "postgres" / "init.sql"
    if not init_sql.exists():
        raise FileNotFoundError(f"init.sql not found: {init_sql}")

    if database_url:
        conn = psycopg2.connect(database_url)
    else:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            user=os.getenv("POSTGRES_USER", "barekat"),
            password=os.getenv("POSTGRES_PASSWORD", "barekat_secret"),
            dbname=os.getenv("POSTGRES_DB", "barekat_health"),
        )

    try:
        with conn.cursor() as cur:
            cur.execute(init_sql.read_text(encoding="utf-8"))
        conn.commit()
        apply_migrations(connection=conn)
    finally:
        conn.close()


if __name__ == "__main__":
    apply_init_sql()
    print("Database schema and migrations applied successfully.")
