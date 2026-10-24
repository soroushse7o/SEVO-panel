"""
Verification of VLESS link generation (WebSocket is the only transport),
plus real encryption passthrough and path sanitization.
"""
import asyncio
import sys

sys.path.insert(0, ".")

import app.config as config_mod
import app.vless as vless_mod


class _FakeSettings:
    domain = "panel.example.com"
    secret_key = "test"
    link_cache_ttl = 0


config_mod.settings = _FakeSettings()
vless_mod.settings = config_mod.settings

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

    # ---- legacy transport values are served as ws ----
    for legacy in ("xhttp", "http", "tcp"):
        link = await vless_mod.generate_vless_link(UID, remark="L", extra={"transport": legacy})
        nl, p = params_of(link)
        check(f"{legacy} -> ws type", p.get("type") == "ws", p)
        check(f"{legacy} -> ws path", p.get("path") == f"/ws/{UID}", p)
        check(f"{legacy} -> :443", nl.endswith(":443"), nl)
        jcfg = await vless_mod.generate_vless_json(UID, remark="L", extra={"transport": legacy})
        check(f"{legacy} json network=ws", jcfg["outbounds"][0]["streamSettings"]["network"] == "ws", jcfg["outbounds"][0]["streamSettings"])

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
