"""Authentication endpoints."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from barekat.security.audit import log_access, log_login
from barekat.security.auth import authenticate_user, create_access_token, decode_token
from barekat.security.mfa import (
    activate_mfa,
    enroll_mfa,
    get_mfa_status,
    is_mfa_required,
    verify_mfa_code,
)
from barekat.security.rbac import Role, require_role, get_current_user

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str
    tenant_id: str | None = None


class MfaVerifyRequest(BaseModel):
    mfa_token: str
    code: str


class MfaEnrollRequest(BaseModel):
    code: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    tenant_id: str | None = None
    tenant_slug: str | None = None


class MfaRequiredResponse(BaseModel):
    mfa_required: bool = True
    mfa_token: str
    message: str = "MFA verification required"


def _token_payload(user: dict) -> dict:
    return {
        "sub": user["username"],
        "role": user["role"],
        "email": user["email"],
        "tenant_id": user.get("tenant_id", "default"),
        "tenant_slug": user.get("tenant_slug", "default"),
        "is_platform_admin": user.get("is_platform_admin", False),
    }


@router.post("/login")
def login(request: LoginRequest, http_request: Request):
    ip = http_request.client.host if http_request.client else None
    ua = http_request.headers.get("user-agent")

    user = authenticate_user(request.username, request.password, request.tenant_id)
    if not user:
        log_login(request.username, success=False, ip_address=ip, user_agent=ua)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if is_mfa_required(user["username"], user["role"]):
        mfa_token = create_access_token(
            {**_token_payload(user), "mfa_pending": True},
            expires_delta=timedelta(minutes=5),
        )
        log_access(
            action="login_mfa_pending",
            resource="/api/v1/auth/login",
            username=user["username"],
            role=user["role"],
            resource_type="auth",
            ip_address=ip,
            user_agent=ua,
        )
        return MfaRequiredResponse(mfa_token=mfa_token)

    log_login(user["username"], success=True, ip_address=ip, user_agent=ua)
    token = create_access_token(_token_payload(user))
    return TokenResponse(
        access_token=token,
        role=user["role"],
        tenant_id=user.get("tenant_id"),
        tenant_slug=user.get("tenant_slug"),
    )


@router.post("/mfa/verify", response_model=TokenResponse)
def verify_mfa(body: MfaVerifyRequest, http_request: Request):
    ip = http_request.client.host if http_request.client else None
    try:
        payload = decode_token(body.mfa_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid MFA token") from exc

    if not payload.get("mfa_pending"):
        raise HTTPException(status_code=400, detail="Not an MFA challenge token")

    username = payload.get("sub", "")
    if not verify_mfa_code(username, body.code):
        log_access(
            action="mfa_failed",
            resource="/api/v1/auth/mfa/verify",
            username=username,
            resource_type="auth",
            status_code=401,
            ip_address=ip,
        )
        raise HTTPException(status_code=401, detail="Invalid MFA code")

    log_login(username, success=True, ip_address=ip)
    token = create_access_token({
        "sub": username,
        "role": payload.get("role"),
        "email": payload.get("email"),
        "tenant_id": payload.get("tenant_id", "default"),
        "tenant_slug": payload.get("tenant_slug", "default"),
        "mfa_verified": True,
    })
    return TokenResponse(
        access_token=token,
        role=payload.get("role", "viewer"),
        tenant_id=payload.get("tenant_id"),
        tenant_slug=payload.get("tenant_slug"),
    )


@router.post("/mfa/enroll")
def mfa_enroll(user: dict = Depends(require_role(Role.ADMIN))):
    username = user.get("sub", "admin")
    return enroll_mfa(username)


@router.post("/mfa/activate")
def mfa_activate(body: MfaEnrollRequest, user: dict = Depends(require_role(Role.ADMIN))):
    username = user.get("sub", "admin")
    if not activate_mfa(username, body.code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")
    return {"status": "activated", "username": username}


@router.get("/mfa/status")
def mfa_status(user: dict = Depends(get_current_user)):
    return get_mfa_status(user.get("sub", ""))
