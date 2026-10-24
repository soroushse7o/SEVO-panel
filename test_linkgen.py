"""
Verification of VLESS link generation across ws / xhttp / tcp / http transports
plus real encryption passthrough and path sanitization.

Proves the 3.0.4 regression fix (ws/xhttp security=tls) and that tcp is
built from RAW_TCP_* while the other three ride the platform HTTPS port.
"""
import asyncio
import sys
import importlib

sys.path.insert(0, ".")

from app.utils import load_app

# Load app with RAW_TCP_* set so tcp links build themselves.
config_mod, vless_mod = load_app(True, "metro.proxy.rlwy.net", "33114")

UID = "11111111-2222-3333-4444-555555555555"
passed = 0
failed = 0


def check(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        # print(f"PASS {name}")
    else:
        failed += 1
        print(f"FAIL {name} :: {extra}")


def params_of(link):
    """Return (netloc, dict-of-params) from a vless link."""
    from urllib.parse import urlsplit, parse_qsl
    rest = link.split("?", 1)[1].split("#", 1)[0] if "?" in link else ""
    q = dict(parse_qsl(rest))
    netloc = link.split("://", 1)[1].split("/", 1)[0].split("?", 1)[0]
    return netloc, q


async def main():
    # ---- ws ----
    link = await vless_mod.generate_vless_link(UID, remark="WS", extra={"transport": "ws"})
    nl, p = params_of(link)
    check("ws format", link.startswith(f"vless://{UID}@"), link)
    check("ws :443", nl.endswith(":443"), nl)
    check("ws type=ws", p.get("type") == "ws", p)
    check("ws security=tls", p.get("security") == "tls", p)
    check("ws path=/ws/uid", p.get("path") == f"/ws/{UID}", p)
    check("ws encryption=none default", p.get("encryption") == "none", p)

    # ---- ws with real encryption ----
    link = await vless_mod.generate_vless_link(UID, remark="WS", extra={"transport": "ws", "encryption": "aes-128-gcm"})
    _, p = params_of(link)
    check("ws encryption=aes-128-gcm", p.get("encryption") == "aes-128-gcm", p)

    # ---- xhttp ----
    link = await vless_mod.generate_vless_link(UID, remark="XH", extra={"transport": "xhttp"})
    nl, p = params_of(link)
    check("xhttp format", link.startswith(f"vless://{UID}@"), link)
    check("xhttp :443", nl.endswith(":443"), nl)
    check("xhttp type=xhttp", p.get("type") == "xhttp", p)
    check("xhttp security=tls", p.get("security") == "tls", p)
    check("xhttp mode=stream-one", p.get("mode") == "stream-one", p)
    check("xhttp path=/xhttp1/uid", p.get("path") == f"/xhttp1/{UID}", p)

    # ---- http ----
    link = await vless_mod.generate_vless_link(UID, remark="HTTP", extra={"transport": "http"})
    nl, p = params_of(link)
    check("http format", link.startswith(f"vless://{UID}@"), link)
    check("http :443", nl.endswith(":443"), nl)
    check("http type=http", p.get("type") == "http", p)
    check("http security=tls", p.get("security") == "tls", p)
    check("http path=/http/uid", p.get("path") == f"/http/{UID}", p)

    # ---- tcp ----
    link = await vless_mod.generate_vless_link(UID, remark="TCP", extra={"transport": "tcp"})
    nl, p = params_of(link)
    check("tcp format", link.startswith(f"vless://{UID}@"), link)
    check("tcp host=public", nl.startswith("metro.proxy.rlwy.net:33114"), nl)
    check("tcp security=none", p.get("security") == "none", p)
    check("tcp type=tcp", p.get("type") == "tcp", p)
    check("tcp no path", "path" not in p, p)

    # tcp with RAW_TCP_ENABLED=false must raise
    config_mod.settings.raw_tcp_enabled = False
    try:
        await vless_mod.generate_vless_link(UID, remark="TCP", extra={"transport": "tcp"})
        check("tcp raises when disabled", False, "no error")
    except vless_mod.LinkConfigError:
        check("tcp raises when disabled", True)
    config_mod.settings.raw_tcp_enabled = True

    # ---- path sanitization ----
    link = await vless_mod.generate_vless_link(UID, remark="P", extra={"transport": "ws", "custom_path": "ws//weird//"})
    _, p = params_of(link)
    check("path sanitized (no double slash)", "//" not in p.get("path", ""), p.get("path"))
    check("path starts with /", p.get("path", "").startswith("/"), p.get("path"))

    # ---- encryption invalid falls back to none ----
    link = await vless_mod.generate_vless_link(UID, remark="E", extra={"transport": "ws", "encryption": "bogus"})
    _, p = params_of(link)
    check("invalid encryption -> none", p.get("encryption") == "none", p.get("encryption"))


if __name__ == "__main__":
    asyncio.run(main())
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
