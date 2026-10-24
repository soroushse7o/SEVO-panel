"""MTProto proxy routes: status, secret rotation, endpoint config, and restart."""

from fastapi import APIRouter, Request, Depends, HTTPException

from app import state
from app.config import settings
from app.security import require_auth
from app.services import mtproxy

router = APIRouter()


@router.get("/api/mtproxy")
async def mtproxy_status(_=Depends(require_auth)):
    return mtproxy.get_status()


@router.post("/api/mtproxy/regenerate")
async def mtproxy_regenerate(request: Request, _=Depends(require_auth)):
    """Issue a new secret. Existing clients must re-import the link."""
    body = {}
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001 - empty body is fine
        pass

    domain = str(body.get("fake_domain") or "").strip()
    if domain and (" " in domain or "." not in domain or len(domain) > 253):
        raise HTTPException(status_code=400, detail="Invalid fronting domain")

    secret = mtproxy.generate_secret(domain)
    await mtproxy.save_secret(secret)
    state.log_event("MTProxy", "Secret regenerated")

    if settings.mtproxy_enabled and mtproxy.find_binary():
        await mtproxy.restart()

    return mtproxy.get_status()


@router.post("/api/mtproxy/set-endpoint")
async def mtproxy_set_endpoint(request: Request, _=Depends(require_auth)):
    """
    Update the bind port (inside the container) and the public endpoint
    (host + port that clients use). Both persist in the DB and mtg restarts
    so the new bind port takes effect. Clear public_host/public_port to fall
    back to automatic Railway / platform detection.
    """
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}

    bind_port = body.get("bind_port")
    public_host = str(body.get("public_host") or "").strip()
    public_port = body.get("public_port")

    try:
        if bind_port is not None and str(bind_port).strip():
            bind_port = int(bind_port)
        else:
            bind_port = None
        if public_port is not None and str(public_port).strip():
            public_port = int(public_port)
        else:
            public_port = None
        return await mtproxy.set_endpoint(bind_port, public_host, public_port)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/api/mtproxy/restart")
async def mtproxy_restart(_=Depends(require_auth)):
    if not settings.mtproxy_enabled:
        raise HTTPException(status_code=400, detail="MTProxy is disabled")
    if not mtproxy.find_binary():
        raise HTTPException(status_code=400, detail="mtg binary is not present in this image")
    await mtproxy.restart()
    state.log_event("MTProxy", "Proxy restarted from the panel")
    return mtproxy.get_status()
