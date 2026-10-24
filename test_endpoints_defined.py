"""
Verify every transport endpoint the CLIENT links point at is actually
registered on the FastAPI app. This proves the server can serve all four
transports (no silent 404s). Lightweight: no live relay, just route table.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app.config as config
class _S:
    domain = "127.0.0.1"
    secret_key = "x" * 32
    raw_tcp_enabled = False
    raw_tcp_public_host = ""
    raw_tcp_public_port = ""
    xhttp_enabled = True
    link_cache_ttl = 0
    environment = "test"
    database_url = ""
    session_cookie = "x"

config.settings = _S()

import main

app = main.create_app()

# Collect all registered routes (path + methods / websocket)
routes = {}
for r in app.routes:
    path = getattr(r, "path", None)
    if path is None:
        continue
    if getattr(r, "endpoint", None) is not None and hasattr(r, "methods"):
        methods = sorted(getattr(r, "methods", []) or [])
    else:
        # WebSocket route
        methods = {"WS"}
    routes.setdefault(path, set()).update(methods)

EXPECTED = {
    "/ws/{uuid}": {"WS"},
    "/xhttp1/{uuid}": {"POST"},
    "/http/{uuid}": {"POST"},
    "/api/aether/status": {"GET"},
    "/api/aether/start": {"POST"},
    "/api/aether/stop": {"POST"},
    "/api/aether/restart": {"POST"},
    "/api/aether/install": {"POST"},
    "/api/aether/settings": {"POST"},
}

print("=== Registered transport routes ===")
for p in EXPECTED:
    methods = routes.get(p, set())
    print(f"  {p:20s} -> {sorted(methods)}")

ok = True
for p, want in EXPECTED.items():
    have = routes.get(p, set())
    if want.issubset(have):
        print(f"  OK   {p}")
    else:
        ok = False
        print(f"  FAIL {p} (want {want}, have {have})")

print("\n=== ENDPOINT AUDIT ===")
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
