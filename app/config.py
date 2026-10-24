"""
Centralized configuration — all secrets and tunables in one place.
Reads from environment variables with sensible defaults.
"""
import os
import secrets
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Config:
    # Server
    port: int = int(os.environ.get("PORT", 8080))
    host: str = "0.0.0.0"
    secret_key: str = os.environ.get("SECRET_KEY", secrets.token_urlsafe(32))
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080  # 7 days

    # Database
    db_path: str = os.environ.get("DB_PATH", "/data/panel.db")
    database_url: str = os.environ.get("DATABASE_URL", "")

    # Auth
    admin_username: str = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password: str = os.environ.get("ADMIN_PASSWORD", "admin")

    # MTProto (Telegram) proxy
    mtproxy_enabled: bool = os.environ.get("MTPROXY_ENABLED", "true").lower() not in ("0", "false", "no", "off")
    mtproxy_port: int = int(os.environ.get("MTPROXY_PORT", 443))
    mtproxy_secret: str = os.environ.get("MTPROXY_SECRET", "")
    mtproxy_fake_domain: str = os.environ.get("MTPROXY_FAKE_DOMAIN", "www.cloudflare.com")
    mtproxy_bin: str = os.environ.get("MTPROXY_BIN", "")
    mtproxy_concurrency: int = int(os.environ.get("MTPROXY_CONCURRENCY", 4096))
    mtproxy_public_host: str = os.environ.get("MTPROXY_PUBLIC_HOST", "")
    mtproxy_public_port: str = os.environ.get("MTPROXY_PUBLIC_PORT", "")

    # Aether (Cloudflare tunnel) outbound -- see app/services/aether.py
    # AETHER_OUTBOUND: direct (default) | aether (fail-closed) | auto. When set, it overrides the panel setting.
    aether_bin: str = os.environ.get("AETHER_BIN", "")
    aether_dir: str = os.environ.get("AETHER_DIR", "")
    aether_version: str = os.environ.get("AETHER_VERSION", "")
    aether_outbound: str = os.environ.get("AETHER_OUTBOUND", "")

    # Domain (auto-detected from platform env vars)
    @property
    def domain(self) -> str:
        return (
            os.environ.get("DOMAIN")
            or os.environ.get("RENDER_EXTERNAL_URL")
            or os.environ.get("RAILWAY_PUBLIC_DOMAIN")
            or "localhost"
        ).replace("https://", "").replace("http://", "")

    # Limits
    rate_limit_per_minute: int = 100
    max_connections_per_link: int = 0  # 0 = unlimited
    link_cache_ttl: int = 60
    traffic_buffer_flush_interval: int = 10
    usage_sync_interval: int = 30
    idle_connection_timeout: int = 300
    log_max_entries: int = 2000
    unlimited_quota_bytes: int = 53_687_091_200_000  # ~50 TB

    # Session
    session_cookie: str = "SE7OSNA_session"


# Singleton
settings = Config()
