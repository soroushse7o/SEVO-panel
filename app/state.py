"""
In-memory state — replaces scattered global variables with a single,
organized state object. All mutable state lives here, all access is
through documented attributes.
"""
import asyncio
import time
import os
from collections import defaultdict, deque
from typing import Any

# Persistent boot timestamp so App Uptime survives process restarts
# (Railway redeploys / /api/panel/restart would otherwise reset it).
_BOOT_FILE_CANDIDATES = [
    os.environ.get("DATA_DIR", ""),
    os.environ.get("DB_PATH", "").rsplit("/", 1)[0] if os.environ.get("DB_PATH", "").startswith("/") else "",
    ".",
]
_BOOT_FILE = None
for _cand in _BOOT_FILE_CANDIDATES:
    if _cand and os.path.isdir(_cand):
        _BOOT_FILE = os.path.join(_cand, ".boot_time")
        break
if _BOOT_FILE is None:
    _BOOT_FILE = ".boot_time"

try:
    if os.path.exists(_BOOT_FILE):
        with open(_BOOT_FILE, "r") as _f:
            _boot_ts = float(_f.read().strip())
    else:
        _boot_ts = time.time()
        with open(_BOOT_FILE, "w") as _f:
            _f.write(str(_boot_ts))
except Exception:
    _boot_ts = time.time()


class AppState:
    """Centralized in-memory state for the panel."""

    def __init__(self, max_log_entries: int = 2000):
        # Links (inbound configs)
        self.links: dict[str, dict] = {}
        self.links_lock = asyncio.Lock()

        # Custom clean-IP addresses
        self.addresses: list[str] = []
        self.addresses_lock = asyncio.Lock()

        # Active WebSocket connections
        self.connections: dict[str, dict] = {}
        self.connections_lock = asyncio.Lock()
        self.connection_sockets: dict[str, Any] = {}
        self.link_ip_map: dict[str, set] = defaultdict(set)

        # Traffic stats
        self.stats = {
            "total_bytes": 0,
            "total_requests": 0,
            "total_errors": 0,
            "start_time": _boot_ts,
            "upload_bytes": 0,
            "download_bytes": 0,
        }

        # Traffic buffer (flushed to DB periodically)
        self.traffic_buffer_lock = asyncio.Lock()
        self.traffic_buffer: dict[str, defaultdict] = {
            "hourly": defaultdict(int),
            "daily": defaultdict(int),
        }

        # Error/event logs (in-memory ring buffer)
        self.error_logs: deque = deque(maxlen=max_log_entries)

        # Link generation cache
        self.link_cache: dict[str, dict] = {}

        # Runtime settings (loaded from DB, mutable)
        self.timezone_offset: float = 0.0
        self.keep_alive_enabled: bool = True
        self.keep_alive_mode: str = "simple"
        self.keep_alive_interval: int = 300
        self.logging_enabled: bool = True

        # Secret admin URL prefix (resolved at startup, see app/secret_path.py)
        self.secret_path: str = ""
        self.process_start: float = time.time()

        # JWT secret (loaded from DB)
        self.secret_key: str = ""
        self.admin_username: str = ""
        self.admin_password_hash: str = ""

        # MTProto proxy
        self.mtproxy_secret: str = ""
        self.mtproxy_config: dict[str, str] = {
            "bind_port": "",
            "public_host": "",
            "public_port": "",
        }

    def log_event(self, etype: str, message: str, ip: str = "", ua: str = ""):
        """Append an event to the in-memory log buffer."""
        from datetime import datetime, timezone
        self.error_logs.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "type": etype,
            "error": message or "(no detail)",
            "ip": ip,
            "ua": ua,
        })


# Global singleton
state = AppState()
