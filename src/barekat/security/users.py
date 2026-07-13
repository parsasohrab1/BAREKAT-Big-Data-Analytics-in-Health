"""Database-backed user lookup for authentication."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from barekat.security.auth import verify_password
from barekat.storage.database import engine


def lookup_user(username: str) -> dict | None:
    query = text("""
        SELECT user_id, username, email, password_hash, role, is_active
        FROM audit.users
        WHERE username = :username
        LIMIT 1
    """)
    try:
        with engine.connect() as conn:
            row = conn.execute(query, {"username": username}).mappings().first()
    except SQLAlchemyError:
        return None
    if not row or not row["is_active"]:
        return None
    return dict(row)


def authenticate_db_user(username: str, password: str, tenant_id: str | None = None) -> dict | None:
    row = lookup_user(username)
    if not row or not verify_password(password, row["password_hash"]):
        return None

    from barekat.tenant.repository import resolve_user_tenant

    ctx = resolve_user_tenant(username, tenant_id)
    tid = ctx.tenant_id if ctx else "default"
    slug = ctx.slug if ctx else "default"
    is_platform_admin = (
        row["role"] == "admin"
        or (ctx.is_platform_admin if ctx else False)
    )
    return {
        "user_id": row["user_id"],
        "username": row["username"],
        "role": row["role"],
        "email": row["email"],
        "tenant_id": tid,
        "tenant_slug": slug,
        "is_platform_admin": is_platform_admin,
    }
