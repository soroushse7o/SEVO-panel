"""
Best Endpoint Finder API (all endpoints require the panel session).

    GET  /api/endpoints/presets          Cloudflare ranges, the panel's Clean-IP list, defaults
    POST /api/endpoints/scan             start a scan  -> {job_id}
    GET  /api/endpoints/job/{job_id}     progress + ranked results
    POST /api/endpoints/job/{job_id}/cancel
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app import state
from app.config import settings
from app.security import require_auth
from app.services import endpoint_finder as ef

router = APIRouter(prefix="/api/endpoints")


def _err(msg: str, code: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": msg}, status_code=code)


@router.get("/presets")
async def presets(_=Depends(require_auth)):
    async with state.addresses_lock:
        clean = list(state.addresses)
    domain = settings.domain
    return {
        "cloudflare_ranges": ef.CLOUDFLARE_RANGES,
        "clean_ips": clean,
        "default_sni": domain if domain != "localhost" else "www.cloudflare.com",
        "default_port": 443,
        "modes": list(ef.MODES),
        "limits": {"max_targets": ef.MAX_TARGETS, "max_concurrency": ef.MAX_CONCURRENCY},
    }


@router.post("/scan")
async def scan(body: dict, _=Depends(require_auth)):
    targets = body.get("targets", "")
    if isinstance(targets, list):
        targets = "\n".join(str(t) for t in targets)
    try:
        job_id = ef.start_job(str(targets), body)
    except ef.FinderError as e:
        return _err(str(e), 409 if "already running" in str(e) else 400)
    state.log_event("Endpoint", f"Endpoint scan started ({job_id})")
    return {"ok": True, "job_id": job_id}


@router.get("/job/{job_id}")
async def job(job_id: str, _=Depends(require_auth)):
    j = ef.get_job(job_id)
    if not j:
        return _err("job not found", 404)
    return j


@router.post("/job/{job_id}/cancel")
async def cancel(job_id: str, _=Depends(require_auth)):
    return {"ok": ef.cancel_job(job_id)}
