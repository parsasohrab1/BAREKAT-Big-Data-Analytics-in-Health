"""Access audit trail — who, when, what data was accessed."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text

from barekat.config.settings import get_settings
from barekat.storage.database import engine


def _resolve_user_id(username: str | None) -> int | None:
    if not username:
        return None
    query = text("SELECT user_id FROM audit.users WHERE username = :username LIMIT 1")
    with engine.connect() as conn:
        row = conn.execute(query, {"username": username}).scalar()
    return int(row) if row else None


def log_access(
    *,
    action: str,
    resource: str | None = None,
    username: str | None = None,
    role: str | None = None,
    user_id: int | None = None,
    patient_id: str | None = None,
    resource_type: str | None = None,
    http_method: str | None = None,
    status_code: int | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> int | None:
    settings = get_settings()
    if not settings.audit_enabled:
        return None

    if user_id is None and username:
        user_id = _resolve_user_id(username)

    if not settings.audit_log_ip:
        ip_address = None

    query = text("""
        INSERT INTO audit.access_logs (
            user_id, username, role, action, resource, resource_type, patient_id,
            http_method, status_code, request_id, user_agent, ip_address, details
        ) VALUES (
            :user_id, :username, :role, :action, :resource, :resource_type, :patient_id,
            :http_method, :status_code, :request_id, :user_agent,
            CAST(:ip_address AS INET), CAST(:details AS JSONB)
        )
        RETURNING log_id
    """)
    with engine.begin() as conn:
        log_id = conn.execute(query, {
            "user_id": user_id,
            "username": username,
            "role": role,
            "action": action,
            "resource": resource,
            "resource_type": resource_type,
            "patient_id": patient_id,
            "http_method": http_method,
            "status_code": status_code,
            "request_id": request_id or str(uuid.uuid4()),
            "user_agent": user_agent,
            "ip_address": ip_address,
            "details": json.dumps(details or {}),
        }).scalar()
    return int(log_id) if log_id else None


def log_login(username: str, success: bool, ip_address: str | None = None, user_agent: str | None = None) -> None:
    log_access(
        action="login_success" if success else "login_failed",
        resource="/api/v1/auth/login",
        username=username if success else username,
        resource_type="auth",
        status_code=200 if success else 401,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def get_access_logs(
    *,
    limit: int = 100,
    offset: int = 0,
    username: str | None = None,
    patient_id: str | None = None,
    action: str | None = None,
    since: datetime | None = None,
) -> tuple[list[dict[str, Any]], int]:
    conditions = ["1=1"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}

    if username:
        conditions.append("username = :username")
        params["username"] = username
    if patient_id:
        conditions.append("patient_id = :patient_id")
        params["patient_id"] = patient_id
    if action:
        conditions.append("action = :action")
        params["action"] = action
    if since:
        conditions.append("timestamp >= :since")
        params["since"] = since

    where = " AND ".join(conditions)
    count_q = text(f"SELECT COUNT(*) FROM audit.access_logs WHERE {where}")
    data_q = text(f"""
        SELECT log_id, user_id, username, role, action, resource, resource_type,
               patient_id, http_method, status_code, request_id, ip_address,
               details, timestamp
        FROM audit.access_logs
        WHERE {where}
        ORDER BY timestamp DESC
        LIMIT :limit OFFSET :offset
    """)

    with engine.connect() as conn:
        total = conn.execute(count_q, params).scalar() or 0
        rows = conn.execute(data_q, params).mappings().all()

    return [dict(r) for r in rows], int(total)


def purge_old_access_logs(retention_days: int) -> int:
    query = text("""
        DELETE FROM audit.access_logs
        WHERE timestamp < NOW() - (:days || ' days')::INTERVAL
    """)
    with engine.begin() as conn:
        result = conn.execute(query, {"days": retention_days})
    return result.rowcount or 0
