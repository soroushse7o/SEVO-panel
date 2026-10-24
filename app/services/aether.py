"""
Aether tunnel manager.

Python port of the process-management half of ASiRi-web-panel
(web/lib/{aether,watchdog,probe,install,config-store}.ts).

What it does
------------
* Runs the Aether binary (Cloudflare-based tunnel client) as a child process.
  Aether opens a local, unauthenticated SOCKS5 proxy on 127.0.0.1:<port>
  (default 1819).
* Parses its log to keep a live phase (starting / scanning / connecting /
  connected / reconnecting / error), gateway and exit info.
* Watchdog: periodic health probe through the SOCKS5 port, exponential
  backoff restarts, fallback to the last known-good preset.
* Best-config sweep: runs every selected protocol x scan-mode combination on this
  server, measures real HTTPS latency through each tunnel and ranks them; the winner
  can be saved (as the saved options and as last known-good) and connected.
* Installer (API only, no UI tab): downloads the pinned release, verifies its sha256.
* Tells app/services/upstream.py when the tunnel is usable, so panel users'
  traffic can leave through Aether instead of the host's own IP.

Not ported: ASiRi's own SOCKS/HTTP/SS gateway and Trojan inbound, Railway TCP
relay. HTTP/3 transport and the HTTP proxy (port+1) listener were removed; the
panel's "Best Config" tab (the sweep below) replaces the old Install tab. The
legacy /api/endpoints/* API (app/services/endpoint_finder.py) is untouched.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import platform
import re
import ssl
import tarfile
import tempfile
import time
from collections import deque
from typing import Any, Optional

from app import state as app_state
from app.config import settings
from app.services import upstream

logger = logging.getLogger("SE7OSNA.aether")

PROTOCOLS = ("masque", "wg", "gool", "mim")
# HTTP/3 was removed on purpose: the tunnel always uses HTTP/2.
TRANSPORTS = ("h2",)
SCAN_MODES = ("turbo", "balanced", "thorough", "verified", "ironclad")
IP_MODES = ("4", "6", "dual")
NOIZE_PROFILES = ("default", "off", "light", "firewall", "balanced", "gfw", "aggressive")

DEFAULT_OPTIONS: dict[str, Any] = {
    "protocol": "masque",
    "transport": "h2",
    "scan": "turbo",
    "ip": "4",
    "noize": "default",
    "port": 1819,
    "quick_reconnect": True,
}

MAX_LOGS = 500
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_RE_EDGE = re.compile(r"using cloudflare edge (\S+)")
_RE_GATEWAY = re.compile(r"selected \S+ gateway (\S+)")
_RE_EXIT = re.compile(
    r"exit: ([0-9a-fA-F.:]+), (\w+) via (\w+), (\d+)ms to cloudflare(?:, warp (\w+))?")
_RE_ERROR = re.compile(r"\bERROR\b")
_RE_WARN = re.compile(r"\bWARN\b")


class AetherError(Exception):
    """User-facing error (shown in the panel as a toast)."""


# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------

def _one_of(allowed: tuple, value: Any, default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


def parse_options(raw: Any) -> dict[str, Any]:
    """Validate/normalise user input; unknown or invalid values fall back to defaults."""
    o = raw if isinstance(raw, dict) else {}
    try:
        port = int(o.get("port"))
    except (TypeError, ValueError):
        port = 0
    d = DEFAULT_OPTIONS
    return {
        "protocol": _one_of(PROTOCOLS, o.get("protocol"), d["protocol"]),
        "transport": _one_of(TRANSPORTS, o.get("transport"), d["transport"]),
        "scan": _one_of(SCAN_MODES, o.get("scan"), d["scan"]),
        "ip": _one_of(IP_MODES, str(o.get("ip", "")), d["ip"]),
        "noize": _one_of(NOIZE_PROFILES, o.get("noize"), d["noize"]),
        "port": port if 1024 <= port <= 65534 else d["port"],
        "quick_reconnect": o.get("quick_reconnect") is not False,
    }


def build_args(o: dict[str, Any]) -> list[str]:
    args = ["--protocol", o["protocol"], "--scan", o["scan"]]
    args.append("-4" if o["ip"] == "4" else "-6" if o["ip"] == "6" else "--dual")
    if o["protocol"] != "wg":
        args.append("--h2")
    if o["noize"] != "default":
        args += ["--noize", o["noize"]]
    args += ["--bind", f"127.0.0.1:{o['port']}"]
    args.append("--quick-reconnect" if o["quick_reconnect"] else "--no-quick-reconnect")
    return args


def same_options(a: Optional[dict], b: Optional[dict]) -> bool:
    if not a or not b:
        return False
    return parse_options(a) == parse_options(b)


# ---------------------------------------------------------------------------
# Runtime state
# ---------------------------------------------------------------------------

class _State:
    def __init__(self) -> None:
        self.proc: Optional[asyncio.subprocess.Process] = None
        self.phase = "stopped"
        self.logs: deque = deque(maxlen=MAX_LOGS)
        self.seq = 0
        self.started_at: Optional[float] = None
        self.connected_at: Optional[float] = None
        self.options: Optional[dict] = None
        self.gateway: Optional[str] = None
        self.exit: Optional[dict] = None
        self.last_error: Optional[str] = None
        self.stop_requested = False
        self.wanted = False          # the operator wants the tunnel up; watchdog keeps it alive
        self.maintenance = False     # True while a best-config sweep owns the tunnel (watchdog + Start/Restart stand down)
        self.auto_start = False
        self.cfg: dict[str, Any] = {"options": None, "last_good": None}
        self.tasks: set = set()
        self.watchdog_task: Optional[asyncio.Task] = None


S = _State()


class _Watchdog:
    def __init__(self) -> None:
        self.reset_all()

    def reset_all(self) -> None:
        self.consecutive_fails = 0
        self.restarts = 0
        self.failed_starts = 0
        self.backoff_idx = 0
        self.next_restart_at: Optional[float] = None
        self.next_reason: Optional[str] = None
        self.last_check_at: Optional[float] = None
        self.last_check_ok: Optional[bool] = None
        self.last_reason: Optional[str] = None
        self.stuck_since: Optional[float] = None
        self.connected_since: Optional[float] = None
        self.down_notified = False
        self.good_saved = False

    def reset_idle(self) -> None:
        self.consecutive_fails = 0
        self.failed_starts = 0
        self.backoff_idx = 0
        self.next_restart_at = None
        self.next_reason = None
        self.stuck_since = None
        self.connected_since = None
        self.down_notified = False
        self.good_saved = False


W = _Watchdog()


def _now() -> float:
    return time.monotonic()


def is_connected() -> bool:
    return S.proc is not None and S.phase == "connected"


# ---------------------------------------------------------------------------
# Paths / binary
# ---------------------------------------------------------------------------

def data_dir() -> str:
    d = getattr(settings, "aether_dir", "") or os.environ.get("AETHER_DIR", "")
    if not d:
        base = os.environ.get("DATA_DIR", "")
        db_path = getattr(settings, "db_path", "") or ""
        if not base and db_path.startswith("/"):
            base = os.path.dirname(db_path)
        if base and os.path.isdir(base):
            d = os.path.join(base, "aether")
        else:
            d = os.path.join(tempfile.gettempdir(), ".aether")
    os.makedirs(d, exist_ok=True)
    return d


def find_binary() -> Optional[str]:
    cands = [
        getattr(settings, "aether_bin", "") or "",
        os.environ.get("AETHER_BIN", ""),
        os.path.join(data_dir(), "aether"),
        "/opt/aether/aether",
        "/usr/local/bin/aether",
    ]
    for c in cands:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


# ---------------------------------------------------------------------------
# Logging + log parsing
# ---------------------------------------------------------------------------

def log_line(text: str, level: str = "info") -> None:
    S.seq += 1
    S.logs.append({"id": S.seq, "text": text, "level": level, "ts": int(time.time() * 1000)})


def parse_line(raw: str) -> None:
    """Feed one line of Aether output; updates phase / gateway / exit info."""
    text = _ANSI.sub("", raw).rstrip()
    if not text:
        return
    level = "error" if _RE_ERROR.search(text) else "warn" if _RE_WARN.search(text) else "info"
    log_line(text, level)

    if "scan mode=" in text:
        S.phase = "scanning"

    m = _RE_EDGE.search(text) or _RE_GATEWAY.search(text)
    if m:
        S.gateway = m.group(1)
        if S.phase != "connected":
            S.phase = "connecting"

    if "socks5 server listening on" in text:
        S.phase = "connected"
        S.connected_at = _now()
        S.last_error = None
        app_state.log_event("Info", f"Aether tunnel connected (gateway {S.gateway or '?'})")

    m = _RE_EXIT.search(text)
    if m:
        S.exit = {"ip": m.group(1), "country": m.group(2), "colo": m.group(3),
                  "latency_ms": int(m.group(4)), "warp": m.group(5)}

    if "tunnel ended" in text or "reconnecting" in text:
        S.phase = "reconnecting"
        S.connected_at = None

    if level == "error":
        S.last_error = re.sub(r"^\[[^\]]*\]\s*", "", text)


async def _pump(stream: Optional[asyncio.StreamReader]) -> None:
    if stream is None:
        return
    while True:
        try:
            line = await stream.readline()
        except (ValueError, asyncio.LimitOverrunError):
            continue  # over-long line: skip it
        if not line:
            break
        parse_line(line.decode("utf-8", errors="replace"))


def _spawn(coro) -> None:
    t = asyncio.create_task(coro)
    S.tasks.add(t)
    t.add_done_callback(S.tasks.discard)


def _on_exit(proc: asyncio.subprocess.Process) -> None:
    """Idempotent exit bookkeeping (called by the waiter task and by _terminate)."""
    if S.proc is not proc:
        return
    S.proc = None
    S.connected_at = None
    if S.stop_requested:
        S.phase = "stopped"
        log_line("[*] aether stopped")
    else:
        S.phase = "error"
        S.last_error = S.last_error or f"Aether exited with code {proc.returncode}"
        log_line(f"[-] aether exited (code={proc.returncode})", "error")
        app_state.log_event("Error", f"Aether exited unexpectedly (code {proc.returncode})")


async def _wait(proc: asyncio.subprocess.Process) -> None:
    await proc.wait()
    _on_exit(proc)


async def _terminate() -> None:
    proc = S.proc
    if proc is None:
        return
    S.stop_requested = True
    try:
        proc.terminate()
    except ProcessLookupError:
        pass
    try:
        await asyncio.wait_for(proc.wait(), timeout=3.0)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        await proc.wait()
    _on_exit(proc)


# ---------------------------------------------------------------------------
# Persistence (settings table -> survives restarts when /data is a volume)
# ---------------------------------------------------------------------------

async def _load_cfg() -> dict[str, Any]:
    from app.database import get_setting
    try:
        d = json.loads(await get_setting("aether_config", "") or "{}")
    except ValueError:
        d = {}
    lg = d.get("last_good")
    return {
        "options": parse_options(d["options"]) if d.get("options") else None,
        "last_good": ({"options": parse_options(lg.get("options")), "at": lg.get("at", 0)}
                      if isinstance(lg, dict) and lg.get("options") else None),
    }


async def _save_cfg(**patch: Any) -> None:
    from app.database import set_setting
    S.cfg.update(patch)
    try:
        await set_setting("aether_config", json.dumps(S.cfg))
    except Exception as e:  # persistence is best-effort
        logger.warning("could not persist aether config: %s", e)


# ---------------------------------------------------------------------------
# Start / stop
# ---------------------------------------------------------------------------

_BUSY_MSG = "A best-config test is running. Cancel it (or press Stop) first."


async def start(options: Optional[dict] = None, persist: bool = True) -> None:
    if S.maintenance:
        raise AetherError(_BUSY_MSG)
    await _start_impl(options, persist)


async def _start_impl(options: Optional[dict] = None, persist: bool = True) -> None:
    """Spawn Aether. Internal callers (watchdog, sweep) use this directly."""
    if S.proc is not None:
        raise AetherError("Aether is already running. Stop it first.")
    binary = find_binary()
    if not binary:
        raise AetherError("Aether binary not found. Install it first.")
    opts = parse_options(options if options is not None else (S.cfg.get("options") or {}))
    args = build_args(opts)

    S.wanted = True
    if persist:
        await _save_cfg(options=opts)

    S.logs.clear()
    S.phase = "starting"
    S.started_at = _now()
    S.connected_at = None
    S.options = opts
    S.gateway = None
    S.exit = None
    S.last_error = None
    S.stop_requested = False
    log_line(f"$ aether {' '.join(args)}")

    try:
        proc = await asyncio.create_subprocess_exec(
            binary, *args,
            cwd=data_dir(),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "NO_COLOR": "1", "TERM": "dumb"},
        )
    except OSError as e:
        S.phase = "error"
        S.last_error = str(e)
        log_line(f"failed to start: {e}", "error")
        raise AetherError(f"failed to start Aether: {e}") from e

    S.proc = proc
    upstream.configure(socks_port=opts["port"])
    _spawn(_pump(proc.stdout))
    _spawn(_pump(proc.stderr))
    _spawn(_wait(proc))
    app_state.log_event("Info", f"Aether starting ({opts['protocol']}/{opts['transport']}, scan={opts['scan']})")


async def stop() -> None:
    if S.maintenance:
        # Stop during a best-config test == cancel it; the tunnel returns to its previous state.
        await cancel_sweep()
        return
    S.wanted = False
    await _terminate()
    S.phase = "stopped"


async def restart(options: Optional[dict] = None) -> None:
    if S.maintenance:
        raise AetherError(_BUSY_MSG)
    opts = options if options is not None else S.options
    await _terminate()
    await _start_impl(opts, persist=options is not None)


# ---------------------------------------------------------------------------
# Settings: outbound mode + auto start
# ---------------------------------------------------------------------------

def _env_bool(name: str) -> Optional[bool]:
    v = os.environ.get(name)
    if v is None or not v.strip():
        return None
    return v.strip().lower() in ("1", "true", "yes", "on")


async def set_outbound_mode(mode: str) -> None:
    from app.database import set_setting
    if mode not in upstream.MODES:
        raise AetherError(f"outbound mode must be one of: {', '.join(upstream.MODES)}")
    upstream.configure(mode=mode)
    await set_setting("aether_outbound", mode)
    app_state.log_event("Info", f"Outbound mode set to '{mode}'")


async def set_auto_start(value: bool) -> None:
    from app.database import set_setting
    S.auto_start = bool(value)
    await set_setting("aether_auto_start", "1" if value else "0")


# ---------------------------------------------------------------------------
# Health probe
# ---------------------------------------------------------------------------

async def probe(port: int, timeout: float = 10.0) -> dict[str, Any]:
    """HTTPS GET to Cloudflare's trace endpoint through the local SOCKS5 port."""
    t0 = time.monotonic()
    host = "www.cloudflare.com"
    try:
        reader, writer = await upstream.socks5_connect(host, 443, upstream.SOCKS_HOST, port, timeout=timeout)
        try:
            await asyncio.wait_for(
                writer.start_tls(ssl.create_default_context(), server_hostname=host), timeout=timeout)
            writer.write(f"GET /cdn-cgi/trace HTTP/1.1\r\nHost: {host}\r\n"
                         "Connection: close\r\nUser-Agent: se7o-sna-watchdog\r\n\r\n".encode())
            await writer.drain()
            line = await asyncio.wait_for(reader.readline(), timeout=timeout)
            parts = line.split()
            ok = len(parts) >= 2 and parts[0].startswith(b"HTTP/1.") and parts[1] == b"200"
            err = None if ok else f"unexpected response: {line[:60]!r}"
        finally:
            writer.close()
    except Exception as e:
        ok, err = False, (str(e) or type(e).__name__)[:200]
    return {"ok": ok, "ms": int((time.monotonic() - t0) * 1000), "error": err}


