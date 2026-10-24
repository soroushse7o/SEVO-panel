"""
Outbound connector — the single place where the panel opens a TCP connection
to the destination a client asked for.

The WebSocket transport used to call
``asyncio.open_connection(address, port)`` directly. It now calls
``open_upstream(address, port)`` instead, which either connects directly
(default, identical to the old behaviour) or tunnels through the local
Aether SOCKS5 proxy (see app/services/aether.py).

Per-inbound routing
-------------------
Every inbound (link) carries an ``outbound`` field that overrides the global
mode for that inbound only:

default        follow the global mode below (the default)
direct         always connect directly from this server
aether         always via Aether / Cloudflare WARP (fail-closed)
auto           via Aether while connected, otherwise direct
socks5://[user:pass@]host:port
               any external SOCKS5 proxy

Global modes
------------
direct  always connect directly (default)
aether  always go through Aether; if the tunnel is not connected the
        connection FAILS (fail-closed, nothing leaks out of the host IP)
auto    go through Aether while it is connected, otherwise connect directly

This module is deliberately dependency-free (stdlib only) so it can be
unit-tested without the web stack.
"""
import asyncio
import ipaddress
import struct
from typing import Callable, Optional, Tuple
from urllib.parse import unquote, urlsplit

MODES = ("direct", "aether", "auto")
ROUTE_KEYWORDS = ("default",) + MODES
_ROUTE_ALIASES = {"warp": "aether", "cloudflare": "aether", "wrap": "aether"}

SOCKS_HOST = "127.0.0.1"
_mode = "direct"
_socks_port = 1819
_ready: Callable[[], bool] = lambda: False


class UpstreamError(OSError):
    """Raised when the outbound connection cannot be established."""


def configure(mode: str | None = None, socks_port: int | None = None,
              ready: Callable[[], bool] | None = None) -> None:
    global _mode, _socks_port, _ready
    if mode is not None:
        if mode not in MODES:
            raise ValueError(f"invalid outbound mode: {mode!r}")
        _mode = mode
    if socks_port is not None:
        _socks_port = int(socks_port)
    if ready is not None:
        _ready = ready


def current_mode() -> str:
    return _mode


def socks_port() -> int:
    return _socks_port


def uses_aether() -> bool:
    """True if a new connection made right now would go through Aether."""
    return _mode == "aether" or (_mode == "auto" and bool(_ready()))


def parse_route(raw) -> str:
    """
    Validate + canonicalise a per-inbound outbound value.

    Returns one of ``default|direct|aether|auto`` or a normalised
    ``socks5://[user:pass@]host:port`` string. Raises ValueError otherwise.
    """
    v = str(raw if raw is not None else "").strip()
    if not v:
        return "default"
    low = v.lower()
    low = _ROUTE_ALIASES.get(low, low)
    if low in ROUTE_KEYWORDS:
        return low
    if low.startswith(("socks5://", "socks5h://")):
        if len(v) > 200:
            raise ValueError("proxy URL is too long")
        try:
            u = urlsplit(v)
            host, port = u.hostname, u.port
        except ValueError:
            raise ValueError("invalid SOCKS5 proxy URL")
        if not host or not port or not (1 <= port <= 65535):
            raise ValueError("SOCKS5 proxy must look like socks5://host:port")
        auth = ""
        if u.username:
            auth = u.username + (":" + u.password if u.password else "") + "@"
        h = f"[{host}]" if ":" in host else host
        return f"socks5://{auth}{h}:{port}"
    raise ValueError("outbound must be default, direct, aether (WARP), auto or socks5://host:port")


def describe_route(route: Optional[str]) -> str:
    """Safe-to-display version of a route (strips proxy credentials)."""
    r = route or "default"
    if r.startswith("socks5://"):
        u = urlsplit(r)
        h = f"[{u.hostname}]" if u.hostname and ":" in u.hostname else u.hostname
        return f"socks5://{h}:{u.port}"
    return r


