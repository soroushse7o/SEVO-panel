"""
Transport / Outbound management API.

Exposes the status of every wire transport the panel can emit
(ws / xhttp / http / tcp) plus a per-user view of which transports
are currently configured for that inbound (same UUID => same user,
multiple inbounds with different transports).
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from app import state
from app.config import settings
from app.security import require_auth
from app.database import fetchall

router = APIRouter()


def _transport_status():
    """Return the panel-level status of each transport."""
    return {
        "ws": {
            "name": "WebSocket",
            "enabled": True,  # ws is always available on the HTTPS port
            "port": 443,
            "security": "tls",
            "path_template": "/ws/{uuid}",
            "description": "WebSocket over the platform HTTPS port. Most compatible.",
        },
        "xhttp": {
            "name": "XHTTP (splithttp)",
            "enabled": getattr(settings, "xhttp_enabled", "true") not in ("false", "0", "no", "off"),
            "port": 443,
            "security": "tls",
            "path_template": "/xhttp1/{uuid}",
            "mode": "stream-one",
            "description": "Xray XHTTP/splithttp (stream-one). Single full-duplex POST, PaaS-friendly. Matches the /xhttp1/{uuid} endpoint.",
        },
        "http": {
            "name": "HTTP",
            "enabled": True,
            "port": 443,
            "security": "tls",
            "path_template": "/http/{uuid}",
            "description": "Plain HTTP/1.1 request/response tunnel over the HTTPS port. PaaS-friendly.",
        },
        "tcp": {
            "name": "Raw TCP",
            "enabled": bool(settings.raw_tcp_enabled),
            "port": int(settings.raw_tcp_public_port) if settings.raw_tcp_public_port else None,
            "security": "none",
            "host": settings.raw_tcp_public_host or None,
            "description": "Raw VLESS TCP on a dedicated TCP Proxy port (no TLS/WS framing).",
        },
    }


@router.get("/api/transports")
async def list_transports(_=Depends(require_auth)):
    return _transport_status()


@router.get("/api/users")
async def list_users(_=Depends(require_auth)):
    """
    Group inbounds by UUID (user). Each user may have multiple transports.
    """
    rows = await fetchall(
        "SELECT uid, label, transport, encryption, limit_bytes, used_bytes, "
        "max_connections, active, expires_at FROM links ORDER BY created_at DESC",
        "SELECT uid, label, transport, encryption, limit_bytes, used_bytes, "
        "max_connections, active, expires_at FROM links ORDER BY created_at DESC",
    )
    users = {}
    for row in rows:
        uid = row["uid"]
        if uid not in users:
            users[uid] = {
                "uuid": uid,
                "label": row.get("label", ""),
                "limit_bytes": row.get("limit_bytes", 0),
                "used_bytes": row.get("used_bytes", 0),
                "max_connections": row.get("max_connections", 0),
                "active": bool(row.get("active", 1)),
                "expires_at": row.get("expires_at"),
                "transports": [],
            }
        users[uid]["transports"].append({
            "transport": row.get("transport", "ws"),
            "encryption": row.get("encryption", "none"),
        })
    return {"users": list(users.values())}


@router.get("/api/outbound-config")
async def get_outbound_config(_=Depends(require_auth)):
    """Return the editable outbound/transport configuration."""
    from app.database import get_setting
    cfg = {}
    for key in ("ob_ws_path", "ob_xhttp_path", "ob_http_path", "ob_tcp_enabled",
                "ob_default_fp", "ob_default_sni", "ob_default_host", "ob_default_alpn",
                "ob_xhttp_mode"):
        cfg[key] = await get_setting(key, "")
    # ensure defaults if empty
    if not cfg["ob_ws_path"]:
        cfg["ob_ws_path"] = "/ws/{uuid}"
    if not cfg["ob_xhttp_path"]:
        cfg["ob_xhttp_path"] = "/xhttp1/{uuid}"
    if not cfg["ob_http_path"]:
        cfg["ob_http_path"] = "/http/{uuid}"
    if not cfg["ob_default_fp"]:
        cfg["ob_default_fp"] = "chrome"
    if not cfg["ob_default_alpn"]:
        cfg["ob_default_alpn"] = "http/1.1"
    if not cfg["ob_xhttp_mode"]:
        cfg["ob_xhttp_mode"] = "stream-one"
    return cfg


@router.post("/api/outbound-config")
async def set_outbound_config(body: dict, _=Depends(require_auth)):
    """Persist editable outbound/transport configuration."""
    from app.database import set_setting
    allowed = {
        "ob_ws_path": str, "ob_xhttp_path": str, "ob_http_path": str,
        "ob_tcp_enabled": str, "ob_default_fp": str, "ob_default_sni": str,
        "ob_default_host": str, "ob_default_alpn": str, "ob_xhttp_mode": str,
    }
    for k, t in allowed.items():
        if k in body:
            v = str(body[k])[:200]
            await set_setting(k, v)
    return {"ok": True}
