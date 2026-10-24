"""
VLESS protocol utilities - link generation, subscription content,
and binary header parsing.
"""
import json
import time
import base64
from urllib.parse import quote
from app.config import settings
from app import state


def get_domain():
    return settings.domain


def format_host_port(host, port=443):
    import ipaddress
    host = host.strip("[]")
    try:
        ipaddress.IPv6Address(host)
        return f"[{host}]:{port}"
    except ipaddress.AddressValueError:
        return f"{host}:{port}"


def code_to_flag(code):
    if not code or len(code) != 2:
        return ""
    code = code.upper()
    try:
        return chr(ord(code[0]) + 127397) + chr(ord(code[1]) + 127397)
    except Exception:
        return ""


# VLESS encryption methods Xray accepts (used only to validate before emitting).
VALID_ENCRYPTIONS = (
    "none", "aes-128-gcm", "aes-256-gcm", "chacha20-poly1305",
    "zero", "aes-128-gcm-salt", "aes-256-gcm-salt", "chacha20-poly1305-salt",
)


def _sanitize_path(path: str, default: str) -> str:
    """Ensure a path starts with '/' and is not empty/unsafe."""
    if not path or not path.strip():
        return default
    p = path.strip()
    if not p.startswith("/"):
        p = "/" + p
    parts = [seg for seg in p.split("/") if seg != ""]
    return "/" + "/".join(parts) if parts else default


def _resolve_encryption(extra) -> str:
    enc = (extra.get("encryption") or "none") if extra else "none"
    enc = str(enc).strip().lower()
    if enc not in VALID_ENCRYPTIONS:
        return "none"
    return enc


async def _ob_path(key: str, default: str) -> str:
    """Read a configurable outbound path template from settings (DB)."""
    try:
        from app.database import get_setting
        v = await get_setting(key, "")
        if v:
            return v
    except Exception:
        pass
    return default


class LinkConfigError(Exception):
    """Raised when a link can't be generated because required config is missing."""
    pass


async def generate_vless_link(uid, remark="SE7O", address=None, extra=None):
    """
    Build a VLESS-over-WebSocket link. WebSocket is the only supported
    transport; any other stored/requested transport value is treated as ws.
    """
    cache_key = f"{uid}:{remark}:{address}:{json.dumps(extra) if extra else ''}"
    cached = state.link_cache.get(cache_key)
    if cached and cached["expires"] > time.time():
        return cached["link"]

    domain = get_domain()
    addr = address or domain
    sni = (extra.get("custom_sni") or domain) if extra else domain
    host = (extra.get("custom_host") or domain) if extra else domain
    fp = (extra.get("custom_fp") or "chrome") if extra else "chrome"
    fragment = extra.get("fragment", "") if extra else ""
    encryption = _resolve_encryption(extra)

    default_path = await _ob_path("ob_ws_path", f"/ws/{uid}")
    path = _sanitize_path(
        (extra.get("custom_path") or default_path) if extra else default_path,
        default_path,
    )
    params = {
        "encryption": encryption, "security": "tls", "type": "ws",
        "host": host, "path": path, "sni": sni, "fp": fp, "alpn": "http/1.1",
    }
    if fragment:
        params["fragment"] = fragment

    if "path" in params and params["path"]:
        params["path"] = params["path"].replace("{uuid}", uid).replace("{uid}", uid)
    query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    safe_remark = quote(remark.encode("utf-8", errors="replace").decode("utf-8"))
    link = f"vless://{uid}@{format_host_port(addr, 443)}?{query}#{safe_remark}"

    state.link_cache[cache_key] = {"link": link, "expires": time.time() + settings.link_cache_ttl}
    return link


async def generate_vless_json(uid, remark="SE7O", address=None, extra=None):
    """
    Build a standard v2ray/Xray client config (JSON) for this link, suitable
    for direct import into clients that accept v2rayN / v2rayNG / NekoBox /
    Streisand-style JSON (rather than a vless:// URI).

    Returns a dict; serialize it with json.dumps for the API/modal.
    """
    domain = get_domain()
    addr = address or domain
    sni = (extra.get("custom_sni") or domain) if extra else domain
    host = (extra.get("custom_host") or domain) if extra else domain
    fp = (extra.get("custom_fp") or "chrome") if extra else "chrome"
    fragment = extra.get("fragment", "") if extra else ""
    encryption = _resolve_encryption(extra)

    default_path = await _ob_path("ob_ws_path", f"/ws/{uid}")
    net_settings = {
        "protocol": "ws",
        "wsSettings": {
            "path": _sanitize_path(
                (extra.get("custom_path") or default_path) if extra else default_path,
                default_path,
            ).replace("{uuid}", uid).replace("{uid}", uid),
            "headers": {"Host": host},
        },
    }
    security = "tls"
    sec_settings = {
        "tlsSettings": {
            "serverName": sni,
            "alpn": ["http/1.1"],
            "fingerprint": fp,
        }
    }
    outbound_address = addr
    outbound_port = 443

    vnext = [{
        "address": outbound_address,
        "port": outbound_port,
        "users": [{
            "id": uid,
            "encryption": encryption,
            "level": 0,
        }],
    }]

    outbound = {
        "tag": "proxy",
        "protocol": "vless",
        "settings": {"vnext": vnext, "servers": []},
        "streamSettings": {
            "network": "ws",
            "security": security,
            **net_settings,
            **sec_settings,
        },
        "mux": {"enabled": False, "concurrency": 8},
    }
    if fragment:
        outbound["streamSettings"]["fragment"] = fragment

    return {
        "remarks": remark,
        "log": {"loglevel": "warning"},
        "outbounds": [outbound, {
            "tag": "direct",
            "protocol": "freedom",
            "settings": {},
        }, {
            "tag": "block",
            "protocol": "blackhole",
            "settings": {},
        }],
        "inbounds": [{
            "tag": "socks",
            "port": 10808,
            "listen": "127.0.0.1",
            "protocol": "socks",
            "settings": {"udp": True},
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls", "quic"],
            },
        }, {
            "tag": "http",
            "port": 10809,
            "listen": "127.0.0.1",
            "protocol": "http",
            "settings": {},
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls", "quic"],
            },
        }],
        "routing": {
            "domainStrategy": "IPIfNonIP",
            "rules": [
                {"type": "field", "ip": ["geoip:private"], "outboundTag": "direct"},
                {"type": "field", "domain": ["geosite:category-ads-all"], "outboundTag": "block"},
            ],
        },
        "dns": {
            "servers": [
                {"address": "1.1.1.1", "port": 53, "domains": ["geosite:category-ads-all"]},
                {"address": "8.8.8.8", "port": 53},
            ],
            "queryStrategy": "UseIPv4",
        },
    }


