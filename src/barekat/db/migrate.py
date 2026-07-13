"""Apply ordered SQL migrations from docker/postgres/migrations/."""

from __future__ import annotations

import re
from pathlib import Path

import psycopg2

MIGRATION_PATTERN = re.compile(r"^(\d{3})_.+\.sql$")


def migrations_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "docker" / "postgres" / "migrations"


def _discover_migrations() -> list[tuple[str, Path]]:
    root = migrations_dir()
    if not root.exists():
        return []
    files: list[tuple[str, Path]] = []
    for path in sorted(root.glob("*.sql")):
        match = MIGRATION_PATTERN.match(path.name)
        if match:
            files.append((match.group(1), path))
    return files


def _ensure_schema_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            CREATE SCHEMA IF NOT EXISTS audit;
            CREATE TABLE IF NOT EXISTS audit.schema_migrations (
                version     VARCHAR(10) PRIMARY KEY,
                filename    VARCHAR(255) NOT NULL,
                applied_at  TIMESTAMPTZ DEFAULT NOW()
            );
        """)


def _applied_versions(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM audit.schema_migrations")
        return {row[0] for row in cur.fetchall()}


def list_pending_migrations(conn=None) -> list[str]:
    """Return filenames of migrations not yet applied."""
    migrations = _discover_migrations()
    if conn is None:
        return [path.name for _, path in migrations]

    applied = _applied_versions(conn)
    return [path.name for version, path in migrations if version not in applied]


def apply_migrations(
    *,
    database_url: str | None = None,
    connection=None,
    stop_on_error: bool = True,
) -> list[str]:
    """Apply pending migrations. Returns list of applied filenames."""
    own_conn = connection is None
    conn = connection
    if own_conn:
        if database_url:
            conn = psycopg2.connect(database_url)
        else:
            from barekat.config.settings import get_settings

            settings = get_settings()
            conn = psycopg2.connect(
                host=settings.postgres_host,
                port=settings.postgres_port,
                user=settings.postgres_user,
                password=settings.postgres_password,
                dbname=settings.postgres_db,
            )

    applied_now: list[str] = []
    try:
        _ensure_schema_table(conn)
        applied = _applied_versions(conn)
        for version, path in _discover_migrations():
            if version in applied:
                continue
            sql = path.read_text(encoding="utf-8")
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO audit.schema_migrations (version, filename) VALUES (%s, %s)",
                    (version, path.name),
                )
            conn.commit()
            applied_now.append(path.name)
    except Exception:
        if own_conn:
            conn.rollback()
        if stop_on_error:
            raise
    finally:
        if own_conn and conn is not None:
            conn.close()

    return applied_now
