"""
Aether tunnel control API (all endpoints require the panel session).

    GET  /api/aether/status      live status, logs, watchdog, settings
    POST /api/aether/start       body: tunnel options (optional; falls back to the saved ones)
    POST /api/aether/stop
    POST /api/aether/restart     body: tunnel options (optional)
    POST /api/aether/install     download + verify the Aether binary
    POST /api/aether/settings    body: {"outbound_mode": "direct|aether|auto", "auto_start": bool}
    GET  /api/aether/sweep         best-config test: progress + ranked results
    POST /api/aether/sweep/start   body: {"protocols": [...], "scans": [...], "attempts": 3, "save": true}
    POST /api/aether/sweep/cancel  stop the test; the tunnel returns to its previous state
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.security import require_auth
from app.services import aether

router = APIRouter(prefix="/api/aether")


def _err(msg: str, code: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": msg}, status_code=code)


@router.get("/status")
async def aether_status(_=Depends(require_auth)):
    return aether.status()


@router.post("/start")
async def aether_start(body: dict, _=Depends(require_auth)):
    try:
        await aether.start(body or None)
    except aether.AetherError as e:
        return _err(str(e))
    return {"ok": True}


@router.post("/stop")
async def aether_stop(_=Depends(require_auth)):
    await aether.stop()
    return {"ok": True}


@router.post("/restart")
async def aether_restart(body: dict, _=Depends(require_auth)):
    try:
        await aether.restart(body or None)
    except aether.AetherError as e:
        return _err(str(e))
    return {"ok": True}


@router.post("/install")
async def aether_install(_=Depends(require_auth)):
    try:
        info = await aether.install()
    except aether.AetherError as e:
        return _err(str(e))
    except Exception as e:  # network errors etc.
        return _err(f"install failed: {e}", 502)
    return {"ok": True, **info}


@router.post("/settings")
async def aether_settings(body: dict, _=Depends(require_auth)):
    try:
        if "outbound_mode" in body:
            await aether.set_outbound_mode(str(body["outbound_mode"]))
        if "auto_start" in body:
            await aether.set_auto_start(bool(body["auto_start"]))
    except aether.AetherError as e:
        return _err(str(e))
    return {"ok": True}


@router.get("/sweep")
async def aether_sweep_status(_=Depends(require_auth)):
    return aether.sweep_status()


@router.post("/sweep/start")
async def aether_sweep_start(body: dict, _=Depends(require_auth)):
    try:
        await aether.start_sweep(
            body.get("protocols"), body.get("scans"), body.get("attempts", 3), body.get("save", True) is not False)
    except aether.AetherError as e:
        return _err(str(e), 409 if "already running" in str(e) else 400)
    return {"ok": True}


@router.post("/sweep/cancel")
async def aether_sweep_cancel(_=Depends(require_auth)):
    return {"ok": await aether.cancel_sweep()}