async def generate_subscription_content(link, uid, addresses, extra=None, status="active"):
    used = link.get("used_bytes", 0)
    limit = link.get("limit_bytes", 0)
    usage_str = f"{_fmt_bytes(used)} / \u221e" if limit == 0 else f"{_fmt_bytes(used)} / {_fmt_bytes(limit)}"

    secs_left = _seconds_until_expiry(link.get("expires_at"))
    expiry_str = "\u221e" if secs_left is None else ("Expired" if secs_left == 0 else f"{secs_left // 86400} Days Left")

    status_remark = ""
    if status == "quota_exceeded":
        status_remark = " Quota Exceeded"
    elif status == "expired":
        status_remark = " Expired"
    elif status == "blocked":
        status_remark = " Blocked"

    full_remark = f"{usage_str} | {expiry_str}"
    if status_remark:
        full_remark += f" | {status_remark}"

    flag_emoji = code_to_flag(link.get("flag", ""))
    if flag_emoji:
        full_remark = flag_emoji + " " + full_remark

    status_node = await generate_vless_link(uid, remark=full_remark, address="0.0.0.0", extra=extra)
    lbl = link.get("label", "")
    server_remark = f"{flag_emoji}SE7O-SNA / This Service is Free" if flag_emoji else "SE7O-SNA / This Service is Free"
    server_node = await generate_vless_link(uid, remark=server_remark, extra=extra)

    links_list = [status_node, server_node]
    for i, addr in enumerate(addresses):
        if flag_emoji:
            r = flag_emoji + "SE7O-" + lbl + "-IP" + str(i + 1)
        else:
            r = "SE7O-" + lbl + "-IP" + str(i + 1)
        links_list.append(await generate_vless_link(uid, remark=r, address=addr, extra=extra))

    return "\n".join(links_list)


def encode_subscription(content):
    return base64.b64encode(content.encode("utf-8")).decode("utf-8")


async def parse_vless_header(first_chunk):
    if len(first_chunk) < 24:
        raise ValueError("VLESS header too small")
    pos = 1 + 16
    addon_len = first_chunk[pos]
    pos += 1 + addon_len
    if len(first_chunk) < pos + 3:
        raise ValueError("Malformed VLESS header")
    command = first_chunk[pos]
    pos += 1
    port = int.from_bytes(first_chunk[pos:pos + 2], "big")
    pos += 2
    addr_type = first_chunk[pos]
    pos += 1

    if addr_type == 1:
        if len(first_chunk) < pos + 4:
            raise ValueError("Incomplete IPv4")
        address = ".".join(str(b) for b in first_chunk[pos:pos + 4])
        pos += 4
    elif addr_type == 2:
        if len(first_chunk) < pos + 1:
            raise ValueError("Missing domain length")
        domain_len = first_chunk[pos]
        pos += 1
        if len(first_chunk) < pos + domain_len:
            raise ValueError("Incomplete domain")
        address = first_chunk[pos:pos + domain_len].decode("utf-8", errors="ignore")
        pos += domain_len
    elif addr_type == 3:
        if len(first_chunk) < pos + 16:
            raise ValueError("Incomplete IPv6")
        ab = first_chunk[pos:pos + 16]
        address = ":".join(f"{ab[i]:02x}{ab[i + 1]:02x}" for i in range(0, 16, 2))
        pos += 16
    else:
        raise ValueError(f"Unsupported address type: {addr_type}")

    return command, address, port, first_chunk[pos:]


def _fmt_bytes(b):
    if not b:
        return "0 B"
    if b >= 1_073_741_824:
        return f"{b / 1_073_741_824:.1f}GB"
    if b >= 1_048_576:
        return f"{b / 1_048_576:.1f}MB"
    return f"{b / 1024:.1f}KB"


def _seconds_until_expiry(expires_at_str):
    if not expires_at_str:
        return None
    try:
        from datetime import datetime, timezone
        s = expires_at_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, int((dt - datetime.now(timezone.utc)).total_seconds()))
    except Exception:
        return None
