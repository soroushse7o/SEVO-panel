"""
MTProto (Telegram) proxy service.

Runs `mtg` as a child process inside the same container as the panel and
exposes the connection details the panel needs to build a tg://proxy link.

Design notes
------------
* The secret is generated once, on first start, and persisted in the settings
  table so it survives restarts and redeploys.
* mtg binds to a configurable *internal* port (MTPROXY_BIND_PORT, 443 by
  default) inside the container. That port is not reachable from the internet
  on its own.
* The *public* endpoint (host + port that clients use) is what appears in the
  tg://proxy link. It is resolved with this priority:
    1. values set manually from the panel (stored in the DB),
    2. RAILWAY_TCP_PROXY_DOMAIN / RAILWAY_TCP_PROXY_PORT injected by Railway,
    3. a fallback that is flagged as unconfirmed so the UI tells the operator
       to wire up a TCP proxy.
* Railway (and similar platforms) put a TCP proxy in front of the internal
  port and inject the public address into the environment. The container's own
  IP is private and must never appear in the link.
"""

import asyncio
import logging
import os
import secrets as pysecrets
import shutil
from typing import Optional

from app import state
from app.config import settings
from app.database import execute as db_exec, fetchone

logger = logging.getLogger("panel.mtproxy")

SECRET_KEY_NAME = "mtproxy_secret"
BIND_PORT_KEY = "mtproxy_bind_port"
PUBLIC_HOST_KEY = "mtproxy_public_host"
PUBLIC_PORT_KEY = "mtproxy_public_port"

# DB setting keys (above) are prefixed with "mtproxy_"; the in-memory
# state.mtproxy_config dict uses short keys. This maps one to the other so
# runtime updates (_set_str) actually land where the getters read from.
_DB_KEY_TO_STATE_KEY = {
    BIND_PORT_KEY: "bind_port",
    PUBLIC_HOST_KEY: "public_host",
    PUBLIC_PORT_KEY: "public_port",
}

# Process handle and last known status.
_process: Optional[asyncio.subprocess.Process] = None
_task: Optional[asyncio.Task] = None
_status = {
    "enabled": False,
    "running": False,
    "binary": None,
    "error": "",
    "restarts": 0,
}


def _hex_domain(domain: str) -> str:
    return domain.encode("utf-8").hex()


def generate_secret(fake_domain: str = "") -> str:
    """Build an 'ee' FakeTLS secret: ee + 16 random bytes + hex(domain)."""
    domain = (fake_domain or settings.mtproxy_fake_domain or "www.cloudflare.com").strip()
    return "ee" + pysecrets.token_hex(16) + _hex_domain(domain)


def secret_domain(secret: str) -> str:
    """Recover the fronting domain from an 'ee' secret, best effort."""
    if not secret.startswith("ee") or len(secret) <= 34:
        return ""
    try:
        return bytes.fromhex(secret[34:]).decode("utf-8", "replace")
    except ValueError:
        return ""


def find_binary() -> str:
    """Locate the mtg binary, honouring MTPROXY_BIN."""
    if settings.mtproxy_bin and os.path.isfile(settings.mtproxy_bin):
        return settings.mtproxy_bin
    found = shutil.which("mtg")
    if found:
        return found
    for candidate in ("/usr/local/bin/mtg", "/mtg"):
        if os.path.isfile(candidate):
            return candidate
    return ""


# --- persisted settings (loaded from DB, mutable at runtime) ---

async def _get_str(key: str, default: str = "") -> str:
    row = await fetchone(
        "SELECT value FROM settings WHERE key = ?",
        "SELECT value FROM settings WHERE key = $1",
        (key,),
    )
    return row["value"] if row and row["value"] else default


async def _set_str(key: str, value: str) -> None:
    state_key = _DB_KEY_TO_STATE_KEY.get(key, key)
    state.mtproxy_config[state_key] = value
    await db_exec(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        "INSERT INTO settings (key, value) VALUES ($1, $2) "
        "ON CONFLICT (key) DO UPDATE SET value = $2",
        (key, value),
    )


async def load_config() -> None:
    """Load persisted MTProxy settings from the DB into memory."""
    state.mtproxy_config["bind_port"] = await _get_str(BIND_PORT_KEY, str(settings.mtproxy_port))
    state.mtproxy_config["public_host"] = await _get_str(PUBLIC_HOST_KEY, settings.mtproxy_public_host)
    state.mtproxy_config["public_port"] = await _get_str(PUBLIC_PORT_KEY, str(settings.mtproxy_public_port))


