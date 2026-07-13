"""CLI entry point for database migrations."""

from barekat.db.migrate import apply_migrations, list_pending_migrations


def main() -> None:
    import psycopg2
    import os

    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "barekat"),
        password=os.getenv("POSTGRES_PASSWORD", "barekat_secret"),
        dbname=os.getenv("POSTGRES_DB", "barekat_health"),
    )
    try:
        pending = list_pending_migrations(conn)
        if not pending:
            print("No pending migrations.")
            return
        applied = apply_migrations(connection=conn)
        print(f"Applied {len(applied)} migration(s): {', '.join(applied)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
