"""
Database abstraction layer — supports SQLite (default) and PostgreSQL.
Uses aiosqlite for async SQLite and asyncpg for PostgreSQL.
"""
import asyncio
import os
from typing import Any, Optional

import aiosqlite
from app.config import settings

try:
    import asyncpg
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

_db_conn: Optional[aiosqlite.Connection] = None
_db_lock = asyncio.Lock()
_pg_pool: Optional[Any] = None

if settings.database_url and HAS_POSTGRES:
    DB_BACKEND = "postgresql"
else:
    DB_BACKEND = "sqlite"

INTEGRITY_ERRORS = (aiosqlite.IntegrityError,)
if HAS_POSTGRES and DB_BACKEND == "postgresql":
    INTEGRITY_ERRORS = (aiosqlite.IntegrityError, asyncpg.exceptions.UniqueViolationError)


async def init_db():
    global _db_conn, _pg_pool
    if DB_BACKEND == "postgresql":
        _pg_pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)
        async with _pg_pool.acquire() as conn:
            await conn.execute(SCHEMA_POSTGRES)
            await conn.execute("ALTER TABLE links ADD COLUMN IF NOT EXISTS transport TEXT DEFAULT 'ws'")
            await conn.execute("ALTER TABLE links ADD COLUMN IF NOT EXISTS encryption TEXT DEFAULT 'none'")
            # Per-inbound outbound routing (default = follow the global mode).
            await conn.execute("ALTER TABLE links ADD COLUMN IF NOT EXISTS outbound TEXT DEFAULT 'default'")
            await conn.execute("UPDATE links SET outbound = 'default' WHERE outbound IS NULL OR outbound = ''")
            # WebSocket is the only supported transport: migrate any old
            # xhttp / http / tcp links onto ws.
            await conn.execute("UPDATE links SET transport = 'ws' WHERE transport IS NULL OR transport <> 'ws'")
    else:
        db_path = settings.db_path
        try:
            test_file = os.path.join(os.path.dirname(db_path), ".write_test")
            with open(test_file, "w") as f:
                f.write("ok")
            os.remove(test_file)
        except Exception:
            db_path = "/tmp/panel.db"
        _db_conn = await aiosqlite.connect(db_path)
        _db_conn.row_factory = aiosqlite.Row
        await _db_conn.execute("PRAGMA journal_mode=WAL")
        await _db_conn.executescript(SCHEMA_SQLITE)
        # CREATE TABLE IF NOT EXISTS doesn't add new columns to a table that
        # already existed from a previous version of the schema (e.g. an
        # older deployment's DB file that predates the "transport" column)
        # -- ALTER TABLE is needed to migrate those in place.
        try:
            await _db_conn.execute("ALTER TABLE links ADD COLUMN transport TEXT DEFAULT 'ws'")
        except Exception:
            pass  # column already exists
        try:
            await _db_conn.execute("ALTER TABLE links ADD COLUMN encryption TEXT DEFAULT 'none'")
        except Exception:
            pass  # column already exists
        try:
            # Per-inbound outbound routing (default = follow the global mode).
            await _db_conn.execute("ALTER TABLE links ADD COLUMN outbound TEXT DEFAULT 'default'")
        except Exception:
            pass  # column already exists
        await _db_conn.execute("UPDATE links SET outbound = 'default' WHERE outbound IS NULL OR outbound = ''")
        # WebSocket is the only supported transport: migrate any old
        # xhttp / http / tcp links onto ws.
        await _db_conn.execute("UPDATE links SET transport = 'ws' WHERE transport IS NULL OR transport <> 'ws'")
        await _db_conn.commit()


async def close_db():
    global _db_conn
    if DB_BACKEND == "sqlite" and _db_conn:
        await _db_conn.close()


async def execute(sqlite_q, pg_q="", params=()):
    if DB_BACKEND == "postgresql":
        async with _pg_pool.acquire() as conn:
            await conn.execute(pg_q or sqlite_q, *params)
    else:
        async with _db_lock:
            await _db_conn.execute(sqlite_q, params)
            await _db_conn.commit()