def bind_port() -> int:
    try:
        return int(state.mtproxy_config.get("bind_port") or settings.mtproxy_port)
    except (TypeError, ValueError):
        return settings.mtproxy_port


def manual_endpoint() -> tuple[str, str]:
    """Return (host, port) if the operator set them manually, else ('', '')."""
    host = (state.mtproxy_config.get("public_host") or "").strip()
    port = (state.mtproxy_config.get("public_port") or "").strip()
    if host and port.isdigit():
        return host, port
    return "", ""


async def load_or_create_secret() -> str:
    """Read the persisted secret, generating and storing one on first run."""
    if settings.mtproxy_secret:
        state.mtproxy_secret = settings.mtproxy_secret.strip()
        return state.mtproxy_secret

    row = await fetchone(
        "SELECT value FROM settings WHERE key = ?",
        "SELECT value FROM settings WHERE key = $1",
        (SECRET_KEY_NAME,),
    )
    if row and row["value"]:
        state.mtproxy_secret = row["value"]
        return state.mtproxy_secret

    secret = generate_secret()
    await save_secret(secret)
    logger.info("Generated a new MTProxy secret")
    return secret


async def save_secret(secret: str) -> None:
    state.mtproxy_secret = secret
    await db_exec(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        "INSERT INTO settings (key, value) VALUES ($1, $2) "
        "ON CONFLICT (key) DO UPDATE SET value = $2",
        (SECRET_KEY_NAME, secret),
    )


def public_endpoint() -> tuple[str, int, bool]:
    """
    Return (host, port, confirmed) for the tg://proxy link.

    Priority: manual panel setting > Railway TCP proxy env > unconfirmed fallback.
    `confirmed` is False when the operator still has to expose a TCP proxy;
    the link then shows the internal address as a best guess and the UI warns.
    """
    host, port = manual_endpoint()
    if host:
        return host, int(port), True

    host = os.environ.get("RAILWAY_TCP_PROXY_DOMAIN", "").strip()
    port_raw = os.environ.get("RAILWAY_TCP_PROXY_PORT", "").strip()
    if host and port_raw.isdigit():
        return host, int(port_raw), True

    from app.vless import get_domain
    return get_domain(), bind_port(), False


def build_link(secret: str = "") -> str:
    secret = secret or state.mtproxy_secret
    if not secret:
        return ""
    host, port, _ = public_endpoint()
    return f"tg://proxy?server={host}&port={port}&secret={secret}"


def build_http_link(secret: str = "") -> str:
    secret = secret or state.mtproxy_secret
    if not secret:
        return ""
    host, port, _ = public_endpoint()
    return f"https://t.me/proxy?server={host}&port={port}&secret={secret}"


def get_status() -> dict:
    host, port, confirmed = public_endpoint()
    secret = state.mtproxy_secret
    return {
        **_status,
        "enabled": settings.mtproxy_enabled,
        # Prefer a real connectivity probe over just "is our child process
        # alive". On Railway mtg may be supervised outside this process, so
        # the panel must report Running whenever the proxy port actually
        # answers -- otherwise it wrongly says "Stopped" while traffic works.
        "running": _status.get("port_listening", False) or (
            _process is not None and _process.returncode is None
        ),
        "bind_port": bind_port(),
        "public_host": host,
        "public_port": port,
        "endpoint_confirmed": confirmed,
        "manual_host": state.mtproxy_config.get("public_host", ""),
        "manual_port": _mtproto_config_get("public_port"),
        "fake_domain": secret_domain(secret),
        "secret": secret,
        "tg_link": build_link(secret),
        "https_link": build_http_link(secret),
    }


def _mtproto_config_get(key: str) -> str:
    return str(state.mtproxy_config.get(key, ""))


async def _pump(stream, level: int) -> None:
    """Forward mtg output into the panel logger."""
    while True:
        line = await stream.readline()
        if not line:
            break
        text = line.decode("utf-8", "replace").rstrip()
        if text:
            logger.log(level, "[mtg] %s", text)


