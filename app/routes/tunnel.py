"""
WebSocket VLESS tunnel — the core proxy engine.
Parses VLESS headers, relays traffic between WS clients and TCP backends.
"""
import asyncio
import secrets
import socket
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app import state
from app.vless import parse_vless_header
from app.services.traffic import add_to_buffer
from app.services.upstream import open_upstream

router = APIRouter()
RELAY_BUF = 512 * 1024


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

        reader, writer = await open_upstream(address, port)
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
