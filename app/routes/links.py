"""
Link (inbound) CRUD routes.
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import Response
from app.security import require_auth
from app import state
from app.database import execute as db_exec, fetchall, fetchone
from app.vless import generate_vless_link, generate_vless_json, LinkConfigError
from app.models import LinkCreate
from app.services.upstream import parse_route
from datetime import datetime, timezone, timedelta
import uuid as uuid_lib
import re
import json

router = APIRouter()


def _active_for_db(v):
    """SQLite stores 0/1, PostgreSQL needs a real bool."""
    from app.database import DB_BACKEND
    return bool(v) if DB_BACKEND == "postgresql" else (1 if v else 0)


def _clean_outbound(raw, strict=True):
    """Validate a per-inbound outbound value. strict=False falls back to 'default' (imports)."""
    try:
        return parse_route(raw)
    except ValueError as e:
        if strict:
            raise HTTPException(status_code=400, detail=str(e))
        return "default"


def _get_defaults():
    return {"limit_bytes": 0, "max_connections": 0, "days_valid": 0}


async def _load_defaults():
    result = {}
    for key, default in [("default_limit_bytes", 0), ("default_max_connections", 0), ("default_expiry_days", 0)]:
        row = await fetchone(
            f"SELECT value FROM settings WHERE key='{key}'",
            f"SELECT value FROM settings WHERE key='{key}'",
        )
        if row and row["value"]:
            try:
                result[key] = int(row["value"])
            except Exception:
                result[key] = default
        else:
            result[key] = default
    return result


@router.post("/api/links")
async def create_link(request: Request, _=Depends(require_auth)):
    body = await request.json()
    label = (body.get("label") or "This Server is Free").strip()[:60]
    uuid_input = (body.get("uuid") or "").strip()

    if not label:
        raise HTTPException(status_code=400, detail="Remark is required")
    if not re.match(r"^[a-zA-Z0-9\-_. ]+$", label):
        raise HTTPException(status_code=400, detail="Invalid label characters")

    if uuid_input:
        try:
            uuid_lib.UUID(uuid_input)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid UUID format")
        uid = uuid_input
    else:
        uid = str(uuid_lib.uuid4())

    async with state.links_lock:
        if uid in state.links:
            raise HTTPException(status_code=400, detail="UUID already exists")

    defaults = await _load_defaults()
    limit_val = float(body.get("limit_value") or defaults["default_limit_bytes"])
    limit_unit = body.get("limit_unit") or "GB"
    limit_bytes = 0 if limit_val <= 0 else int(limit_val * (1024**3) if limit_unit == "GB" else limit_val * (1024**2) if limit_unit == "MB" else limit_val)
    max_conn = int(body.get("max_connections") or defaults["default_max_connections"])
    if max_conn < 0:
        max_conn = 0

    days_valid = body.get("days_valid") if body.get("days_valid") is not None else defaults["default_expiry_days"]
    expires_at = None
    try:
        days_valid = int(days_valid)
        if days_valid > 0:
            expires_at = (datetime.now(timezone.utc) + timedelta(days=days_valid)).isoformat()
    except (ValueError, TypeError):
        pass

    now = datetime.now(timezone.utc).isoformat()
    custom_path = body.get("custom_path", "")
    custom_sni = body.get("custom_sni", "")
    custom_host = body.get("custom_host", "")
    custom_fp = body.get("custom_fp", "chrome")
    color = body.get("color", "#39ff14")
    flag = body.get("flag", "")
    fragment = body.get("fragment", "")
    encryption = body.get("encryption", "none")
    if encryption not in ("none", "aes-128-gcm", "aes-256-gcm", "chacha20-poly1305", "zero"):
        encryption = "none"
    transport = "ws"  # WebSocket is the only supported transport
    outbound = _clean_outbound(body.get("outbound"))

    if flag:
        flag = flag.strip()[:2].upper()
        if not re.match(r"^[A-Z]{2}$", flag):
            flag = ""

    link_data = {
        "uid": uid, "label": label, "limit_bytes": limit_bytes, "used_bytes": 0,
        "max_connections": max_conn, "created_at": now, "active": 1,
        "expires_at": expires_at, "custom_path": custom_path, "custom_sni": custom_sni,
        "custom_host": custom_host, "custom_fp": custom_fp, "color": color,
        "flag": flag, "fragment": fragment, "transport": transport, "encryption": encryption,
        "outbound": outbound,
    }

    async with state.links_lock:
        state.links[uid] = link_data

    await db_exec(
        "INSERT INTO links (uid, label, limit_bytes, max_connections, created_at, active, expires_at, custom_path, custom_sni, custom_host, custom_fp, color, flag, fragment, transport, encryption, outbound) VALUES (?,?,?,?,?,1,?,?,?,?,?,?,?,?,?,?,?)",
        "INSERT INTO links (uid, label, limit_bytes, max_connections, created_at, active, expires_at, custom_path, custom_sni, custom_host, custom_fp, color, flag, fragment, transport, encryption, outbound) VALUES ($1,$2,$3,$4,$5,TRUE,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)",
        (uid, label, limit_bytes, max_conn, now, expires_at, custom_path, custom_sni, custom_host, custom_fp, color, flag, fragment, transport, encryption, outbound),
    )

    extra = {"custom_path": custom_path, "custom_sni": custom_sni, "custom_host": custom_host, "custom_fp": custom_fp, "fragment": fragment, "transport": transport, "encryption": encryption}
    state.log_event("Inbound", f"Created inbound {label} ({uid})")
    try:
        vless_link = await generate_vless_link(uid, remark=f"SE7O-{label}", extra=extra)
    except LinkConfigError as e:
        vless_link = None
        state.log_event("Warning", f"Link {uid} created but has no usable link yet: {e}")
    return {
        "uuid": uid, "label": label, "limit_bytes": limit_bytes, "used_bytes": 0,
        "max_connections": max_conn, "active": True, "created_at": now,
        "expires_at": expires_at, "color": color, "flag": flag, "fragment": fragment,
        "transport": transport,
        "outbound": outbound,
        "vless_link": vless_link,
    }


@router.get("/api/links")
async def list_links(_=Depends(require_auth)):
    async with state.links_lock:
        items = list(state.links.values())
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    from app.services.links import count_connections

    result = []
    for row in items:
        uid = row["uid"]
        extra = {
            "custom_path": row.get("custom_path", ""),
            "custom_sni": row.get("custom_sni", ""),
            "custom_host": row.get("custom_host", ""),
            "custom_fp": row.get("custom_fp", "chrome"),
            "fragment": row.get("fragment", ""),
            "transport": row.get("transport", "ws"),
            "encryption": row.get("encryption", "none"),
        }
        try:
            vless_link = await generate_vless_link(uid, remark=f"SE7O-{row['label']}", extra=extra)
        except LinkConfigError:
            vless_link = None
        result.append({
            "uuid": uid,
            "label": row["label"],
            "limit_bytes": row["limit_bytes"],
            "used_bytes": row["used_bytes"],
            "max_connections": row["max_connections"],
            "active": bool(row["active"]),
            "created_at": row["created_at"],
            "expires_at": row.get("expires_at"),
            "color": row.get("color", "#39ff14"),
            "flag": row.get("flag", ""),
            "fragment": row.get("fragment", ""),
            "transport": row.get("transport", "ws"),
            "encryption": row.get("encryption", "none"),
            "outbound": row.get("outbound") or "default",
            "current_connections": await count_connections(uid),
            "vless_link": vless_link,
        })
    return {"links": result}


@router.patch("/api/links/batch")
async def batch_links(request: Request, _=Depends(require_auth)):
    body = await request.json()
    uids = body.get("uids", [])
    action = body.get("action", "")
    async with state.links_lock:
        for uid in uids:
            link = state.links.get(uid)
            if not link:
                continue
            if action == "activate":
                link["active"] = 1
                await db_exec("UPDATE links SET active=1 WHERE uid=?", "UPDATE links SET active=TRUE WHERE uid=$1", (uid,))
            elif action == "deactivate":
                link["active"] = 0
                await db_exec("UPDATE links SET active=0 WHERE uid=?", "UPDATE links SET active=FALSE WHERE uid=$1", (uid,))
            elif action == "reset_usage":
                link["used_bytes"] = 0
                await db_exec("UPDATE links SET used_bytes=0 WHERE uid=?", "UPDATE links SET used_bytes=0 WHERE uid=$1", (uid,))
            elif action == "delete":
                if link.get("label") == "This Server is Free":
                    continue
                await db_exec("DELETE FROM links WHERE uid=?", "DELETE FROM links WHERE uid=$1", (uid,))
                state.links.pop(uid, None)
    return {"ok": True}


@router.patch("/api/links/{uid}")
async def update_link(uid: str, request: Request, _=Depends(require_auth)):
    body = await request.json()
    async with state.links_lock:
        link = state.links.get(uid)
        if not link:
            raise HTTPException(status_code=404, detail="Link not found")
        if link.get("label") == "This Server is Free":
            if "label" in body and body["label"].strip() != "This Server is Free":
                raise HTTPException(status_code=400, detail="Cannot rename default inbound")

    updates = {}
    if "active" in body:
        updates["active"] = int(body["active"])
    if "limit_value" in body:
        val = float(body.get("limit_value") or 0)
        updates["limit_bytes"] = 0 if val <= 0 else int(val * 1024**3)
    if body.get("reset_usage"):
        updates["used_bytes"] = 0
    if "label" in body:
        updates["label"] = str(body["label"])[:60]
    if "max_connections" in body:
        mc = int(body["max_connections"] or 0)
        updates["max_connections"] = mc if mc >= 0 else 0
    if "days_valid" in body:
        try:
            dv = int(body["days_valid"])
            updates["expires_at"] = (datetime.now(timezone.utc) + timedelta(days=dv)).isoformat() if dv > 0 else None
        except (ValueError, TypeError):
            pass
    for field in ("custom_path", "custom_sni", "custom_host", "custom_fp", "color", "fragment", "encryption"):
        if field in body:
            if field == "encryption":
                ev = str(body[field]).strip().lower()
                updates[field] = ev if ev in ("none", "aes-128-gcm", "aes-256-gcm", "chacha20-poly1305", "zero") else "none"
            else:
                updates[field] = str(body[field])[:100]
    if "transport" in body:
        updates["transport"] = "ws"
    if "outbound" in body:
        updates["outbound"] = _clean_outbound(body["outbound"])
    if "flag" in body:
        fv = str(body["flag"]).strip()[:2].upper()
        updates["flag"] = fv if re.match(r"^[A-Z]{2}$", fv) else ""

    if updates:
        async with state.links_lock:
            link.update(updates)
        # Build SQL dynamically (identical column order for both backends)
        db_updates = dict(updates)
        if "active" in db_updates:
            db_updates["active"] = _active_for_db(db_updates["active"])
        cols = list(db_updates)
        set_parts = ", ".join(f"{k} = ?" for k in cols)
        pg_parts = ", ".join(f"{k} = ${i + 1}" for i, k in enumerate(cols))
        vals = tuple(db_updates[k] for k in cols) + (uid,)
        await db_exec(
            f"UPDATE links SET {set_parts} WHERE uid = ?",
            f"UPDATE links SET {pg_parts} WHERE uid = ${len(cols) + 1}",
            vals,
        )

    state.log_event("Inbound", f"Updated inbound {uid}")
    return {"ok": True}


@router.delete("/api/links/{uid}")
async def delete_link(uid: str, _=Depends(require_auth)):
    async with state.links_lock:
        link = state.links.get(uid)
        if link and link.get("label") == "This Server is Free":
            raise HTTPException(status_code=400, detail="Cannot delete default inbound")
    await db_exec("DELETE FROM links WHERE uid = ?", "DELETE FROM links WHERE uid = $1", (uid,))
    async with state.links_lock:
        state.links.pop(uid, None)
    state.log_event("Inbound", f"Deleted inbound {uid}")
    return {"ok": True}


@router.post("/api/links/{uid}/new-uuid")
async def regenerate_uuid(uid: str, _=Depends(require_auth)):
    async with state.links_lock:
        if uid not in state.links:
            raise HTTPException(status_code=404, detail="Link not found")
        link = state.links.pop(uid)
        new_uid = str(uuid_lib.uuid4())
        while new_uid in state.links:
            new_uid = str(uuid_lib.uuid4())
        link["uid"] = new_uid
        state.links[new_uid] = link
    await db_exec("UPDATE links SET uid=? WHERE uid=?", "UPDATE links SET uid=$1 WHERE uid=$2", (new_uid, uid))
    state.log_event("Inbound", f"UUID regenerated for {link['label']}: {uid} -> {new_uid}")
    return {"new_uuid": new_uid}


@router.post("/api/links/{uid}/disconnect")
async def disconnect_link(uid: str, _=Depends(require_auth)):
    async with state.connections_lock:
        to_close = [cid for cid, info in state.connections.items() if info.get("uuid") == uid]
    for cid in to_close:
        ws = state.connection_sockets.get(cid)
        if ws:
            try:
                await ws.close(code=1000, reason="admin disconnect")
            except Exception:
                pass
        async with state.connections_lock:
            state.connections.pop(cid, None)
            state.connection_sockets.pop(cid, None)
    state.log_event("Inbound", f"Disconnected all for {uid}")
    return {"ok": True}


@router.get("/api/links/{uid}/json")
async def link_json(uid: str, _=Depends(require_auth)):
    """Return a standard v2ray/Xray client config JSON for this link, ready
    to import into a JSON-capable client (v2rayN / v2rayNG / NekoBox / etc.)."""
    async with state.links_lock:
        link = state.links.get(uid)
        if not link:
            raise HTTPException(status_code=404, detail="Link not found")
        link = dict(link)

    extra = {
        "custom_path": link.get("custom_path", ""),
        "custom_sni": link.get("custom_sni", ""),
        "custom_host": link.get("custom_host", ""),
        "custom_fp": link.get("custom_fp", "chrome"),
        "fragment": link.get("fragment", ""),
        "transport": link.get("transport", "ws"),
    }
    try:
        cfg = await generate_vless_json(
            uid, remark=link.get("label", "SE7O"), extra=extra
        )
    except LinkConfigError as e:
        raise HTTPException(status_code=400, detail=str(e))

    filename = f"{link.get('label', 'SE7O')}-{uid[:8]}.json"
    return Response(
        content=json.dumps(cfg, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/api/import-links")
async def import_links(request: Request, _=Depends(require_auth)):
    body = await request.json()
    if isinstance(body, dict) and "links" in body:
        body = body["links"]
    if not isinstance(body, list):
        raise HTTPException(status_code=400, detail="Expected a list of links")

    imported = 0
    for item in body:
        if not isinstance(item, dict):
            continue
        uid_input = item.get("uid") or item.get("uuid") or str(uuid_lib.uuid4())
        try:
            uuid_lib.UUID(str(uid_input))
        except (ValueError, AttributeError, TypeError):
            continue
        uid_input = str(uid_input)
        label = str(item.get("label", "Imported"))[:60]
        if not re.match(r"^[a-zA-Z0-9\-_. ]+$", label):
            continue
        try:
            limit_bytes = int(item.get("limit_bytes", 0) or 0)
            used_bytes = int(item.get("used_bytes", 0) or 0)
            max_conn = int(item.get("max_connections", 0) or 0)
        except (ValueError, TypeError):
            continue
        created_at = item.get("created_at") or datetime.now(timezone.utc).isoformat()
        active = 1 if item.get("active", True) else 0
        expires_at = item.get("expires_at")
        custom_path = str(item.get("custom_path", ""))[:100]
        custom_sni = str(item.get("custom_sni", ""))[:100]
        custom_host = str(item.get("custom_host", ""))[:100]
        custom_fp = str(item.get("custom_fp", "chrome"))[:32]
        color = str(item.get("color", "#39ff14"))[:16]
        fragment = str(item.get("fragment", ""))[:100]
        flag = str(item.get("flag", "")).strip()[:2].upper()
        if not re.match(r"^[A-Z]{2}$", flag):
            flag = ""
        transport = "ws"
        outbound = _clean_outbound(item.get("outbound"), strict=False)

        async with state.links_lock:
            if uid_input in state.links:
                continue
            state.links[uid_input] = {
                "uid": uid_input, "label": label, "limit_bytes": limit_bytes,
                "used_bytes": used_bytes, "max_connections": max_conn,
                "created_at": created_at, "active": active, "expires_at": expires_at,
                "custom_path": custom_path, "custom_sni": custom_sni,
                "custom_host": custom_host, "custom_fp": custom_fp,
                "color": color, "flag": flag, "fragment": fragment, "transport": transport,
                "outbound": outbound,
            }
        await db_exec(
            "INSERT INTO links (uid, label, limit_bytes, used_bytes, max_connections, created_at, active, expires_at, custom_path, custom_sni, custom_host, custom_fp, color, flag, fragment, transport, outbound) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            "INSERT INTO links (uid, label, limit_bytes, used_bytes, max_connections, created_at, active, expires_at, custom_path, custom_sni, custom_host, custom_fp, color, flag, fragment, transport, outbound) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)",
            (uid_input, label, limit_bytes, used_bytes, max_conn, created_at, _active_for_db(active),
             expires_at, custom_path, custom_sni, custom_host, custom_fp, color, flag, fragment, transport, outbound),
        )
        imported += 1

    state.log_event("Inbound", f"Imported {imported} inbounds")
    return {"ok": True, "imported": imported}


@router.get("/api/export-links")
async def export_links(_=Depends(require_auth)):
    from fastapi.responses import JSONResponse
    async with state.links_lock:
        return JSONResponse(content=list(state.links.values()))