async def fetchall(sqlite_q, pg_q="", params=()):
    if DB_BACKEND == "postgresql":
        async with _pg_pool.acquire() as conn:
            rows = await conn.fetch(pg_q or sqlite_q, *params)
            return [dict(r) for r in rows]
    else:
        async with _db_lock:
            cur = await _db_conn.execute(sqlite_q, params)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def fetchone(sqlite_q, pg_q="", params=()):
    if DB_BACKEND == "postgresql":
        async with _pg_pool.acquire() as conn:
            row = await conn.fetchrow(pg_q or sqlite_q, *params)
            return dict(row) if row else None
    else:
        async with _db_lock:
            cur = await _db_conn.execute(sqlite_q, params)
            row = await cur.fetchone()
            return dict(row) if row else None


LINKS_COLS = (
    "uid TEXT PRIMARY KEY, label TEXT NOT NULL, "
    "limit_bytes BIGINT DEFAULT 0, used_bytes BIGINT DEFAULT 0, "
    "max_connections INT DEFAULT 0, created_at TEXT NOT NULL, "
    "active BOOLEAN DEFAULT TRUE, expires_at TEXT, "
    "custom_path TEXT DEFAULT '', custom_sni TEXT DEFAULT '', "
    "custom_host TEXT DEFAULT '', custom_fp TEXT DEFAULT 'chrome', "
    "color TEXT DEFAULT '#39ff14', flag TEXT DEFAULT '', fragment TEXT DEFAULT '', "
    "transport TEXT DEFAULT 'ws', outbound TEXT DEFAULT 'default'"
)

SCHEMA_SQLITE = (
    "CREATE TABLE IF NOT EXISTS links (" + LINKS_COLS + ");"
    "CREATE TABLE IF NOT EXISTS hourly_traffic (hour TEXT PRIMARY KEY, bytes INTEGER DEFAULT 0);"
    "CREATE TABLE IF NOT EXISTS daily_traffic (day TEXT PRIMARY KEY, bytes INTEGER DEFAULT 0);"
    "CREATE TABLE IF NOT EXISTS custom_addresses (id INTEGER PRIMARY KEY AUTOINCREMENT, address TEXT NOT NULL UNIQUE);"
    "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);"
    "CREATE TABLE IF NOT EXISTS login_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL, ip TEXT, success INTEGER DEFAULT 1, user_agent TEXT DEFAULT '', path TEXT DEFAULT '');"
)

SCHEMA_POSTGRES = (
    "CREATE TABLE IF NOT EXISTS links (" + LINKS_COLS + ");"
    "CREATE TABLE IF NOT EXISTS hourly_traffic (hour TEXT PRIMARY KEY, bytes BIGINT DEFAULT 0);"
    "CREATE TABLE IF NOT EXISTS daily_traffic (day TEXT PRIMARY KEY, bytes BIGINT DEFAULT 0);"
    "CREATE TABLE IF NOT EXISTS custom_addresses (id SERIAL PRIMARY KEY, address TEXT NOT NULL UNIQUE);"
    "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);"
    "CREATE TABLE IF NOT EXISTS login_logs (id SERIAL PRIMARY KEY, timestamp TEXT NOT NULL, ip TEXT, success BOOLEAN DEFAULT TRUE, user_agent TEXT DEFAULT '', path TEXT DEFAULT '');"
)


async def get_setting(key: str, default: str = "") -> str:
    """Read a single key from the settings table (SQLite + Postgres)."""
    try:
        rows = await fetchall(
            "SELECT value FROM settings WHERE key = ?",
            "SELECT value FROM settings WHERE key = $1",
            (key,),
        )
        if rows:
            return rows[0]["value"] or default
    except Exception:
        pass
    return default


async def set_setting(key: str, value: str) -> None:
    """Upsert a single key into the settings table (SQLite + Postgres)."""
    await execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        "INSERT INTO settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value = $2",
        (key, value),
    )