# ---------------------------------------------------------------------------
# Watchdog
# ---------------------------------------------------------------------------

def _num(name: str, fallback: float) -> float:
    try:
        n = float(os.environ.get(name, ""))
        return n if n > 0 else fallback
    except ValueError:
        return fallback


def _tuning() -> dict[str, float]:
    return {
        "tick": _num("WATCHDOG_TICK_SEC", 5),
        "check": _num("WATCHDOG_INTERVAL_SEC", 30),
        "max_failures": int(_num("WATCHDOG_MAX_FAILURES", 3)),
        "stuck": _num("WATCHDOG_STUCK_SEC", 300),
        "stable": _num("WATCHDOG_STABLE_SEC", 60),
        "fallback_after": int(_num("WATCHDOG_FALLBACK_AFTER", 3)),
        "backoff_base": _num("WATCHDOG_BACKOFF_BASE_SEC", 2),
        "backoff_max": _num("WATCHDOG_BACKOFF_MAX_SEC", 300),
        "probe_timeout": _num("WATCHDOG_PROBE_TIMEOUT_SEC", 10),
    }


def backoff_sec(attempt: int, base: float = 2.0, cap: float = 300.0) -> float:
    """Exponential backoff, zero-indexed: 0 -> base, 1 -> 2*base, ... capped."""
    return min(cap, base * 2 ** min(max(0, int(attempt)), 30))


