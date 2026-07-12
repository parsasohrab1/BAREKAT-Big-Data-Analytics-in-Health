"""JWT authentication utilities."""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from barekat.config.settings import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"

# Development users (replace with DB lookup in production)
DEV_USERS = {
  "admin": {"password": "admin123", "role": "admin", "email": "admin@barekat.local"},
  "clinician": {"password": "clinician123", "role": "clinician", "email": "clinician@barekat.local"},
  "researcher": {"password": "researcher123", "role": "researcher", "email": "researcher@barekat.local"},
}


def verify_password(plain: str, hashed: str) -> bool:
  return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
  return pwd_context.hash(password)


def authenticate_user(username: str, password: str) -> dict | None:
  user = DEV_USERS.get(username)
  if not user or user["password"] != password:
    return None
  return {"username": username, "role": user["role"], "email": user["email"]}


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
