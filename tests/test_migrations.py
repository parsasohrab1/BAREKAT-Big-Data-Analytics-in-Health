"""Tests for SQL migration runner."""

from barekat.db.migrate import migrations_dir


def test_migrations_directory_exists():
    root = migrations_dir()
    assert root.is_dir()


def test_migrations_include_auth_seed():
    files = sorted(p.name for p in migrations_dir().glob("*.sql"))
    assert "002_etl_audit.sql" in files
    assert "013_auth_user_seeds.sql" in files
    assert files.index("002_etl_audit.sql") < files.index("013_auth_user_seeds.sql")
