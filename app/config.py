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

    # XHTTP transport (Xray "splithttp", stream-up mode) — served on the
    # same HTTP port as the WebSocket transport, no extra port needed.
    xhttp_enabled: bool = os.environ.get("XHTTP_ENABLED", "true").lower() not in ("0", "false", "no", "off")

    # Optional second raw-TCP VLESS listener (type=tcp, no WS/HTTP framing).
    # This needs its own externally-reachable TCP port. On Railway, expose
    # it the same way MTProxy's port is exposed: Settings -> Networking ->
    # "TCP Proxy" on this service, pointed at RAW_TCP_PORT. Render's web
    # service plan does NOT support extra raw TCP ports at all — only the
    # single HTTP $PORT — so this stays disabled by default there.
    raw_tcp_enabled: bool = os.environ.get("RAW_TCP_ENABLED", "false").lower() not in ("0", "false", "no", "off")
    raw_tcp_port: int = int(os.environ.get("RAW_TCP_PORT", 8080))
    raw_tcp_public_host: str = os.environ.get("RAW_TCP_PUBLIC_HOST", "")
    raw_tcp_public_port: str = os.environ.get("RAW_TCP_PUBLIC_PORT", "")

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
