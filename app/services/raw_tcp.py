"""
Raw-TCP VLESS listener (type=tcp, no TLS/WS/HTTP framing at all).

This is a second, independent TCP server bound to its own port
(RAW_TCP_PORT, default 8080) — the same pattern the MTProxy service already
uses for its own port. IMPORTANT: binding the port inside this process is
only half the story. For clients to actually reach it, the *host platform*
also has to forward an external port to it:

  - Railway: Settings -> Networking -> "TCP Proxy" on this service, pointed
    at RAW_TCP_PORT. Railway will hand you a public host:port pair (often a
    different public port than RAW_TCP_PORT) — put those into
    RAW_TCP_PUBLIC_HOST / RAW_TCP_PUBLIC_PORT so generated links use the
    right address. This is exactly how the existing MTProxy 443 port is
    exposed in this project already.
  - Render: web services only expose a single HTTP port. Render does not
    support extra raw TCP ports on the standard web service type, so
    RAW_TCP_ENABLED should stay off there.

If RAW_TCP_ENABLED is on but the platform doesn't forward the port, the
listener still runs fine inside the container — it's just unreachable from
the internet, and generated vless:// tcp links won't connect.
"""
import asyncio
import logging
import secrets
import socket
from datetime import datetime, timezone, timedelta

from app import state
from app.config import settings
from app.vless import parse_vless_header
from app.services.traffic import add_to_buffer
from app.services.upstream import open_upstream

logger = logging.getLogger("SE7OSNA.raw_tcp")

RELAY_BUF = 512 * 1024
_server = None


async def _check_quota(uid: str, extra_bytes: int) -> bool:
    async with state.links_lock:
        link = state.links.get(uid)
        if not link or not link["active"]:
            return False
        if link["limit_bytes"] == 0:
            return True
        return (link["used_bytes"] + extra_bytes) <= link["limit_bytes"]


async def _add_usage(uid: str, n: int):
    async with state.links_lock:
        if uid in state.links:
            state.links[uid]["used_bytes"] += n


async def _pipe(reader, writer, conn_id, uid, direction: str):
    try:
        while True:
            data = await reader.read(RELAY_BUF)
            if not data:
                break
            size = len(data)
            if not await _check_quota(uid, size):
                break
            state.stats["total_bytes"] += size
            state.stats["upload_bytes" if direction == "up" else "download_bytes"] += size
            async with state.raw_tcp_lock:
                if conn_id in state.raw_tcp_connections:
                    state.raw_tcp_connections[conn_id]["bytes"] += size
            local_now = datetime.now(timezone.utc) + timedelta(hours=state.timezone_offset)
            await add_to_buffer(local_now.strftime("%Y-%m-%d %H:00"), local_now.strftime("%Y-%m-%d"), size)
            await _add_usage(uid, size)
            writer.write(data)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            if not writer.is_closing():
                writer.write_eof()
        except Exception:
            pass


async def _handle_client(client_reader, client_writer):
    conn_id = secrets.token_urlsafe(8)
    backend_writer = None
    uid = None
    try:
        # A raw TCP read can return as soon as any bytes are available, not
        # necessarily the whole VLESS header in one call (same class of
        # issue as xhttp's chunked POST body) -- so accumulate until we can
        # actually parse it, bounded so garbage input can't grow forever.
        buf = bytearray()
        try:
            while len(buf) < 4096:
                chunk = await asyncio.wait_for(client_reader.read(16384), timeout=15.0)
                if not chunk:
                    return
                buf.extend(chunk)
                if len(buf) < 24:
                    continue
                try:
                    command, address, port, initial_payload = await parse_vless_header(bytes(buf))
                    break
                except ValueError:
                    continue
            else:
                return
        except asyncio.TimeoutError:
            return
        first_chunk = bytes(buf)

        # VLESS header doesn't carry the link uid the way ws/xhttp paths do
        # (those get it from the URL) — the uid IS the first 16 bytes of the
        # header. parse_vless_header only returns the parsed target, not the
        # uid, so recover it the same way the header spec defines it.
        import uuid as uuid_lib
        uid = str(uuid_lib.UUID(bytes=first_chunk[1:17]))

        async with state.links_lock:
            link = state.links.get(uid)
            if not link or not link["active"]:
                return
            expires_at = link.get("expires_at")
        if expires_at:
            try:
                exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if exp < datetime.now(timezone.utc):
                    return
            except Exception:
                pass

        try:
            backend_reader, backend_writer = await open_upstream(address, port)
        except Exception:
            return

        try:
            sock = backend_writer.get_extra_info("socket")
            if sock:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass

        peer = client_writer.get_extra_info("peername")
        client_ip = peer[0] if peer else "unknown"
        async with state.raw_tcp_lock:
            state.raw_tcp_connections[conn_id] = {
                "uuid": uid, "ip": client_ip,
                "connected_at": datetime.now(timezone.utc).isoformat(), "bytes": 0,
            }
        state.stats["total_requests"] += 1

        if initial_payload:
            size = len(initial_payload)
            state.stats["total_bytes"] += size
            state.stats["upload_bytes"] += size
            await _add_usage(uid, size)
            backend_writer.write(initial_payload)
            await backend_writer.drain()

        up = asyncio.create_task(_pipe(client_reader, backend_writer, conn_id, uid, "up"))
        down = asyncio.create_task(_pipe(backend_reader, client_writer, conn_id, uid, "down"))
        done, pending = await asyncio.wait({up, down}, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
    except Exception:
        state.stats["total_errors"] += 1
    finally:
        async with state.raw_tcp_lock:
            state.raw_tcp_connections.pop(conn_id, None)
        for w in (backend_writer, client_writer):
            try:
                if w and not w.is_closing():
                    w.close()
                    await w.wait_closed()
            except Exception:
                pass


async def start():
    global _server
    if not settings.raw_tcp_enabled:
        return
    try:
        _server = await asyncio.start_server(_handle_client, "0.0.0.0", settings.raw_tcp_port)
        logger.info("Raw-TCP VLESS listener bound on :%d (make sure the platform forwards it externally)", settings.raw_tcp_port)
    except Exception as e:
        logger.error("Failed to bind raw-TCP listener on :%d — %s", settings.raw_tcp_port, e)
        _server = None


async def stop():
    global _server
    if _server:
        _server.close()
        try:
            await _server.wait_closed()
        except Exception:
            pass
        _server = None
