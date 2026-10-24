"""
Health monitoring endpoint (public, no authentication, no secrets).

    GET /health        (alias: GET /api/health, HEAD supported)

Returns JSON with application status, uptime and system health metrics.
HTTP 200 when healthy / degraded, HTTP 503 when a critical check fails
(database unreachable), so load balancers and uptime monitors can use the
status code alone.
"""
import asyncio
import os
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app import state
from app.config import settings
from app.database import DB_BACKEND, fetchone

router = APIRouter()
VERSION = "3.1.0"

try:
    import psutil
except ImportError:  # psutil is in requirements.txt, but never let health crash
    psutil = None


def _system_metrics() -> dict:
    m: dict = {}
    try:
        la = os.getloadavg()
        m["load_avg"] = [round(x, 2) for x in la]
    except (OSError, AttributeError):
        pass
    m["cpu_count"] = os.cpu_count()
    if psutil:
        try:
            m["cpu_percent"] = psutil.cpu_percent(interval=None)
            vm = psutil.virtual_memory()
            m["memory"] = {"total_mb": round(vm.total / 1048576), "used_mb": round(vm.used / 1048576),
                           "percent": vm.percent}
            data_dir = os.path.dirname(settings.db_path) if settings.db_path.startswith("/") else "."
            if not os.path.isdir(data_dir):
                data_dir = "."
            du = psutil.disk_usage(data_dir)
            m["disk"] = {"total_gb": round(du.total / 1073741824, 1), "used_gb": round(du.used / 1073741824, 1),
                         "percent": du.percent}
            p = psutil.Process()
            m["process"] = {"rss_mb": round(p.memory_info().rss / 1048576, 1), "threads": p.num_threads(),
                            "pid": p.pid}
        except Exception:
            pass
    return m


async def _db_check() -> dict:
    t0 = time.monotonic()
    try:
        await asyncio.wait_for(fetchone("SELECT 1 AS ok", "SELECT 1 AS ok"), timeout=3.0)
        return {"ok": True, "backend": DB_BACKEND, "latency_ms": round((time.monotonic() - t0) * 1000, 1)}
    except Exception as e:
        return {"ok": False, "backend": DB_BACKEND, "error": type(e).__name__}


@router.api_route("/health", methods=["GET", "HEAD"])
@router.api_route("/api/health", methods=["GET", "HEAD"])
async def health():
    now = time.time()
    db = await _db_check()

    async with state.connections_lock:
        active_conns = len(state.connections)
    async with state.links_lock:
        links_total = len(state.links)
        links_active = sum(1 for l in state.links.values() if l.get("active"))

    outbound = {}
    try:
        from app.services import aether, upstream
        outbound = {"mode": upstream.current_mode(), "warp_phase": aether.S.phase,
                    "warp_connected": aether.is_connected()}
    except Exception:
        pass

    checks = {"database": db["ok"], "state_loaded": links_total > 0}
    status = "ok" if all(checks.values()) else ("error" if not db["ok"] else "degraded")

    body = {
        "status": status,
        "version": VERSION,
        "time": int(now),
        "uptime": {
            "process_seconds": int(now - state.process_start),
            "app_seconds": int(now - state.stats.get("start_time", state.process_start)),
        },
        "checks": checks,
        "database": db,
        "app": {
            "active_connections": active_conns,
            "inbounds_total": links_total,
            "inbounds_active": links_active,
            "total_requests": state.stats.get("total_requests", 0),
            "total_errors": state.stats.get("total_errors", 0),
            "outbound": outbound,
        },
        "system": _system_metrics(),
    }
    return JSONResponse(body, status_code=503 if status == "error" else 200,
                        headers={"Cache-Control": "no-store"})