async def _notify(event: str, text: str) -> None:
    app_state.log_event("Warning" if event == "tunnel_down" else "Info", text)
    try:
        from app.services.telegram import notify_event
        await notify_event(event, text, "aether")
    except Exception as e:  # never let a notification failure break the watchdog
        logger.debug("notify failed: %s", e)


async def _report_down(reason: str, delay: float) -> None:
    W.last_reason = reason
    log_line(f"[watchdog] {reason}; restarting in {round(delay)}s (attempt {W.backoff_idx + 1})", "warn")
    if not W.down_notified:
        W.down_notified = True
        await _notify("tunnel_down", f"Aether tunnel down: {reason}. Restarting in {round(delay)}s")


async def _schedule_restart(reason: str) -> None:
    t = _tuning()
    delay = backoff_sec(W.backoff_idx, t["backoff_base"], t["backoff_max"])
    W.next_restart_at = _now() + delay
    W.next_reason = reason
    await _report_down(reason, delay)
    W.backoff_idx += 1


async def _restart_now(options: dict) -> None:
    W.restarts += 1
    W.next_restart_at = None
    W.stuck_since = None
    W.connected_since = None
    W.consecutive_fails = 0
    await _terminate()
    try:
        await _start_impl(options, persist=False)
    except AetherError as e:
        log_line(f"[watchdog] restart failed: {e}", "error")
        await _schedule_restart(f"restart failed: {e}")


