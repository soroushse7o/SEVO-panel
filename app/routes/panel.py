"""
Panel page and misc public routes.
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from app import state
from app.database import fetchall, fetchone
from app.security import require_auth
from app.vless import get_domain
from datetime import datetime, timezone
import os
import asyncio

router = APIRouter()
PANEL_VERSION = "3.0.4"


@router.post("/api/panel/restart")
async def restart_panel(_=Depends(require_auth)):
    """
    Restart the whole panel process. Active connections will drop for a
    few seconds while the process re-executes itself with the same argv/env
    (so the host platform keeps the same port assignment). On Railway this
    re-exec is equivalent to a restart of the service.
    """
    state.log_event("System", "Panel restart requested from the web UI")
    try:
        # Give the response a moment to flush, then exit. On platforms with a
        # process manager (Railway, Render, supervisors) the runtime respawn
        # the process automatically -- a clean exit is more reliable than
        # os.execv, which can fail or orphan the port on some runtimes.
        await asyncio.sleep(0.3)
        os._exit(0)
    except Exception as e:
        state.log_event("System", f"Restart failed ({e})")
    return {"ok": True}


@router.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {"service": "SE7O-SNA Panel", "version": PANEL_VERSION, "status": "active", "domain": get_domain()}


STATIC_IMG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "img")
_IMG_CACHE: dict[str, bytes] = {}


def _read_img(name: str) -> bytes | None:
    if name in _IMG_CACHE:
        return _IMG_CACHE[name]
    try:
        with open(os.path.join(STATIC_IMG, name), "rb") as f:
            data = f.read()
        _IMG_CACHE[name] = data
        return data
    except OSError:
        return None


@router.get("/favicon.ico")
async def favicon():
    data = _read_img("favicon.png")
    if data is None:
        return Response(content=b"", media_type="image/x-icon", status_code=204)
    return Response(content=data, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=604800"})


@router.get("/img/logo.png")
async def logo_image():
    data = _read_img("logo.png")
    if data is None:
        raise HTTPException(status_code=404, detail="logo not found")
    return Response(content=data, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=604800"})


@router.get("/img/favicon.png")
async def favicon_png():
    data = _read_img("favicon.png")
    if data is None:
        raise HTTPException(status_code=404, detail="favicon not found")
    return Response(content=data, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=604800"})


@router.get("/panel")
@router.get("/login")
@router.get("/dashboard")
async def panel_page(request: Request):
    """Serve the single-page panel HTML."""
    from app.templates.panel_html import PANEL_HTML
    return HTMLResponse(content=PANEL_HTML)


@router.get("/api/login-logs")
async def get_login_logs(_=Depends(require_auth)):
    rows = await fetchall(
        "SELECT timestamp, ip, success, user_agent, path FROM login_logs ORDER BY timestamp DESC LIMIT 20",
        "SELECT timestamp, ip, success, user_agent, path FROM login_logs ORDER BY timestamp DESC LIMIT 20",
    )
    return {"logs": rows}


@router.get("/api/logs")
async def get_logs(_=Depends(require_auth)):
    return {"logs": list(state.error_logs)}


@router.delete("/api/logs/clear")
async def clear_logs(_=Depends(require_auth)):
    state.error_logs.clear()
    return {"ok": True}


@router.get("/api/logs/size")
async def logs_size(_=Depends(require_auth)):
    import json
    total = sum(len(json.dumps(log)) for log in state.error_logs)
    return {"count": len(state.error_logs), "size_kb": round(total / 1024, 2)}


@router.get("/api/links/{uid}/health")
async def link_health(uid: str, _=Depends(require_auth)):
    async with state.links_lock:
        link = state.links.get(uid)
    if not link:
        raise HTTPException(status_code=404, detail="Not found")
    now = datetime.now(timezone.utc)

    expires = None
    if link.get("expires_at"):
        try:
            expires = datetime.fromisoformat(link["expires_at"].replace("Z", "+00:00"))
        except Exception:
            pass

    is_expired = bool(expires and expires < now)
    limit = link.get("limit_bytes", 0)
    used = link.get("used_bytes", 0)
    over_quota = bool(limit and used >= limit)

    async with state.connections_lock:
        conns = sum(1 for info in state.connections.values() if info.get("uuid") == uid)

    return {
        "uid": uid,
        "label": link.get("label"),
        "active": bool(link.get("active")),
        "expired": is_expired,
        "over_quota": over_quota,
        "used_bytes": used,
        "limit_bytes": limit,
        "active_connections": conns,
        "healthy": bool(link.get("active")) and not is_expired and not over_quota,
    }
