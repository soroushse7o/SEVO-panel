"""
SE7O-SNA Panel v3.0 — Modular Architecture
==========================================
Single command to run: python main.py
"""
import os
import sys
import asyncio
import logging
import logging.config
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import init_db, close_db, DB_BACKEND, fetchall, execute as db_exec
from app import state
from app.services import links as links_service
from app.services.traffic import flush_loop, sync_usage_loop, cleanup_link_cache_loop
from app.services.keepalive import simple_loop, advanced_loop
from app.services.telegram import report_loop
from app.services.links import auto_disable_expired
from app.services import mtproxy as mtproxy_service
from app.services import raw_tcp as raw_tcp_service
from app.services import aether as aether_service

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        }
    },
    "handlers": {"json_console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"level": "INFO", "handlers": ["json_console"]},
}
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger("SE7OSNA")

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database (%s)...", DB_BACKEND)
    await init_db()
    await links_service.load_all()

    rows = await fetchall("SELECT key, value FROM settings", "SELECT key, value FROM settings")
    for row in rows:
        key, value = row["key"], row["value"]
        if key == "jwt_secret_key" and value:
            state.secret_key = value
        elif key == "admin_password_hash" and value:
            state.admin_password_hash = value
        elif key == "admin_username" and value:
            state.admin_username = value
        elif key == "timezone_offset" and value:
            try:
                state.timezone_offset = float(value)
            except Exception:
                pass
        elif key == "keep_alive_enabled" and value:
            state.keep_alive_enabled = value == "1"
        elif key == "keep_alive_mode" and value:
            state.keep_alive_mode = value
        elif key == "keep_alive_interval" and value:
            try:
                state.keep_alive_interval = max(60, int(value))
            except Exception:
                pass
        elif key == "log_enabled" and value:
            state.logging_enabled = value == "1"

    # --- SECRET_KEY / ADMIN_USERNAME / ADMIN_PASSWORD ---
    # These three used to be seeded into the DB only on the very first boot
    # (guarded by "if not state.X"), so once a value existed in the DB,
    # changing the env var on the host and redeploying had NO EFFECT — the
    # stale DB value silently won forever. We now treat an *explicitly set*
    # env var (present in os.environ, not just the dataclass default) as an
    # operator override that always takes precedence over the DB, exactly
    # like the MTProxy settings already do. If the env var is absent, we
    # fall back to whatever is already persisted (or generate one on first
    # run), so an operator who removes the env var doesn't get logged out.
    import secrets as _secrets
    import bcrypt as _bcrypt

    env_secret_key = os.environ.get("SECRET_KEY", "").strip()
    if env_secret_key and env_secret_key != state.secret_key:
        state.secret_key = env_secret_key
        await db_exec(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('jwt_secret_key', ?)",
            "INSERT INTO settings (key, value) VALUES ('jwt_secret_key', $1) ON CONFLICT (key) DO UPDATE SET value = $1",
            (state.secret_key,),
        )
        logger.info("SECRET_KEY overridden from environment")
    elif not state.secret_key:
        state.secret_key = _secrets.token_urlsafe(32)
        await db_exec(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('jwt_secret_key', ?)",
            "INSERT INTO settings (key, value) VALUES ('jwt_secret_key', $1) ON CONFLICT (key) DO UPDATE SET value = $1",
            (state.secret_key,),
        )

    env_admin_username = os.environ.get("ADMIN_USERNAME", "").strip()
    if env_admin_username and env_admin_username != state.admin_username:
        state.admin_username = env_admin_username
        await db_exec(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('admin_username', ?)",
            "INSERT INTO settings (key, value) VALUES ('admin_username', $1) ON CONFLICT (key) DO UPDATE SET value = $1",
            (state.admin_username,),
        )
        logger.info("ADMIN_USERNAME overridden from environment")
    elif not state.admin_username:
        state.admin_username = settings.admin_username
        await db_exec(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('admin_username', ?)",
            "INSERT INTO settings (key, value) VALUES ('admin_username', $1) ON CONFLICT (key) DO UPDATE SET value = $1",
            (state.admin_username,),
        )

    env_admin_password = os.environ.get("ADMIN_PASSWORD", "").strip()
    if env_admin_password:
        # Only re-hash + write to the DB if the env password actually
        # differs from what's stored, so we don't churn a new bcrypt hash
        # (and a new column write) on every single restart.
        matches_current = False
        if state.admin_password_hash:
            try:
                matches_current = _bcrypt.checkpw(env_admin_password.encode("utf-8"), state.admin_password_hash.encode("utf-8"))
            except Exception:
                matches_current = False
        if not matches_current:
            state.admin_password_hash = _bcrypt.hashpw(env_admin_password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")
            await db_exec(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('admin_password_hash', ?)",
                "INSERT INTO settings (key, value) VALUES ('admin_password_hash', $1) ON CONFLICT (key) DO UPDATE SET value = $1",
                (state.admin_password_hash,),
            )
            logger.info("ADMIN_PASSWORD overridden from environment")
    elif not state.admin_password_hash:
        state.admin_password_hash = _bcrypt.hashpw(settings.admin_password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")
        await db_exec(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('admin_password_hash', ?)",
            "INSERT INTO settings (key, value) VALUES ('admin_password_hash', $1) ON CONFLICT (key) DO UPDATE SET value = $1",
            (state.admin_password_hash,),
        )

    asyncio.create_task(simple_loop())
    asyncio.create_task(advanced_loop())
    asyncio.create_task(auto_disable_expired())
    asyncio.create_task(report_loop())
    asyncio.create_task(flush_loop())
    asyncio.create_task(sync_usage_loop())
    asyncio.create_task(cleanup_link_cache_loop())

    await mtproxy_service.start()
    await raw_tcp_service.start()
    await aether_service.init()

    logger.info("SE7O-SNA Panel v3.0 started")
    yield
    await aether_service.shutdown()
    await mtproxy_service.stop()
    await raw_tcp_service.stop()
    await close_db()


def create_app() -> FastAPI:
    app = FastAPI(title="SE7O-SNA Panel v2", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    # NOTE: allow_origins=["*"] together with allow_credentials=True is
    # rejected by every modern browser (CORS spec forbids a wildcard origin
    # on credentialed requests), so it silently broke any cross-origin use
    # of the cookie-authenticated API. The panel's own frontend is served
    # same-origin and never needed CORS credentials in the first place.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], allow_credentials=False,
        allow_methods=["*"], allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    from app.routes.auth import router as auth_router
    from app.routes.links import router as links_router
    from app.routes.addresses import router as addresses_router
    from app.routes.tunnel import router as tunnel_router
    from app.routes.stats import router as stats_router
    from app.routes.settings import router as settings_router
    from app.routes.subscription import router as sub_router
    from app.routes.backup import router as backup_router
    from app.routes.mtproxy import router as mtproxy_router
    from app.routes.panel import router as panel_router
    from app.routes.transports import router as transports_router
    from app.routes.aether import router as aether_router

    app.include_router(auth_router)
    app.include_router(links_router)
    app.include_router(addresses_router)
    app.include_router(tunnel_router)
    app.include_router(stats_router)
    app.include_router(settings_router)
    app.include_router(sub_router)
    app.include_router(backup_router)
    app.include_router(mtproxy_router)
    app.include_router(panel_router)
    app.include_router(transports_router)
    app.include_router(aether_router)

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", settings.port))
    logger.info("Starting on port %d", port)
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        proxy_headers=True,
        forwarded_allow_ips="*",
        log_config=LOGGING_CONFIG,
        access_log=False,
    )
