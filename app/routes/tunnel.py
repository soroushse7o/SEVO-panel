"""
WebSocket VLESS tunnel — the core proxy engine.
Parses VLESS headers, relays traffic between WS clients and TCP backends.
"""
import asyncio
import secrets
import socket
import time as _time
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import StreamingResponse, Response
from app import state
from app.config import settings
from app.vless import parse_vless_header
from app.services.traffic import add_to_buffer

router = APIRouter()
RELAY_BUF = 512 * 1024
XHTTP_SESSION_WAIT_TIMEOUT = 15.0


async def count_connections(uid: str) -> int:
    async with state.connections_lock:
        return sum(1 for info in state.connections.values() if info.get("uuid") == uid)


async def close_connections_for_link(uid: str):
    async with state.connections_lock:
        to_close = [cid for cid, info in state.connections.items() if info.get("uuid") == uid]
    for cid in to_close:
        ws = state.connection_sockets.get(cid)
        if ws:
            try:
                await ws.close(code=1000, reason="link deleted/blocked")
            except Exception:
                pass
        async with state.connections_lock:
            state.connections.pop(cid, None)
            state.connection_sockets.pop(cid, None)
    async with state.connections_lock:
        state.link_ip_map.pop(uid, None)


async def check_quota(uid: str, extra_bytes: int) -> bool:
    async with state.links_lock:
        link = state.links.get(uid)
        if not link or not link["active"]:
            return False
        if link["limit_bytes"] == 0:
            return True
        return (link["used_bytes"] + extra_bytes) <= link["limit_bytes"]


async def add_usage(uid: str, n: int):
    from app.services.telegram import notify_event
    async with state.links_lock:
        if uid in state.links:
            link = state.links[uid]
            link["used_bytes"] += n
            limit = link["limit_bytes"]
            if limit > 0 and link["used_bytes"] >= limit * 0.9 and (link["used_bytes"] - n) < limit * 0.9:
                state.log_event("Warning", f"Inbound {link['label']} ({uid}) has used over 90% of quota")
                asyncio.create_task(notify_event("quota_90", link["label"], uid))
            elif limit > 0 and link["used_bytes"] >= limit * 0.8 and (link["used_bytes"] - n) < limit * 0.8:
                state.log_event("Warning", f"Inbound {link['label']} ({uid}) has used over 80% of quota")


async def _ws_to_tcp(websocket, writer, conn_id, link_uid):
    try:
        while True:
            msg = await websocket.receive()
            if msg["type"] == "websocket.disconnect":
                break
            data = msg.get("bytes") or (msg.get("text") or "").encode()
            if not data:
                continue
            size = len(data)
            if not await check_quota(link_uid, size):
                await websocket.close(code=1008, reason="quota exceeded")
                break
            state.stats["total_bytes"] += size
            state.stats["upload_bytes"] += size
            async with state.connections_lock:
                if conn_id in state.connections:
                    state.connections[conn_id]["bytes"] += size
            local_now = datetime.now(timezone.utc) + timedelta(hours=state.timezone_offset)
            await add_to_buffer(local_now.strftime("%Y-%m-%d %H:00"), local_now.strftime("%Y-%m-%d"), size)
            await add_usage(link_uid, size)
            try:
                writer.write(data)
                await writer.drain()
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        try:
            if writer and not writer.is_closing():
                writer.write_eof()
        except Exception:
            pass


async def _tcp_to_ws(websocket, reader, conn_id, link_uid):
    first = True
    try:
        while True:
            data = await reader.read(RELAY_BUF)
            if not data:
                break
            size = len(data)
            if not await check_quota(link_uid, size):
                await websocket.close(code=1008, reason="quota exceeded")
                break
            state.stats["total_bytes"] += size
            state.stats["download_bytes"] += size
            async with state.connections_lock:
                if conn_id in state.connections:
                    state.connections[conn_id]["bytes"] += size
            local_now = datetime.now(timezone.utc) + timedelta(hours=state.timezone_offset)
            await add_to_buffer(local_now.strftime("%Y-%m-%d %H:00"), local_now.strftime("%Y-%m-%d"), size)
            await add_usage(link_uid, size)
            try:
                await websocket.send_bytes((b"\x00\x00" + data) if first else data)
                first = False
            except Exception:
                break
    except Exception:
        pass


