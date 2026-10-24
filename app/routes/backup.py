"""
Backup and restore routes.
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from app.security import require_auth
from app import state
from app.database import execute as db_exec, fetchall, DB_BACKEND
from app.utils import validate_address
from datetime import datetime, timezone
import uuid as uuid_lib

router = APIRouter()


def _safe_route(raw):
    from app.services.upstream import parse_route
    try:
        return parse_route(raw)
    except ValueError:
        return "default"


MAX_RESTORE_SIZE = 5 * 1024 * 1024


@router.get("/api/backup/full")
async def full_backup(_=Depends(require_auth)):
    async with state.links_lock:
        links = list(state.links.values())
    async with state.addresses_lock:
        addrs = list(state.addresses)
    rows = await fetchall("SELECT key, value FROM settings", "SELECT key, value FROM settings")
    settings = {r["key"]: r["value"] for r in rows}
    return {"links": links, "addresses": addrs, "settings": settings}


@router.post("/api/restore")
async def restore_backup(request: Request, _=Depends(require_auth)):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_RESTORE_SIZE:
        raise HTTPException(status_code=413, detail="Backup too large")

    body = await request.json()

    if "settings" in body:
        for k, v in body["settings"].items():
            await db_exec(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                "INSERT INTO settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value = $2",
                (k, str(v)),
            )

    if "addresses" in body:
        await db_exec("DELETE FROM custom_addresses", "DELETE FROM custom_addresses")
        async with state.addresses_lock:
            state.addresses.clear()
            for a in body["addresses"]:
                addr = str(a).strip()
                if addr and validate_address(addr):
                    state.addresses.append(addr)
                    try:
                        await db_exec(
                            "INSERT INTO custom_addresses (address) VALUES (?)",
                            "INSERT INTO custom_addresses (address) VALUES ($1)",
                            (addr,),
                        )
                    except Exception:
                        pass

    if "links" in body:
        await db_exec("DELETE FROM links", "DELETE FROM links")
        async with state.links_lock:
            state.links.clear()
        for link in body["links"]:
            uid = link.get("uid") or str(uuid_lib.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            link_data = {
                "uid": uid,
                "label": link.get("label", "Restored"),
                "limit_bytes": int(link.get("limit_bytes", 0)),
                "used_bytes": int(link.get("used_bytes", 0)),
                "max_connections": int(link.get("max_connections", 0)),
                "created_at": link.get("created_at", now),
                "active": 1 if link.get("active", True) else 0,
                "expires_at": link.get("expires_at"),
                "custom_path": link.get("custom_path", ""),
                "custom_sni": link.get("custom_sni", ""),
                "custom_host": link.get("custom_host", ""),
                "custom_fp": link.get("custom_fp", "chrome"),
                "color": link.get("color", "#39ff14"),
                "flag": link.get("flag", ""),
                "fragment": link.get("fragment", ""),
                "transport": "ws",
                "outbound": _safe_route(link.get("outbound")),
            }
            async with state.links_lock:
                state.links[uid] = link_data
            await db_exec(
                "INSERT INTO links (uid, label, limit_bytes, used_bytes, max_connections, created_at, active, expires_at, custom_path, custom_sni, custom_host, custom_fp, color, flag, fragment, transport, outbound) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                "INSERT INTO links (uid, label, limit_bytes, used_bytes, max_connections, created_at, active, expires_at, custom_path, custom_sni, custom_host, custom_fp, color, flag, fragment, transport, outbound) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)",
                (uid, link_data["label"], link_data["limit_bytes"], link_data["used_bytes"],
                 link_data["max_connections"], link_data["created_at"],
                 bool(link_data["active"]) if DB_BACKEND == "postgresql" else link_data["active"],
                 link_data["expires_at"], link_data["custom_path"], link_data["custom_sni"],
                 link_data["custom_host"], link_data["custom_fp"], link_data["color"],
                 link_data["flag"], link_data["fragment"], link_data["transport"], link_data["outbound"]),
            )

    return {"ok": True}
