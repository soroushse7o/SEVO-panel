"""
Authentication routes — login, logout, password change.
"""
import re
import secrets

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.database import execute as db_exec, fetchone
from app.security import hash_password, verify_password, create_jwt, require_auth
from app import state
from app.config import settings

router = APIRouter()


def _log_flag(success: bool):
    from app.database import DB_BACKEND
    return success if DB_BACKEND == "postgresql" else (1 if success else 0)


limiter = Limiter(key_func=get_remote_address)


@router.post("/api/login")
@limiter.limit("10/minute")
async def api_login(request: Request):
    from app.services.telegram import notify_login
    body = await request.json()
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")
    ip = request.client.host
    ua = request.headers.get("user-agent", "")
    user_ok = secrets.compare_digest(username.lower(), (state.admin_username or "").lower()) if username else False
    success = user_ok and verify_password(password, state.admin_password_hash)

    if state.logging_enabled:
        from datetime import datetime, timezone
        try:
            await db_exec(
                "INSERT INTO login_logs (timestamp, ip, success, user_agent, path) VALUES (?,?,?,?,?)",
                "INSERT INTO login_logs (timestamp, ip, success, user_agent, path) VALUES ($1,$2,$3,$4,$5)",
                (datetime.now(timezone.utc).isoformat(), ip, _log_flag(success), ua, "/api/login"),
            )
        except Exception:
            pass

    if not success:
        state.log_event("Auth", f"Failed login from {ip}", ip, ua)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    state.log_event("Auth", f"Successful login from {ip}", ip, ua)
    token = create_jwt({"sub": "admin"})
    resp = JSONResponse({"ok": True})
    resp.set_cookie(
        key=settings.session_cookie, value=token,
        max_age=settings.jwt_expire_minutes * 60,
        httponly=True, samesite="lax",
        secure=settings.domain != "localhost", path="/",
    )
    # Notify telegram in background
    import asyncio
    asyncio.create_task(notify_login(ip, ua))
    return resp


@router.post("/api/logout")
async def api_logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(settings.session_cookie, path="/")
    return resp


@router.get("/api/me")
async def api_me(_=Depends(require_auth)):
    return {"authenticated": True, "username": state.admin_username}


@router.post("/api/change-username")
async def api_change_username(request: Request, _=Depends(require_auth)):
    body = await request.json()
    current = str(body.get("current_password") or "")
    new_username = str(body.get("new_username") or "").strip()
    if not verify_password(current, state.admin_password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if not re.match(r"^[A-Za-z0-9._-]{3,32}$", new_username):
        raise HTTPException(
            status_code=400,
            detail="Username must be 3-32 characters: letters, digits, dot, underscore or hyphen",
        )
    state.admin_username = new_username
    await db_exec(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('admin_username', ?)",
        "INSERT INTO settings (key, value) VALUES ('admin_username', $1) ON CONFLICT (key) DO UPDATE SET value = $1",
        (new_username,),
    )
    state.log_event("Security", f"Admin username changed to {new_username}")
    return {"ok": True, "username": new_username}


@router.post("/api/change-password")
async def api_change_password(request: Request, _=Depends(require_auth)):
    body = await request.json()
    current = str(body.get("current_password") or "")
    new = str(body.get("new_password") or "")
    if not verify_password(current, state.admin_password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(new) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if not re.search(r"[A-Z]", new) or not re.search(r"[a-z]", new) or not re.search(r"[0-9]", new):
        raise HTTPException(status_code=400, detail="Password must contain uppercase, lowercase, and digit")

    new_hash = hash_password(new)
    state.admin_password_hash = new_hash
    await db_exec(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('admin_password_hash', ?)",
        "INSERT INTO settings (key, value) VALUES ('admin_password_hash', $1) ON CONFLICT (key) DO UPDATE SET value = $1",
        (new_hash,),
    )
    state.log_event("Security", "Admin password changed")
    return {"ok": True}
