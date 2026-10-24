"""
Dashboard statistics routes.
"""
from fastapi import APIRouter, Depends
from app.security import require_auth
from app import state
from app.database import fetchall, fetchone
from datetime import datetime, timezone
import psutil

router = APIRouter()


@router.get("/stats")
async def get_stats(_=Depends(require_auth)):
    async with state.connections_lock:
        conn_count = len(state.connections)

    cpu = None
    try:
        cpu = psutil.cpu_percent(interval=0.1)
    except Exception:
        pass

    mem = 0
    try:
        mem = psutil.virtual_memory().percent
    except Exception:
        pass

    disk_pct = 0
    disk_free = 0.0
    try:
        d = psutil.disk_usage("/")
        disk_pct = d.percent
        disk_free = round(d.free / (1024**3), 1)
    except Exception:
        pass

    now = datetime.now(timezone.utc) + __import__("datetime").timedelta(hours=state.timezone_offset)
    today_str = now.strftime("%Y-%m-%d")

    rows = await fetchall(
        "SELECT hour, bytes FROM hourly_traffic WHERE hour LIKE ? ORDER BY hour ASC",
        "SELECT hour, bytes FROM hourly_traffic WHERE hour LIKE $1 ORDER BY hour ASC",
        (today_str + "%",),
    )
    hourly_dict = {f"{h:02d}:00": 0 for h in range(24)}
    for r in rows:
        h = r["hour"][-5:] if len(r["hour"]) >= 5 else r["hour"]
        if h in hourly_dict:
            hourly_dict[h] = r["bytes"]

    month_start = now.strftime("%Y-%m") + "-01"
    month_rows = await fetchall(
        "SELECT SUM(bytes) as total FROM daily_traffic WHERE day >= ?",
        "SELECT SUM(bytes) as total FROM daily_traffic WHERE day >= $1",
        (month_start,),
    )
    monthly_bytes = month_rows[0]["total"] if month_rows and month_rows[0]["total"] else 0

    monthly_limit = 0
    lim_row = await fetchone(
        "SELECT value FROM settings WHERE key='monthly_limit_gb'",
        "SELECT value FROM settings WHERE key='monthly_limit_gb'",
    )
    if lim_row and lim_row["value"]:
        try:
            monthly_limit = float(lim_row["value"]) * 1024**3
        except Exception:
            pass

    import time as _time
    uptime_seconds = int(_time.time() - state.stats.get("start_time", _time.time()))
    days, rem = divmod(uptime_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    uptime_str = (f"{days}d " if days else "") + f"{hours:02d}:{minutes:02d}"

    return {
        "active_connections": conn_count,
        "total_traffic_mb": round(state.stats["total_bytes"] / (1024 * 1024), 2),
        "total_requests": state.stats["total_requests"],
        "total_errors": state.stats["total_errors"],
        "upload_bytes": state.stats["upload_bytes"],
        "download_bytes": state.stats["download_bytes"],
        "uptime": uptime_str,
        "cpu_percent": cpu,
        "memory_percent": mem,
        "disk_percent": disk_pct,
        "disk_free_gb": disk_free,
        "hourly_traffic": {f"{h:02d}:00": hourly_dict[f"{h:02d}:00"] for h in range(24)},
        "links_count": len(state.links),
        "domain": state.stats.get("domain", ""),
        "monthly_usage_bytes": monthly_bytes,
        "monthly_limit_bytes": int(monthly_limit),
    }


@router.get("/connections")
async def get_connections(_=Depends(require_auth)):
    """Live per-user connection IPs + connect time."""
    out = {}
    async with state.connections_lock:
        for cid, info in state.connections.items():
            uid = info.get("uuid")
            if not uid:
                continue
            ip = info.get("ip", "unknown")
            connected_at = info.get("connected_at", "")
            out.setdefault(uid, []).append({"ip": ip, "connected_at": connected_at})
    return out