async def _maybe_fallback(current: Optional[dict]) -> Optional[dict]:
    t = _tuning()
    if W.failed_starts < t["fallback_after"]:
        return None
    good = S.cfg.get("last_good")
    if not good or same_options(good["options"], current):
        return None
    log_line("[watchdog] repeated failures; falling back to the last known-good preset", "warn")
    await _notify("tunnel_down", f"{W.failed_starts} failed starts in a row; falling back to the last known-good preset")
    await _save_cfg(options=good["options"])
    W.failed_starts = 0
    W.backoff_idx = 0
    return good["options"]


async def _tick() -> None:
    t = _tuning()
    if not S.wanted or S.maintenance:
        if not S.wanted:
            W.reset_idle()
        return
    now = _now()

    if S.proc is None:
        if W.next_restart_at is None:
            if W.connected_since is None or now - W.connected_since < t["stable"]:
                W.failed_starts += 1
            W.connected_since = None
            await _schedule_restart("Aether process exited")
        if W.next_restart_at is not None and now >= W.next_restart_at and S.options:
            fb = await _maybe_fallback(S.options)
            await _restart_now(fb or S.options)
        return

    if S.phase == "connected":
        W.stuck_since = None
        if W.connected_since is None:
            W.connected_since = now
        if W.down_notified and now - W.connected_since > 10:
            W.down_notified = False

        if now - W.connected_since >= t["stable"]:
            W.failed_starts = 0
            W.backoff_idx = 0
            if not W.good_saved and S.options:
                W.good_saved = True
                await _save_cfg(last_good={"options": S.options, "at": int(time.time() * 1000)})

        if S.options and (W.last_check_at is None or now - W.last_check_at >= t["check"]):
            W.last_check_at = now
            res = await probe(S.options["port"], t["probe_timeout"])
            W.last_check_ok = res["ok"]
            if res["ok"]:
                W.consecutive_fails = 0
            else:
                W.consecutive_fails += 1
                log_line(f"[watchdog] health check failed ({W.consecutive_fails}/{t['max_failures']}): "
                         f"{res['error'] or 'unknown'}", "warn")
                if W.consecutive_fails >= t["max_failures"]:
                    W.failed_starts += 1
                    delay = backoff_sec(W.backoff_idx, t["backoff_base"], t["backoff_max"])
                    await _report_down(f"{W.consecutive_fails} consecutive health checks failed", delay)
                    W.backoff_idx += 1
                    await _terminate()
                    W.next_restart_at = _now() + delay
                    W.next_reason = "health checks failed"
        return

    # Alive but not connected (scanning / connecting / reconnecting): Aether handles short blips itself.
    W.connected_since = None
    if W.stuck_since is None:
        W.stuck_since = now
    if now - W.stuck_since > t["stuck"]:
        W.failed_starts += 1
        W.stuck_since = None
        delay = backoff_sec(W.backoff_idx, t["backoff_base"], t["backoff_max"])
        await _report_down(f'stuck in "{S.phase}" for over {round(t["stuck"])}s', delay)
        W.backoff_idx += 1
        await _terminate()
        W.next_restart_at = _now() + delay
        W.next_reason = "stuck"


