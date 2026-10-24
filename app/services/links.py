"""
Link (inbound) service layer — business logic for CRUD operations.
Decouples routes from database and state access.
"""
import asyncio
from datetime import datetime, timezone, timedelta
import uuid as uuid_lib
from app import state
from app.database import execute as db_exec, fetchone
from app.vless import generate_vless_link


DEFAULT_ADDRESSES = [
    "69.46.46.175", "69.46.46.174", "69.46.46.18", "69.46.46.242",
    "69.46.46.85", "69.46.46.240", "69.46.46.4", "69.46.46.30",
    "69.46.46.145", "69.46.46.27", "69.46.46.55", "69.46.46.197",
    "69.46.46.163", "69.46.46.8", "69.46.46.51",
    "blog.railway.com", "lantern.railway.com", "luminaire.railway.com",
]


async def load_all():
    """Load all links and clean-IP addresses from database into memory."""
    from app.database import fetchall, fetchone
    rows = await fetchall("SELECT * FROM links", "SELECT * FROM links")
    async with state.links_lock:
        for r in rows:
            state.links[r["uid"]] = dict(r)

    addr_rows = await fetchall("SELECT address FROM custom_addresses", "SELECT address FROM custom_addresses")
    addresses = [r["address"] for r in addr_rows]

    # The clean-IP list is always exactly DEFAULT_ADDRESSES. Every startup
    # the table is rebuilt from the code so edits to DEFAULT_ADDRESSES are
    # always reflected after a restart (no manual entries are preserved --
    # add custom IPs by editing DEFAULT_ADDRESSES or via the panel UI).
    try:
        await db_exec("DELETE FROM custom_addresses", "DELETE FROM custom_addresses")
    except Exception:
        pass
    for addr in DEFAULT_ADDRESSES:
        try:
            await db_exec(
                "INSERT INTO custom_addresses (address) VALUES (?)",
                "INSERT INTO custom_addresses (address) VALUES ($1)",
                (addr,),
            )
        except Exception:
            pass
    addr_rows = await fetchall("SELECT address FROM custom_addresses",
                               "SELECT address FROM custom_addresses")
    addresses = [r["address"] for r in addr_rows]

    async with state.addresses_lock:
        state.addresses.clear()
        state.addresses.extend(addresses)

    # Calculate total usage
    total = sum(link.get("used_bytes", 0) for link in state.links.values())
    state.stats["total_bytes"] = total

    # Create default link if none exist
    if not state.links:
        default_uid = str(uuid_lib.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        default_link = {
            "uid": default_uid, "label": "This Server is Free",
            "limit_bytes": 0, "used_bytes": 0,
            "max_connections": 0, "created_at": now, "active": 1,
            "expires_at": None, "custom_path": "", "custom_sni": "",
            "custom_host": "", "custom_fp": "chrome", "color": "#39ff14",
            "flag": "", "fragment": "",
        }
        async with state.links_lock:
            state.links[default_uid] = default_link
        await db_exec(
            "INSERT INTO links (uid, label, limit_bytes, max_connections, created_at, active, expires_at, flag, fragment) VALUES (?,?,?,?,?,1,?,'','')",
            "INSERT INTO links (uid, label, limit_bytes, max_connections, created_at, active, expires_at, flag, fragment) VALUES ($1,$2,$3,$4,$5,TRUE,$6,'','')",
            (default_uid, "This Server is Free", 0, 0, now, None),
        )


async def auto_disable_expired():
    """Periodically disable expired links."""
    while True:
        await asyncio.sleep(60)
        try:
            row = await fetchone(
                "SELECT value FROM settings WHERE key='auto_disable_enabled'",
                "SELECT value FROM settings WHERE key='auto_disable_enabled'",
            )
            if row and row["value"] != "1":
                continue
            now = datetime.now(timezone.utc)
            async with state.links_lock:
                for uid, link in state.links.items():
                    if link.get("active") and link.get("expires_at"):
                        exp = _parse_dt(link["expires_at"])
                        if exp and exp < now:
                            link["active"] = 0
                            await db_exec(
                                "UPDATE links SET active = 0 WHERE uid = ?",
                                "UPDATE links SET active = FALSE WHERE uid = $1",
                                (uid,),
                            )
                            state.log_event("Auto", f"Expired inbound {link['label']} auto-disabled")
        except Exception:
            pass


async def count_connections(uid: str) -> int:
    async with state.connections_lock:
        return sum(1 for info in state.connections.values() if info.get("uuid") == uid)


def _parse_dt(raw: str):
    try:
        s = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return None