async def _supervise() -> None:
    """Keep mtg alive, restarting it with a capped backoff."""
    global _process
    backoff = 2
    while True:
        binary = find_binary()
        if not binary:
            _status["error"] = "mtg binary not found in the image"
            logger.warning("MTProxy enabled but the mtg binary was not found; disabling")
            return
        _status["binary"] = binary

        bind = f"0.0.0.0:{bind_port()}"
        cmd = [
            binary, "simple-run",
            "-c", str(settings.mtproxy_concurrency),
            "-t", "30s",
            bind, state.mtproxy_secret,
        ]
        logger.info("Starting mtg on %s", bind)
        try:
            _process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except Exception as exc:  # noqa: BLE001
            _status["error"] = f"failed to start: {exc}"
            logger.error("Could not start mtg: %s", exc)
            return

        _status["error"] = ""
        await asyncio.gather(
            _pump(_process.stdout, logging.INFO),
            _pump(_process.stderr, logging.WARNING),
            _process.wait(),
        )

        code = _process.returncode
        _process = None
        _status["restarts"] += 1
        _status["error"] = f"mtg exited with code {code}"
        logger.warning("mtg exited with code %s, restarting in %ss", code, backoff)
        state.log_event("MTProxy", f"mtg exited with code {code}, restarting")
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 60)


async def _health_check() -> None:
    """Periodically probe the proxy bind port so the panel reports a truthful
    running/stopped status even when mtg is supervised outside this process
    (e.g. Railway's own process manager)."""
    while True:
        try:
            host = "127.0.0.1"
            port = bind_port()
            if not settings.mtproxy_enabled:
                _status["port_listening"] = False
            else:
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(host, port), timeout=2.0
                    )
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except Exception:
                        pass
                    _status["port_listening"] = True
                    _status["error"] = ""
                except (OSError, asyncio.TimeoutError, asyncio.CancelledError):
                    _status["port_listening"] = False
        except Exception:
            _status["port_listening"] = False
        await asyncio.sleep(10)


async def start() -> None:
    """Start the MTProxy supervisor if it is enabled."""
    global _task
    if not settings.mtproxy_enabled:
        logger.info("MTProxy is disabled")
        return
    await load_config()
    await load_or_create_secret()
    # Always run the port health-check loop so the panel shows a truthful
    # status regardless of whether mtg runs inside this process or is
    # supervised externally (Railway, sidecar, etc.).
    _health_task = asyncio.create_task(_health_check())
    if find_binary():
        _task = asyncio.create_task(_supervise())
        state.log_event("MTProxy", "MTProto proxy starting")
    else:
        _status["error"] = "mtg binary not found in the image"
        logger.warning("MTProxy is enabled but mtg is not installed in this image")


async def stop() -> None:
    """Terminate mtg and its supervisor."""
    global _task, _process
    if _task:
        _task.cancel()
        try:
            await _task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        _task = None
    if _process and _process.returncode is None:
        _process.terminate()
        try:
            await asyncio.wait_for(_process.wait(), timeout=5)
        except asyncio.TimeoutError:
            _process.kill()
    _process = None


async def restart() -> None:
    await stop()
    # reload config in case it changed while stopped
    await load_config()
    await start()


async def set_endpoint(bind_port: Optional[int], public_host: str, public_port: Optional[int]) -> dict:
    """
    Persist operator-configured bind port and public endpoint, then restart
    mtg so the new bind port takes effect.
    """
    if bind_port is not None:
        if not (1 <= int(bind_port) <= 65535):
            raise ValueError("bind port must be between 1 and 65535")
        await _set_str(BIND_PORT_KEY, str(int(bind_port)))

    host = (public_host or "").strip()
    if host:
        if " " in host or len(host) > 253:
            raise ValueError("invalid public host")
        await _set_str(PUBLIC_HOST_KEY, host)
    else:
        # clear manual host so Railway/env resolution takes over again
        await _set_str(PUBLIC_HOST_KEY, "")

    if public_port is not None and str(public_port).strip():
        if not (1 <= int(public_port) <= 65535):
            raise ValueError("public port must be between 1 and 65535")
        await _set_str(PUBLIC_PORT_KEY, str(int(public_port)))
    else:
        await _set_str(PUBLIC_PORT_KEY, "")

    if settings.mtproxy_enabled and find_binary():
        await restart()

    state.log_event("MTProxy", "Endpoint configuration updated")
    return get_status()
