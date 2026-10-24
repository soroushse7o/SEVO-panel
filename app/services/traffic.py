"""
Traffic buffering and database sync.
Buffers traffic in memory, flushes to DB every N seconds.
Syncs per-link usage periodically.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from app import state
from app.database import execute as db_exec, DB_BACKEND


async def add_to_buffer(hour: str, day: str, size: int):
    async with state.traffic_buffer_lock:
        state.traffic_buffer["hourly"][hour] += size
        state.traffic_buffer["daily"][day] += size


async def flush_loop():
    """Periodically flush traffic buffer to database."""
    from app.config import settings
    while True:
        await asyncio.sleep(settings.traffic_buffer_flush_interval)
        try:
            async with state.traffic_buffer_lock:
                if not state.traffic_buffer["hourly"] and not state.traffic_buffer["daily"]:
                    continue
                hourly = dict(state.traffic_buffer["hourly"])
                daily = dict(state.traffic_buffer["daily"])
                state.traffic_buffer["hourly"].clear()
                state.traffic_buffer["daily"].clear()

            # NOTE: sqlite's "?" placeholders bind positionally (each "?" needs
            # its own value) while postgres lets us reuse "$2" twice for one
            # value, so the two backends need differently-shaped param tuples.
            for hour, bytes_val in hourly.items():
                params = (hour, bytes_val, bytes_val) if DB_BACKEND != "postgresql" else (hour, bytes_val)
                await db_exec(
                    "INSERT INTO hourly_traffic (hour, bytes) VALUES (?,?) ON CONFLICT(hour) DO UPDATE SET bytes = bytes + ?",
                    "INSERT INTO hourly_traffic (hour, bytes) VALUES ($1,$2) ON CONFLICT (hour) DO UPDATE SET bytes = hourly_traffic.bytes + $2",
                    params,
                )
            for day, bytes_val in daily.items():
                params = (day, bytes_val, bytes_val) if DB_BACKEND != "postgresql" else (day, bytes_val)
                await db_exec(
                    "INSERT INTO daily_traffic (day, bytes) VALUES (?,?) ON CONFLICT(day) DO UPDATE SET bytes = bytes + ?",
                    "INSERT INTO daily_traffic (day, bytes) VALUES ($1,$2) ON CONFLICT (day) DO UPDATE SET bytes = daily_traffic.bytes + $2",
                    params,
                )
        except Exception as e:
            pass


async def sync_usage_loop():
    """Periodically persist in-memory usage to database."""
    from app.config import settings
    while True:
        await asyncio.sleep(settings.usage_sync_interval)
        try:
            async with state.links_lock:
                items = list(state.links.items())
            for uid, link in items:
                await db_exec(
                    "UPDATE links SET used_bytes = ? WHERE uid = ?",
                    "UPDATE links SET used_bytes = $1 WHERE uid = $2",
                    (link["used_bytes"], uid),
                )
        except Exception:
            pass


async def cleanup_link_cache_loop():
    """Remove expired link cache entries."""
    import time
    while True:
        await asyncio.sleep(600)
        now = time.time()
        expired = [k for k, v in state.link_cache.items() if v["expires"] <= now]
        for k in expired:
            state.link_cache.pop(k, None)
