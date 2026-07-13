"""JWT authentication utilities."""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from barekat.config.settings import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"

# Dev-only fallback when PostgreSQL is unavailable (disabled in production)
_DEV_USERS = {
    "admin": {
        "password": "admin123",
        "role": "admin",
        "email": "admin@barekat.local",
        "tenant_id": "default",
        "is_platform_admin": True,
    },
    "clinician": {
        "password": "clinician123",
        "role": "clinician",
        "email": "clinician@barekat.local",
        "tenant_id": "tehran-general",
    },
    "researcher": {
        "password": "researcher123",
        "role": "researcher",
        "email": "researcher@barekat.local",
        "tenant_id": "isfahan-medical",
    },
}


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _authenticate_dev(username: str, password: str, tenant_id: str | None = None) -> dict | None:
    user = _DEV_USERS.get(username)
    if not user or user["password"] != password:
        return None

    tid = user.get("tenant_id", "default")
    slug = "default"
    is_platform_admin = user.get("is_platform_admin", False)

    try:
        from barekat.tenant.repository import resolve_user_tenant

        ctx = resolve_user_tenant(username, tenant_id or tid)
        if ctx:
            tid = ctx.tenant_id
            slug = ctx.slug
            is_platform_admin = is_platform_admin or ctx.is_platform_admin
    except Exception:
        pass

    return {
        "username": username,
        "role": user["role"],
        "email": user["email"],
        "tenant_id": tid,
        "tenant_slug": slug,
        "is_platform_admin": is_platform_admin,
    }


def authenticate_user(username: str, password: str, tenant_id: str | None = None) -> dict | None:
    settings = get_settings()

    if settings.auth_use_database:
        from barekat.security.users import authenticate_db_user

        user = authenticate_db_user(username, password, tenant_id)
        if user:
            return user

    if settings.auth_dev_fallback and not settings.is_production:
        return _authenticate_dev(username, password, tenant_id)

    return None


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc
