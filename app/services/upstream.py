"""
Outbound connector — the single place where the panel opens a TCP connection
to the destination a client asked for.

Every transport (ws / xhttp / http / raw-tcp) used to call
``asyncio.open_connection(address, port)`` directly. They now call
``open_upstream(address, port)`` instead, which either connects directly
(default, identical to the old behaviour) or tunnels through the local
Aether SOCKS5 proxy (see app/services/aether.py).

Modes
-----
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
from typing import Callable, Tuple

MODES = ("direct", "aether", "auto")

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
                         timeout: float = 15.0) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """SOCKS5 CONNECT (no auth). Returns the (reader, writer) of the tunnelled stream."""
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(proxy_host, proxy_port), timeout=timeout)
    try:
        async def rd(n: int) -> bytes:
            return await asyncio.wait_for(reader.readexactly(n), timeout=timeout)

        writer.write(b"\x05\x01\x00")
        await writer.drain()
        ver, method = await rd(2)
        if ver != 5 or method != 0:
            raise UpstreamError("upstream SOCKS5 refused the greeting")

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


async def open_upstream(address: str, port: int, timeout: float = 10.0
                        ) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """Drop-in replacement for ``asyncio.open_connection(address, port)``."""
    if _mode == "aether" and not _ready():
        raise UpstreamError("outbound is set to Aether but the tunnel is not connected")
    if uses_aether():
        # Aether has to resolve + reach the destination through Cloudflare, so give it more room.
        return await socks5_connect(address, port, SOCKS_HOST, _socks_port, timeout=timeout + 8)
    return await asyncio.wait_for(asyncio.open_connection(address, port), timeout=timeout)