async def _watchdog_loop() -> None:
    while True:
        await asyncio.sleep(_tuning()["tick"])
        try:
            await _tick()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log_line(f"[watchdog] {e}", "error")


# ---------------------------------------------------------------------------
# Best-config sweep
# ---------------------------------------------------------------------------

SWEEP_DEFAULT_SCANS = ("turbo", "balanced")
SWEEP_MAX_ATTEMPTS = 10
_SCAN_WAIT = {"turbo": 1.0, "balanced": 1.5, "thorough": 2.0, "verified": 2.0, "ironclad": 3.0}


class _Sweep:
    def __init__(self) -> None:
        self.status = "idle"      # idle | running | finishing | done | cancelled | error
        self.combos: list[tuple[str, str]] = []
        self.results: list[dict[str, Any]] = []
        self.done = 0
        self.current: Optional[dict] = None
        self.attempts = 3
        self.save = True
        self.winner: Optional[dict] = None
        self.winner_opts: Optional[dict] = None
        self.saved = False
        self.error: Optional[str] = None
        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None
        self.no_restore = False
        self.task: Optional[asyncio.Task] = None


SW = _Sweep()


def _rank_key(r: dict[str, Any]) -> tuple:
    # working configs first, then the most reliable, then the fastest
    return (not r["ok"], r["attempts"] - r["ok_count"], r["avg_ms"] if r["avg_ms"] is not None else 1e12)