def resolve_route(route: Optional[str]) -> str:
    """
    Decide how a NEW connection for an inbound with this ``route`` leaves the
    server. Returns ``'direct'``, ``'aether'`` or a ``socks5://...`` URL.
    Raises UpstreamError when the route is fail-closed and unavailable.
    """
    r = route or "default"
    effective = _mode if r == "default" else r
    if effective.startswith("socks5://"):
        return effective
    if effective == "aether":
        if not _ready():
            raise UpstreamError("outbound is set to Aether but the tunnel is not connected")
        return "aether"
    if effective == "auto":
        return "aether" if _ready() else "direct"
    return "direct"


def route_uses_aether(route: Optional[str]) -> bool:
    try:
        return resolve_route(route) == "aether"
    except UpstreamError:
        return True  # fail-closed aether: it WOULD use Aether if it were up


def _addr_bytes(host: str, port: int) -> bytes:
    port_b = struct.pack(">H", port)
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        name = host.encode("idna") if not host.isascii() else host.encode("ascii")
        if not name or len(name) > 255:
            raise UpstreamError("invalid destination host")
        return b"\x03" + bytes([len(name)]) + name + port_b
    return (b"\x01" if ip.version == 4 else b"\x04") + ip.packed + port_b


async def socks5_connect(address: str, port: int, proxy_host: str, proxy_port: int,
                         timeout: float = 15.0, auth: Optional[Tuple[str, str]] = None
                         ) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """SOCKS5 CONNECT (no auth, or RFC 1929 user/pass when ``auth`` is given).
    Returns the (reader, writer) of the tunnelled stream."""
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(proxy_host, proxy_port), timeout=timeout)
    try:
        async def rd(n: int) -> bytes:
            return await asyncio.wait_for(reader.readexactly(n), timeout=timeout)

        writer.write(b"\x05\x02\x00\x02" if auth else b"\x05\x01\x00")
        await writer.drain()
        ver, method = await rd(2)
        if ver != 5 or method not in ((0, 2) if auth else (0,)):
            raise UpstreamError("upstream SOCKS5 refused the greeting")
        if method == 2:
            u, p = auth[0].encode(), auth[1].encode()
            if len(u) > 255 or len(p) > 255:
                raise UpstreamError("SOCKS5 credentials too long")
            writer.write(b"\x01" + bytes([len(u)]) + u + bytes([len(p)]) + p)
            await writer.drain()
            v2, status = await rd(2)
            if status != 0:
                raise UpstreamError("upstream SOCKS5 rejected the username/password")

        writer.write(b"\x05\x01\x00" + _addr_bytes(address, port))
        await writer.drain()
        head = await rd(4)
        if head[0] != 5 or head[1] != 0:
            raise UpstreamError(f"upstream SOCKS5 connect failed (code {head[1]})")
        atyp = head[3]
        if atyp == 1:
            await rd(4 + 2)
        elif atyp == 4:
            await rd(16 + 2)
        elif atyp == 3:
            (ln,) = await rd(1)
            await rd(ln + 2)
        else:
            raise UpstreamError("upstream SOCKS5 sent a bad reply")
        return reader, writer
    except BaseException:
        writer.close()
        raise


async def open_upstream(address: str, port: int, timeout: float = 10.0, route: Optional[str] = None
                        ) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """
    Drop-in replacement for ``asyncio.open_connection(address, port)``.

    ``route`` is the inbound's own outbound setting (see module docstring);
    ``None`` / ``"default"`` follows the global mode.
    """
    how = resolve_route(route)
    if how == "aether":
        # Aether has to resolve + reach the destination through Cloudflare, so give it more room.
        return await socks5_connect(address, port, SOCKS_HOST, _socks_port, timeout=timeout + 8)
    if how.startswith("socks5://"):
        u = urlsplit(how)
        auth = (unquote(u.username), unquote(u.password or "")) if u.username else None
        return await socks5_connect(address, port, u.hostname, u.port, timeout=timeout + 8, auth=auth)
    return await asyncio.wait_for(asyncio.open_connection(address, port), timeout=timeout)