def get_client_ip(websocket: WebSocket) -> str:
    forwarded = websocket.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if websocket.client:
        return websocket.client.host
    return "unknown"


async def _validate_link(uid: str):
    """Shared active/expiry/max-connections check used by every transport.
    Returns (ok: bool, max_conn: int, reason: str)."""
    async with state.links_lock:
        link = state.links.get(uid)
        if not link or not link["active"]:
            return False, 0, "not found or disabled"
        max_conn = link.get("max_connections", 0)

    expires_at = link.get("expires_at")
    if expires_at:
        try:
            exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < datetime.now(timezone.utc):
                return False, 0, "expired"
        except Exception:
            pass

    if max_conn > 0 and await count_connections(uid) >= max_conn:
        return False, 0, "connection limit"

    return True, max_conn, ""


@router.websocket("/ws/{uuid}")
async def websocket_tunnel(websocket: WebSocket, uuid: str):
    await websocket.accept()
    writer = None
    conn_id = None
    client_ip = get_client_ip(websocket)
    try:
        async with state.links_lock:
            link = state.links.get(uuid)
            if not link or not link["active"]:
                await websocket.close(code=1008, reason="not found or disabled")
                return
            max_conn = link.get("max_connections", 0)

        # Check expiry
        expires_at = link.get("expires_at")
        if expires_at:
            try:
                exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if exp < datetime.now(timezone.utc):
                    await websocket.close(code=1008, reason="expired")
                    return
            except Exception:
                pass

        if max_conn > 0 and await count_connections(uuid) >= max_conn:
            await websocket.close(code=1008, reason="connection limit")
            return

        first_msg = await asyncio.wait_for(websocket.receive(), timeout=15.0)
        if first_msg["type"] == "websocket.disconnect":
            return
        first_chunk = first_msg.get("bytes") or (first_msg.get("text") or "").encode()
        if not first_chunk:
            return

        try:
            command, address, port, initial_payload = await parse_vless_header(first_chunk)
        except ValueError as e:
            await websocket.close(code=1008, reason="invalid header")
            return

        conn_id = secrets.token_urlsafe(8)
        now = datetime.now(timezone.utc).isoformat()
        async with state.connections_lock:
            state.connections[conn_id] = {
                "uuid": uuid, "ip": client_ip, "connected_at": now,
                "bytes": 0, "last_active": __import__("time").time(),
            }
            state.connection_sockets[conn_id] = websocket
            state.link_ip_map[uuid].add(client_ip)

        state.stats["total_requests"] += 1

        if initial_payload:
            p_size = len(initial_payload)
            state.stats["total_bytes"] += p_size
            state.stats["upload_bytes"] += p_size
            await add_usage(uuid, p_size)

        reader, writer = await asyncio.wait_for(asyncio.open_connection(address, port), timeout=10.0)
        try:
            sock = writer.get_extra_info("socket")
            if sock:
                # NOTE: this was mislabeled "TCP_FASTOPEN" but level=6/opt=1 is
                # actually IPPROTO_TCP/TCP_NODELAY on Linux (opt 1), not
                # TCP_FASTOPEN (opt 23). TCP_NODELAY is what we actually want
                # here anyway (disables Nagle's algorithm for lower latency
                # on the relayed connection), so keep the effect but name it
                # correctly via the socket module constants.
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass

        if initial_payload:
            try:
                writer.write(initial_payload)
                await writer.drain()
            except Exception:
                pass

        up_task = asyncio.create_task(_ws_to_tcp(websocket, writer, conn_id, uuid))
        down_task = asyncio.create_task(_tcp_to_ws(websocket, reader, conn_id, uuid))
        done, pending = await asyncio.wait({up_task, down_task}, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

    except WebSocketDisconnect:
        pass
    except Exception:
        state.stats["total_errors"] += 1
        # Errors like a connect timeout can happen before the up/down relay
        # tasks exist, in which case nothing else closes the socket — do it
        # here so the connection doesn't linger open on the server side.
        try:
            await websocket.close(code=1011, reason="internal error")
        except Exception:
            pass
    finally:
        if writer:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
        if conn_id:
            async with state.connections_lock:
                info = state.connections.pop(conn_id, None)
                state.connection_sockets.pop(conn_id, None)
                if info:
                    uid = info.get("uuid")
                    ip = info.get("ip")
                    if uid and ip:
                        if not any(c.get("uuid") == uid and c.get("ip") == ip for c in state.connections.values()):
                            if uid in state.link_ip_map:
                                state.link_ip_map[uid].discard(ip)
                                if not state.link_ip_map[uid]:
                                    state.link_ip_map.pop(uid, None)


# ---------------------------------------------------------------------------
# XHTTP transport (Xray "splithttp", stream-up mode)
# ---------------------------------------------------------------------------
# Two long-lived HTTP requests share one session_id and together behave like
# one full-duplex connection:
#   POST /xhttp/{uuid}/{session_id}  <- client uploads (chunked body); the
#                                        first bytes are the VLESS header.
#   GET  /xhttp/{uuid}/{session_id}  -> server downloads (chunked response).
# The POST handler owns opening the backend TCP connection (it's the one
# that sees the VLESS header first) and publishes it into
# state.xhttp_sessions; the GET handler waits for that to appear.
# This is plain HTTP/1.1-compatible (two separate unidirectional requests),
# unlike XHTTP's "stream-one" mode which needs true request/response
# concurrency (HTTP/2) that most PaaS front proxies don't guarantee.

async def _xhttp_cleanup(session_id: str, uid: str, client_ip: str):
    async with state.xhttp_lock:
        sess = state.xhttp_sessions.pop(session_id, None)
    if sess:
        writer = sess.get("writer")
        if writer:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
        conn_id = sess.get("conn_id")
        if conn_id:
            async with state.connections_lock:
                info = state.connections.pop(conn_id, None)
                if info:
                    ip = info.get("ip")
                    if ip and uid in state.link_ip_map:
                        if not any(c.get("uuid") == uid and c.get("ip") == ip for c in state.connections.values()):
                            state.link_ip_map[uid].discard(ip)
                            if not state.link_ip_map[uid]:
                                state.link_ip_map.pop(uid, None)


@router.post("/xhttp/{uuid}/{session_id}")
async def xhttp_upload(request: Request, uuid: str, session_id: str):
    ok, max_conn, reason = await _validate_link(uuid)
    if not ok:
        return Response(status_code=403)

    forwarded = request.headers.get("x-forwarded-for")
    client_ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")

    buf = bytearray()
    writer = None
    reader = None
    conn_id = None
    header_parsed = False
    initial_payload = b""

    try:
        async for chunk in request.stream():
            if not chunk:
                continue
            if not header_parsed:
                buf.extend(chunk)
                if len(buf) < 24:
                    continue
                try:
                    command, address, port, initial_payload = await parse_vless_header(bytes(buf))
                except ValueError:
                    # Unlike a WebSocket frame (one logical message per
                    # send()), an HTTP POST body is a raw byte stream that
                    # can be split across network chunks anywhere -- a
                    # long domain name can easily land the header across
                    # two or more chunks. Keep buffering (up to a sane cap
                    # to bound memory from garbage input) instead of
                    # failing on the first incomplete read.
                    if len(buf) > 4096:
                        return Response(status_code=400)
                    continue
                header_parsed = True

                conn_id = secrets.token_urlsafe(8)
                now = datetime.now(timezone.utc).isoformat()
                async with state.connections_lock:
                    state.connections[conn_id] = {
                        "uuid": uuid, "ip": client_ip, "connected_at": now,
                        "bytes": 0, "last_active": _time.time(),
                    }
                    state.link_ip_map[uuid].add(client_ip)
                state.stats["total_requests"] += 1

                try:
                    reader, writer = await asyncio.wait_for(asyncio.open_connection(address, port), timeout=10.0)
                except Exception:
                    async with state.connections_lock:
                        state.connections.pop(conn_id, None)
                    return Response(status_code=502)

                try:
                    sock = writer.get_extra_info("socket")
                    if sock:
                        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                except Exception:
                    pass

                async with state.xhttp_lock:
                    state.xhttp_sessions[session_id] = {
                        "reader": reader, "writer": writer, "uuid": uuid,
                        "conn_id": conn_id, "ready": True,
                    }

                if initial_payload:
                    size = len(initial_payload)
                    state.stats["total_bytes"] += size
                    state.stats["upload_bytes"] += size
                    await add_usage(uuid, size)
                    try:
                        writer.write(initial_payload)
                        await writer.drain()
                    except Exception:
                        break
                continue

            size = len(chunk)
            if not await check_quota(uuid, size):
                break
            state.stats["total_bytes"] += size
            state.stats["upload_bytes"] += size
            async with state.connections_lock:
                if conn_id in state.connections:
                    state.connections[conn_id]["bytes"] += size
            local_now = datetime.now(timezone.utc) + timedelta(hours=state.timezone_offset)
            await add_to_buffer(local_now.strftime("%Y-%m-%d %H:00"), local_now.strftime("%Y-%m-%d"), size)
            await add_usage(uuid, size)
            try:
                writer.write(chunk)
                await writer.drain()
            except Exception:
                break
    except Exception:
        state.stats["total_errors"] += 1
    finally:
        try:
            if writer and not writer.is_closing():
                writer.write_eof()
        except Exception:
            pass

    return Response(status_code=200)


# ---------------------------------------------------------------------------
# XHTTP stream-one mode (single full-duplex POST request).
# The client sends ONE long-lived POST whose body is the VLESS upstream
# bytes; the server replies with a chunked response carrying downstream
# bytes. This is HTTP/1.1-compatible and works behind PaaS front proxies
# (unlike stream-up which needs two separate requests on one session).
# ---------------------------------------------------------------------------
@router.post("/xhttp1/{uuid}")
async def xhttp_stream_one(request: Request, uuid: str):
    ok, max_conn, reason = await _validate_link(uuid)
    if not ok:
        return Response(status_code=403)

    forwarded = request.headers.get("x-forwarded-for")
    client_ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")

    buf = bytearray()
    reader_box = [None]
    writer = None
    conn_id = None
    header_parsed = False
    initial_payload = b""

    async def upstream():
        nonlocal writer, conn_id, header_parsed, initial_payload
        try:
            async for chunk in request.stream():
                if not chunk:
                    continue
                if not header_parsed:
                    buf.extend(chunk)
                    if len(buf) < 24:
                        continue
                    try:
                        command, address, port, initial_payload = await parse_vless_header(bytes(buf))
                    except ValueError:
                        if len(buf) > 4096:
                            return
                        continue
                    header_parsed = True

                    conn_id = secrets.token_urlsafe(8)
                    now = datetime.now(timezone.utc).isoformat()
                    async with state.connections_lock:
                        state.connections[conn_id] = {
                            "uuid": uuid, "ip": client_ip, "connected_at": now,
                            "bytes": 0, "last_active": _time.time(),
                        }
                        state.link_ip_map[uuid].add(client_ip)
                    state.stats["total_requests"] += 1

                    try:
                        reader_box[0], writer = await asyncio.wait_for(asyncio.open_connection(address, port), timeout=10.0)
                    except Exception:
                        async with state.connections_lock:
                            state.connections.pop(conn_id, None)
                        return
                    try:
                        sock = writer.get_extra_info("socket")
                        if sock:
                            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    except Exception:
                        pass

                    if initial_payload:
                        size = len(initial_payload)
                        state.stats["total_bytes"] += size
                        state.stats["upload_bytes"] += size
                        await add_usage(uuid, size)
                        try:
                            writer.write(initial_payload)
                            await writer.drain()
                        except Exception:
                            return
                    continue

                size = len(chunk)
                if not await check_quota(uuid, size):
                    break
                state.stats["total_bytes"] += size
                state.stats["upload_bytes"] += size
                async with state.connections_lock:
                    if conn_id in state.connections:
                        state.connections[conn_id]["bytes"] += size
                local_now = datetime.now(timezone.utc) + timedelta(hours=state.timezone_offset)
                await add_to_buffer(local_now.strftime("%Y-%m-%d %H:00"), local_now.strftime("%Y-%m-%d"), size)
                await add_usage(uuid, size)
                try:
                    writer.write(chunk)
                    await writer.drain()
                except Exception:
                    break
        except Exception:
            state.stats["total_errors"] += 1
        finally:
            try:
                if writer and not writer.is_closing():
                    writer.write_eof()
            except Exception:
                pass

    async def gen():
        pump = asyncio.create_task(upstream())
        try:
            # Wait until the backend connection is established by upstream().
            waited = 0.0
            while reader_box[0] is None and waited < 15.0 and not pump.done():
                await asyncio.sleep(0.02)
                waited += 0.02
            reader = reader_box[0]
            if reader is None:
                return
            while True:
                data = await reader.read(RELAY_BUF)
                if not data:
                    break
                size = len(data)
                if not await check_quota(uuid, size):
                    break
                state.stats["total_bytes"] += size
                state.stats["download_bytes"] += size
                async with state.connections_lock:
                    if conn_id in state.connections:
                        state.connections[conn_id]["bytes"] += size
                local_now = datetime.now(timezone.utc) + timedelta(hours=state.timezone_offset)
                await add_to_buffer(local_now.strftime("%Y-%m-%d %H:00"), local_now.strftime("%Y-%m-%d"), size)
                await add_usage(uuid, size)
                yield data
        except Exception:
            pass
        finally:
            await pump
            if writer:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass
            if conn_id:
                async with state.connections_lock:
                    state.connections.pop(conn_id, None)

    return StreamingResponse(gen(), media_type="application/octet-stream", headers={
        "X-Accel-Buffering": "no", "Cache-Control": "no-store",
    })


@router.get("/xhttp/{uuid}/{session_id}")
async def xhttp_download(request: Request, uuid: str, session_id: str):
    ok, _, reason = await _validate_link(uuid)
    if not ok:
        return Response(status_code=403)

    waited = 0.0
    while waited < XHTTP_SESSION_WAIT_TIMEOUT:
        async with state.xhttp_lock:
            sess = state.xhttp_sessions.get(session_id)
        if sess and sess.get("ready"):
            break
        await asyncio.sleep(0.05)
        waited += 0.05
    else:
        return Response(status_code=504)

    reader = sess["reader"]
    conn_id = sess.get("conn_id")

    async def gen():
        try:
            while True:
                data = await reader.read(RELAY_BUF)
                if not data:
                    break
                size = len(data)
                if not await check_quota(uuid, size):
                    break
                state.stats["total_bytes"] += size
                state.stats["download_bytes"] += size
                async with state.connections_lock:
                    if conn_id in state.connections:
                        state.connections[conn_id]["bytes"] += size
                local_now = datetime.now(timezone.utc) + timedelta(hours=state.timezone_offset)
                await add_to_buffer(local_now.strftime("%Y-%m-%d %H:00"), local_now.strftime("%Y-%m-%d"), size)
                await add_usage(uuid, size)
                yield data
        except Exception:
            pass
        finally:
            await _xhttp_cleanup(session_id, uuid, "")

    return StreamingResponse(gen(), media_type="application/octet-stream", headers={
        "X-Accel-Buffering": "no", "Cache-Control": "no-store",
    })


# ---------------------------------------------------------------------------
# HTTP transport (VLESS type=http) -- single full-duplex-over-one-request
# ---------------------------------------------------------------------------
# Unlike xhttp (which needs a paired POST+GET with a shared session_id),
# the "http" transport tunnels the whole VLESS session inside ONE long-lived
# HTTP POST whose body is chunked: the first bytes are the VLESS header,
# the rest is bidirectionally relayed. This is the most PaaS-friendly shape
# (a single streaming request survives Railway/Render front proxies far better
# than xhttp's two-request handshake) while still looking like ordinary HTTPS
# traffic on the panel's $PORT.
@router.post("/http/{uuid}")
async def http_tunnel(request: Request, uuid: str):
    ok, max_conn, reason = await _validate_link(uuid)
    if not ok:
        return Response(status_code=403)

    forwarded = request.headers.get("x-forwarded-for")
    client_ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")

    buf = bytearray()
    writer = None
    reader = None
    conn_id = None
    header_parsed = False
    initial_payload = b""

    async def upstream():
        nonlocal writer, reader, conn_id, header_parsed, initial_payload
        try:
            async for chunk in request.stream():
                if not chunk:
                    continue
                if not header_parsed:
                    buf.extend(chunk)
                    if len(buf) < 24:
                        continue
                    try:
                        command, address, port, initial_payload = await parse_vless_header(bytes(buf))
                    except ValueError:
                        return
                    header_parsed = True

                    conn_id = secrets.token_urlsafe(8)
                    now = datetime.now(timezone.utc).isoformat()
                    async with state.connections_lock:
                        state.connections[conn_id] = {
                            "uuid": uuid, "ip": client_ip, "connected_at": now,
                            "bytes": 0, "last_active": _time.time(),
                        }
                        state.link_ip_map[uuid].add(client_ip)
                    state.stats["total_requests"] += 1

                    try:
                        reader, writer = await asyncio.wait_for(asyncio.open_connection(address, port), timeout=10.0)
                    except Exception:
                        async with state.connections_lock:
                            state.connections.pop(conn_id, None)
                        return
                    try:
                        sock = writer.get_extra_info("socket")
                        if sock:
                            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    except Exception:
                        pass

                    asyncio.create_task(_http_backend_to_client(reader, uuid, conn_id))

                    if initial_payload:
                        size = len(initial_payload)
                        state.stats["total_bytes"] += size
                        state.stats["upload_bytes"] += size
                        await add_usage(uuid, size)
                        try:
                            writer.write(initial_payload)
                            await writer.drain()
                        except Exception:
                            return
                    continue

                size = len(chunk)
                if not await check_quota(uuid, size):
                    return
                state.stats["total_bytes"] += size
                state.stats["upload_bytes"] += size
                async with state.connections_lock:
                    if conn_id in state.connections:
                        state.connections[conn_id]["bytes"] += size
                local_now = datetime.now(timezone.utc) + timedelta(hours=state.timezone_offset)
                await add_to_buffer(local_now.strftime("%Y-%m-%d %H:00"), local_now.strftime("%Y-%m-%d"), size)
                await add_usage(uuid, size)
                try:
                    writer.write(chunk)
                    await writer.drain()
                except Exception:
                    return
        except Exception:
            state.stats["total_errors"] += 1
        finally:
            try:
                if writer and not writer.is_closing():
                    writer.write_eof()
            except Exception:
                pass

    async def gen():
        pump = asyncio.create_task(upstream())
        try:
            while True:
                if reader is None:
                    await asyncio.sleep(0.01)
                    continue
                data = await reader.read(RELAY_BUF)
                if not data:
                    break
                size = len(data)
                if not await check_quota(uuid, size):
                    break
                state.stats["total_bytes"] += size
                state.stats["download_bytes"] += size
                async with state.connections_lock:
                    if conn_id in state.connections:
                        state.connections[conn_id]["bytes"] += size
                local_now = datetime.now(timezone.utc) + timedelta(hours=state.timezone_offset)
                await add_to_buffer(local_now.strftime("%Y-%m-%d %H:00"), local_now.strftime("%Y-%m-%d"), size)
                await add_usage(uuid, size)
                yield data
        except Exception:
            pass
        finally:
            await pump
            if conn_id:
                async with state.connections_lock:
                    state.connections.pop(conn_id, None)
                    state.connection_sockets.pop(conn_id, None)
                    if uuid in state.link_ip_map:
                        state.link_ip_map[uuid].discard(client_ip)
                        if not state.link_ip_map[uuid]:
                            state.link_ip_map.pop(uuid, None)

    return StreamingResponse(gen(), media_type="application/octet-stream", headers={
        "X-Accel-Buffering": "no", "Cache-Control": "no-store",
    })


async def _http_backend_to_client(reader, uid, conn_id):
    """Fallback pump if the main generator lost the reader race."""
    try:
        while True:
            data = await reader.read(RELAY_BUF)
            if not data:
                break
    except Exception:
        pass