def _pick(allowed: tuple, raw: Any) -> list[str]:
    if raw is None:
        return list(allowed)
    if isinstance(raw, str):
        raw = [raw]
    out: list[str] = []
    for v in raw if isinstance(raw, (list, tuple)) else []:
        if isinstance(v, str) and v in allowed and v not in out:
            out.append(v)
    return out


def sweep_status() -> dict[str, Any]:
    now = time.time()
    results = []
    for i, r in enumerate(sorted(SW.results, key=_rank_key), 1):
        results.append({**r, "rank": i})
    end = SW.finished_at or now
    return {
        "status": SW.status,
        "active": S.maintenance,
        "total": len(SW.combos),
        "done": SW.done,
        "current": SW.current,
        "attempts": SW.attempts,
        "save": SW.save,
        "results": results,
        "winner": SW.winner,
        "saved": SW.saved,
        "error": SW.error,
        "elapsed_sec": int(end - SW.started_at) if SW.started_at else None,
        "schema": {
            "protocols": PROTOCOLS, "scans": SCAN_MODES,
            "default_protocols": PROTOCOLS, "default_scans": SWEEP_DEFAULT_SCANS,
            "max_attempts": SWEEP_MAX_ATTEMPTS,
        },
    }


async def start_sweep(protocols: Any = None, scans: Any = None, attempts: Any = 3, save: bool = True) -> None:
    if S.maintenance:
        raise AetherError("A best-config test is already running.")
    if not find_binary():
        raise AetherError("Aether binary not found. Install it first.")
    protos = _pick(PROTOCOLS, protocols)
    scs = _pick(SCAN_MODES, scans if scans is not None else list(SWEEP_DEFAULT_SCANS))
    if not protos:
        raise AetherError("Select at least one protocol.")
    if not scs:
        raise AetherError("Select at least one scan mode.")
    try:
        n = int(attempts)
    except (TypeError, ValueError):
        n = 3
    n = max(1, min(n, SWEEP_MAX_ATTEMPTS))

    # protocol/scan vary; port, ip family, noize and quick-reconnect come from the current/saved options
    base = parse_options(S.options or S.cfg.get("options") or {})
    prev = {
        "running": S.proc is not None,
        "options": S.options or S.cfg.get("options"),
        "wanted": S.wanted,
    }

    S.maintenance = True        # set before any await: watchdog and Start/Restart step aside right now
    SW.status = "running"
    SW.combos = [(p, sc) for p in protos for sc in scs]
    SW.results = []
    SW.done = 0
    SW.current = None
    SW.attempts = n
    SW.save = bool(save)
    SW.winner = None
    SW.winner_opts = None
    SW.saved = False
    SW.error = None
    SW.started_at = time.time()
    SW.finished_at = None
    SW.no_restore = False

    app_state.log_event("Info", f"Best-config test started ({len(SW.combos)} combinations)")
    SW.task = asyncio.create_task(_run_sweep(base, list(SW.combos), n, bool(save), prev))
    S.tasks.add(SW.task)
    SW.task.add_done_callback(S.tasks.discard)


async def cancel_sweep() -> bool:
    t = SW.task
    if not S.maintenance or t is None or t.done():
        return False
    if SW.status == "running":      # never interrupt the restore phase half-way
        t.cancel()
    await asyncio.wait([t], timeout=90)
    return True


async def _measure_combo(opts: dict[str, Any], attempts: int) -> dict[str, Any]:
    res: dict[str, Any] = {
        "protocol": opts["protocol"], "scan": opts["scan"], "ok": False,
        "avg_ms": None, "min_ms": None, "max_ms": None,
        "ok_count": 0, "attempts": attempts, "connect_sec": None,
        "gateway": None, "exit": None, "error": None,
    }
    t0 = _now()
    await _terminate()
    try:
        await _start_impl(opts, persist=False)
    except AetherError as e:
        res["error"] = str(e)[:160]
        return res

    deadline = t0 + _num("SWEEP_CONNECT_TIMEOUT_SEC", 60) * _SCAN_WAIT.get(opts["scan"], 1.0)
    while S.phase != "connected":
        if S.proc is None:
            res["error"] = (S.last_error or "Aether exited before connecting")[:160]
            return res
        if _now() >= deadline:
            res["error"] = "connect timeout"
            await _terminate()
            return res
        await asyncio.sleep(0.5)

    res["connect_sec"] = round(_now() - t0, 1)
    res["gateway"] = S.gateway
    res["exit"] = S.exit
    probe_timeout = _tuning()["probe_timeout"]
    samples: list[int] = []
    last_err = None
    for i in range(attempts):
        p = await probe(opts["port"], probe_timeout)
        if p["ok"]:
            samples.append(p["ms"])
        else:
            last_err = p["error"]
        if i < attempts - 1:
            await asyncio.sleep(0.3)
    res["ok_count"] = len(samples)
    if samples:
        res.update(ok=True, avg_ms=int(sum(samples) / len(samples)), min_ms=min(samples), max_ms=max(samples))
    else:
        res["error"] = (last_err or "probe failed")[:160]
    await _terminate()
    return res


