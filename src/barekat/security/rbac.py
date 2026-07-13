"""Role-Based Access Control (RBAC) for health data platform."""

from enum import Enum

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from barekat.security.auth import decode_token

security = HTTPBearer()


class Role(str, Enum):
  ADMIN = "admin"
  CLINICIAN = "clinician"
  RESEARCHER = "researcher"
  VIEWER = "viewer"
  PLATFORM_ADMIN = "platform_admin"


ROLE_PERMISSIONS: dict[Role, set[str]] = {
  Role.PLATFORM_ADMIN: {"read", "write", "delete", "manage_users", "view_phi", "export", "manage_tenants"},
  Role.ADMIN: {"read", "write", "delete", "manage_users", "view_phi", "export", "manage_tenants"},
  Role.CLINICIAN: {"read", "write", "view_phi", "acknowledge_alerts"},
  Role.RESEARCHER: {"read", "export", "run_analytics"},
  Role.VIEWER: {"read"},
}


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
  try:
    payload = decode_token(credentials.credentials)
    return payload
  except Exception as exc:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Invalid or expired token",
      headers={"WWW-Authenticate": "Bearer"},
    ) from exc


def require_permission(permission: str):
  def checker(user: dict = Depends(get_current_user)) -> dict:
    role = Role(user.get("role", "viewer"))
    allowed = ROLE_PERMISSIONS.get(role, set())
    if permission not in allowed:
      raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Role '{role.value}' lacks permission: {permission}",
      )
    return user

  return checker


def require_role(*roles: Role):
  def checker(user: dict = Depends(get_current_user)) -> dict:
    user_role = Role(user.get("role", "viewer"))
    if user_role not in roles:
      raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Required role: {[r.value for r in roles]}",
      )
    return user

  return checker
