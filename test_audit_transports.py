"""
Audit test: verify the link/json a CLIENT receives exactly matches the
SERVER endpoints that tunnel.py actually serves. No live server needed.
"""
import asyncio
import sys
import os
import re

# Make the panel package importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Stub settings before importing vless (vless reads settings.domain etc.)
import app.config as config

class _FakeSettings:
    domain = "panel.example.com"
    secret_key = "test"
    link_cache_ttl = 0

config.settings = _FakeSettings()

import app.vless as vless
from app.vless import generate_vless_link, generate_vless_json


def extract_path_from_uri(uri):
    # vless://uuid@host:port?params#remark  -> find type= and path=
    m = re.search(r"[?&]path=([^&#]+)", uri)
    path = None
    if m:
        from urllib.parse import unquote
        path = unquote(m.group(1))
    t = re.search(r"[?&]type=([^&#]+)", uri)
    typ = t.group(1) if t else "ws"
    return typ, path


async def main():
    uid = "11111111-2222-3333-4444-555555555555"
    results = []
    for transport in ("ws",):
        extra = {"transport": transport}
        uri = await generate_vless_link(uid, remark="T", extra=extra)
        jcfg = await generate_vless_json(uid, remark="T", extra=extra)
        results.append((transport, uri, jcfg))

    print("=== GENERATED LINKS / JSON (client side) ===")
    server_endpoints = {
        "ws": "/ws/{uuid}",
    }
    ok = True
    for transport, uri, jcfg in results:
        print(f"\n--- {transport} ---")
        print("URI :", uri)
        typ, path = extract_path_from_uri(uri)
        # JSON path
        ss = jcfg["outbounds"][0]["streamSettings"]
        net = ss["network"]
        if net == "ws":
            jpath = ss["wsSettings"]["path"]
        else:
            jpath = None
        # Compare URI path vs server endpoint
        exp = server_endpoints[transport]
        # replace {uuid} with the actual uid
        exp_path = exp.replace("{uuid}", uid)
        print(f"  uri type={typ} path={path}")
        print(f"  json path={jpath}")
        print(f"  server expects path={exp_path}")
        if path != exp_path:
            ok = False; print(f"  FAIL: uri path {path} != server {exp_path}")
        if jpath != exp_path:
            ok = False; print(f"  FAIL: json path {jpath} != server {exp_path}")
        if typ != transport:
            ok = False; print(f"  FAIL: uri type {typ} != {transport}")

    print("\n=== AUDIT RESULT ===")
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