async def _run_sweep(base: dict, combos: list, attempts: int, save: bool, prev: dict) -> None:
    final = "done"
    try:
        for proto, scan in combos:
            SW.current = {"protocol": proto, "scan": scan}
            SW.results.append(await _measure_combo({**base, "protocol": proto, "scan": scan}, attempts))
            SW.done += 1
        SW.current = None
        best = sorted((r for r in SW.results if r["ok"]), key=_rank_key)
        if best:
            SW.winner = best[0]
            SW.winner_opts = {**base, "protocol": best[0]["protocol"], "scan": best[0]["scan"]}
        else:
            SW.error = "No configuration could connect and pass the latency probe."
    except asyncio.CancelledError:
        final = "cancelled"
    except Exception as e:  # never leave the panel stuck in maintenance
        final = "error"
        SW.error = str(e)[:200] or type(e).__name__
        logger.exception("best-config sweep failed")
    SW.current = None
    SW.status = "finishing"
    try:
        await _sweep_restore(final, save, prev)
    except Exception as e:
        logger.exception("could not restore the tunnel after the sweep")
        SW.error = SW.error or f"restore failed: {e}"[:200]
        log_line(f"[sweep] restore failed: {e}", "error")
    finally:
        SW.finished_at = time.time()
        SW.status = final
        S.maintenance = False
        if final == "done" and SW.winner:
            app_state.log_event("Info", f"Best config: {SW.winner['protocol']}/{SW.winner['scan']} "
                                        f"({SW.winner['avg_ms']} ms)")
        else:
            app_state.log_event("Info", f"Best-config test {final}")


async def _sweep_restore(final: str, save: bool, prev: dict) -> None:
    await _terminate()
    if SW.no_restore:
        S.wanted = False
        S.phase = "stopped"
        return
    W.reset_idle()
    W.next_restart_at = None

    if final == "done" and save and SW.winner_opts:
        wopts = SW.winner_opts
        await _save_cfg(options=wopts, last_good={"options": wopts, "at": int(time.time() * 1000)})
        SW.saved = True
        W.good_saved = True
        S.wanted = True
        await _start_impl(wopts, persist=False)
        return

    # back to what it was before the test
    S.options = prev["options"]
    S.gateway = None
    S.exit = None
    S.last_error = None
    if prev["running"] and prev["options"]:
        S.wanted = True
        await _start_impl(prev["options"], persist=False)
    else:
        S.wanted = bool(prev["wanted"])
        S.phase = "stopped"


# ---------------------------------------------------------------------------
# Installer
# ---------------------------------------------------------------------------

def _asset_name() -> str:
    if platform.system() != "Linux":
        raise AetherError(f"unsupported OS: {platform.system()}")
    m = platform.machine().lower()
    if m in ("x86_64", "amd64"):
        return "aether-linux-x86_64-musl.tar.gz"
    if m in ("aarch64", "arm64"):
        return "aether-linux-aarch64-musl.tar.gz"
    raise AetherError(f"unsupported architecture: {m}")


def _release_base() -> str:
    ver = getattr(settings, "aether_version", "") or os.environ.get("AETHER_VERSION", "")
    if ver and re.fullmatch(r"v?[0-9A-Za-z][0-9A-Za-z._-]*", ver):
        return f"https://github.com/CluvexStudio/Aether/releases/download/{ver}/"
    return "https://github.com/CluvexStudio/Aether/releases/latest/download/"


def _extract_binary(archive_path: str, dest: str) -> None:
    """Extract only the member named 'aether' (never trusts archive paths)."""
    with tarfile.open(archive_path, "r:gz") as tf:
        for member in tf.getmembers():
            if member.isfile() and os.path.basename(member.name) == "aether":
                src = tf.extractfile(member)
                if src is None:
                    continue
                with open(dest, "wb") as out:
                    while True:
                        chunk = src.read(1 << 20)
                        if not chunk:
                            break
                        out.write(chunk)
                return
    raise AetherError("the downloaded archive does not contain the aether binary")


