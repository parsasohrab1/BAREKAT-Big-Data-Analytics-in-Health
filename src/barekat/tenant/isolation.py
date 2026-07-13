"""SQL helpers for tenant data isolation."""

from __future__ import annotations

from barekat.tenant.context import get_tenant_id


def tenant_filter(column: str = "tenant_id", param: str = "tenant_id") -> str:
    """Return SQL WHERE fragment for tenant isolation."""
    return f"{column} = :{param}"


def tenant_params(tenant_id: str | None = None) -> dict:
    return {"tenant_id": tenant_id or get_tenant_id()}


def scoped_query(base_sql: str, *, table_alias: str | None = None) -> str:
    """Append tenant filter to a SELECT query."""
    col = f"{table_alias}.tenant_id" if table_alias else "tenant_id"
    if "WHERE" in base_sql.upper():
        return f"{base_sql} AND {tenant_filter(col)}"
    return f"{base_sql} WHERE {tenant_filter(col)}"
