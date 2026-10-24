"""
Authentication & security utilities.
JWT tokens, bcrypt password hashing, and FastAPI dependency for auth.
"""
import bcrypt
from datetime import datetime, timedelta, timezone
from fastapi import Request, HTTPException
from jose import jwt, JWTError
from app.config import settings
from app import state


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_jwt(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, state.secret_key, algorithm=settings.jwt_algorithm)


def decode_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(token, state.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


async def require_auth(request: Request):
    """FastAPI dependency — raises 401 if no valid JWT cookie."""
    token = request.cookies.get(settings.session_cookie)
    if not token or not decode_jwt(token):
        raise HTTPException(status_code=401, detail="unauthorized")
    return token