async def install() -> dict[str, Any]:
    import httpx
    asset = _asset_name()
    base = _release_base()
    async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
        arch_r, sum_r = await asyncio.gather(client.get(base + asset), client.get(base + asset + ".sha256"))
    for r in (arch_r, sum_r):
        if r.status_code != 200:
            raise AetherError(f"download failed ({r.status_code}): {r.request.url}")
    parts = sum_r.text.strip().split()
    expected = parts[0].lower() if parts else ""
    actual = hashlib.sha256(arch_r.content).hexdigest()
    if not expected or expected != actual:
        raise AetherError("checksum of the downloaded file does not match")

    d = data_dir()
    archive = os.path.join(d, asset)
    tmp_bin = os.path.join(d, "aether.new")
    final = os.path.join(d, "aether")

    def _work() -> None:
        with open(archive, "wb") as f:
            f.write(arch_r.content)
        try:
            _extract_binary(archive, tmp_bin)
            os.chmod(tmp_bin, 0o755)
            os.replace(tmp_bin, final)  # atomic; safe even if the old binary is running
        finally:
            for p in (archive, tmp_bin):
                try:
                    os.remove(p)
                except FileNotFoundError:
                    pass

    await asyncio.to_thread(_work)

    version = None
    try:
        p = await asyncio.create_subprocess_exec(
            final, "--version", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        out, _ = await asyncio.wait_for(p.communicate(), timeout=5)
        version = out.decode(errors="replace").strip() or None
    except Exception:
        pass
    app_state.log_event("Info", f"Aether installed ({version or 'unknown version'})")
    return {"path": final, "sha256": actual, "version": version}


# ---------------------------------------------------------------------------
# Public API for routes / main
# ---------------------------------------------------------------------------

def status() -> dict[str, Any]:
    now = _now()
    t = _tuning()
    return {
        "binary": find_binary(),
        "running": S.proc is not None,
        "phase": S.phase,
        "pid": S.proc.pid if S.proc else None,
        "options": S.options,
        "saved_options": S.cfg.get("options"),
        "default_options": DEFAULT_OPTIONS,
        "gateway": S.gateway,
        "exit": S.exit,
        "last_error": S.last_error,
        "uptime_sec": int(now - S.connected_at) if S.connected_at is not None else None,
        "running_sec": int(now - S.started_at) if S.started_at is not None and S.proc else None,
        "logs": list(S.logs)[-250:],
        "wanted": S.wanted,
        "auto_start": S.auto_start,
        "outbound_mode": upstream.current_mode(),
        "outbound_active": upstream.uses_aether(),
        "outbound_env_override": bool(getattr(settings, "aether_outbound", "")),
        "last_good": S.cfg.get("last_good"),
        "maintenance": S.maintenance,
        "sweep": sweep_status(),
        "watchdog": {
            "enabled": S.watchdog_task is not None and not S.watchdog_task.done(),
            "consecutive_failures": W.consecutive_fails,
            "max_failures": t["max_failures"],
            "restarts": W.restarts,
            "next_restart_in_sec": (max(0, int(W.next_restart_at - now) + 1)
                                    if W.next_restart_at is not None else None),
            "last_check_ok": W.last_check_ok,
            "last_reason": W.last_reason,
        },
        "options_schema": {
            "protocol": PROTOCOLS, "transport": TRANSPORTS, "scan": SCAN_MODES,
            "ip": IP_MODES, "noize": NOIZE_PROFILES,
        },
    }


async def init() -> None:
    """Called once from the FastAPI lifespan."""
    upstream.configure(ready=is_connected)
    try:
        S.cfg = await _load_cfg()
    except Exception as e:
        logger.warning("could not load aether config: %s", e)
    from app.database import get_setting

    env_mode = (getattr(settings, "aether_outbound", "") or "").strip().lower()
    mode = env_mode or (await get_setting("aether_outbound", "")) or "direct"
    try:
        upstream.configure(mode=mode)
    except ValueError:
        logger.warning("invalid outbound mode %r, using 'direct'", mode)
    if S.cfg.get("options"):
        upstream.configure(socks_port=S.cfg["options"]["port"])

    env_auto = _env_bool("AETHER_AUTO_START")
    S.auto_start = env_auto if env_auto is not None else (await get_setting("aether_auto_start", "0")) == "1"

    S.watchdog_task = asyncio.create_task(_watchdog_loop())

    if S.auto_start:
        if find_binary():
            try:
                await start(S.cfg.get("options"), persist=False)
            except AetherError as e:
                logger.warning("aether auto-start failed: %s", e)
        else:
            logger.warning("AETHER auto-start is on but the Aether binary was not found")


async def shutdown() -> None:
    S.wanted = False
    if S.maintenance and SW.task is not None and not SW.task.done():
        SW.no_restore = True
        await cancel_sweep()
    if S.watchdog_task:
        S.watchdog_task.cancel()
        try:
            await S.watchdog_task
        except (asyncio.CancelledError, Exception):
            pass
    await _terminate()
