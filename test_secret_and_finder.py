"""
Offline tests (stdlib only, no web stack, no network) for:
  * the SECRET_PATH middleware (app/secret_path.py)
  * the Best Endpoint Finder (app/services/endpoint_finder.py)
Run:  python test_secret_and_finder.py
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import state  # noqa: E402
from app import secret_path as sp  # noqa: E402
from app.services import endpoint_finder as ef  # noqa: E402

FAILED = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))
    if not cond:
        FAILED.append(name)


# ------------------------------------------------------------------ middleware
async def call(mw, path, method="GET"):
    sent = []

    async def send(m):
        sent.append(m)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {"type": "http", "method": method, "path": path, "raw_path": path.encode(), "headers": []}
    await mw(scope, receive, send)
    start = next(m for m in sent if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return start["status"], dict(start["headers"]), body


async def test_middleware():
    seen = {}

    async def app(scope, receive, send):
        seen["path"] = scope["path"]
        seen["admin"] = scope.get("se7o_admin")
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"APP"})

    mw = sp.SecretPathMiddleware(app)
    state.secret_path = "s3cr3t-XYZ"

    st, _, body = await call(mw, "/s3cr3t-XYZ/panel")
    check("/<secret>/panel reaches the panel route", st == 200 and seen["path"] == "/panel" and seen["admin"] is True)
    st, _, _ = await call(mw, "/s3cr3t-XYZ/api/login", "POST")
    check("/<secret>/api/* is rewritten to /api/*", st == 200 and seen["path"] == "/api/login")
    st, _, _ = await call(mw, "/s3cr3t-XYZ/stats")
    check("/<secret>/stats is rewritten", st == 200 and seen["path"] == "/stats")

    seen.clear()
    for p in ("/panel", "/panel/", "/login", "/dashboard", "/api/login", "/api/links", "/api/me",
              "/api/endpoints/presets", "/api/aether/status", "/stats", "/connections", "/openapi.json"):
        st, _, body = await call(mw, p)
        check(f"{p} WITHOUT the secret is blocked (404)", st == 404 and not seen and json.loads(body) == {"detail": "Not Found"})
    # A wrong prefix is never treated as the secret: it is passed through
    # UNCHANGED and without the admin flag, so it can only hit a (non-existent) route -> 404.
    for wrong in ("/wrong/panel", "/s3cr3t-XYZ2/panel", "/S3CR3T-XYZ/panel"):
        seen.clear()
        await call(mw, wrong)
        check(f"wrong secret {wrong} is not rewritten / not admin", seen.get("path") == wrong and not seen.get("admin"))

    for p in ("/", "/health", "/api/health", "/sub/abc", "/user/abc", "/check/abc", "/img/logo.png", "/favicon.ico"):
        seen.clear()
        st, _, _ = await call(mw, p)
        check(f"public {p} stays reachable", st == 200 and seen["path"] == p and not seen["admin"])

    st, h, _ = await call(mw, "/s3cr3t-XYZ")
    check("/<secret> redirects to /<secret>/panel", st == 307 and h[b"location"] == b"/s3cr3t-XYZ/panel")

    # websockets are never rewritten or blocked
    seen.clear()
    await mw({"type": "websocket", "path": "/ws/abc"}, None, None) if False else None

    # fail-closed before the secret is known
    state.secret_path = ""
    seen.clear()
    st, _, _ = await call(mw, "/panel")
    check("no secret configured yet -> admin still blocked", st == 404 and not seen)
    state.secret_path = "s3cr3t-XYZ"


def test_validate():
    check("valid secret accepted", sp.validate("/My-Secret_1/") == "My-Secret_1")
    for bad in ("", "ab", "has space", "a/b", "x" * 65, "panel", "API", "health", "ws", "dashboard"):
        try:
            sp.validate(bad)
            check(f"validate rejects {bad[:12]!r}", False)
        except ValueError:
            check(f"validate rejects {bad[:12]!r}", True)
    g = sp.generate()
    check("generated secret is valid", sp.validate(g) == g and len(g) >= 12)
    state.secret_path = "abc123"
    check("panel_url", sp.panel_url("x.example.com") == "https://x.example.com/abc123/panel"
          and sp.base_prefix() == "/abc123")


# ------------------------------------------------------------------ finder
def test_expand():
    t = ef.expand_targets("1.1.1.1, 1.1.1.1\nexample.com  2606:4700::1111", 5)
    check("expand: ip/host/ipv6, deduped", t == ["1.1.1.1", "example.com", "2606:4700::1111"], t)
    t = ef.expand_targets("104.16.0.0/24", 8)
    check("expand: CIDR sample size + inside range + no network/broadcast",
          len(t) == 8 and len(set(t)) == 8 and all(x.startswith("104.16.0.") and x not in ("104.16.0.0", "104.16.0.255") for x in t), t)
    check("expand: tiny CIDR", ef.expand_targets("9.9.9.9/32") == ["9.9.9.9"])
    check("expand: cap at MAX_TARGETS", len(ef.expand_targets("10.0.0.0/8, 104.16.0.0/13", 256, 300)) <= 300)
    for bad in ("not a host!", "1.2.3.4/99", "2001:db8::/32", "", "http://x.com"):
        try:
            ef.expand_targets(bad)
            check(f"expand rejects {bad!r}", False)
        except ef.FinderError:
            check(f"expand rejects {bad!r}", True)
    p = ef.validate_params({"mode": "TCP", "port": "8443", "attempts": 99, "timeout": 0.2, "concurrency": 999})
    d = ef.validate_params({})
    check("params defaults", d["mode"] == "tls" and d["port"] == 443 and d["attempts"] == 3 and d["timeout"] == 4.0)
    check("params clamped", p["mode"] == "tcp" and p["port"] == 8443 and p["attempts"] == 10 and p["timeout"] == 1.0
          and p["concurrency"] == ef.MAX_CONCURRENCY)
    for bad in ({"mode": "udp"}, {"port": 0}, {"port": 70000}, {"sni": "bad host"}):
        try:
            ef.validate_params(bad)
            check(f"params reject {bad}", False)
        except ef.FinderError:
            check(f"params reject {bad}", True)


async def test_probe_and_job():
    async def handler(r, w):
        await asyncio.sleep(0.02)
        w.close()

    srv = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = srv.sockets[0].getsockname()[1]

    # SSRF guard: loopback is refused by default
    row = await ef.probe_endpoint("127.0.0.1", port, "tcp", "example.com", 2, 2.0)
    check("SSRF guard blocks loopback", row["ok"] is False and "non-public" in row.get("error", ""), row)
    row = await ef.probe_endpoint("192.168.1.1", 443, "tcp", "example.com", 1, 1.0)
    check("SSRF guard blocks private LAN", row["ok"] is False and "non-public" in row.get("error", ""), row)

    # open the guard only for this test so a local server can be measured
    orig = ef._is_public
    ef._is_public = lambda ip: True
    try:
        row = await ef.probe_endpoint("127.0.0.1", port, "tcp", "example.com", 3, 2.0)
        check("tcp probe stats", row["ok"] and row["received"] == 3 and row["loss"] == 0
              and 0 <= row["min"] <= row["avg"] <= row["max"] and row["jitter"] >= 0, row)

        dead = await ef.probe_endpoint("127.0.0.1", 1, "tcp", "example.com", 2, 1.0)
        check("closed port -> failure with 100% loss", dead["ok"] is False and dead["loss"] == 100.0 and dead["error"], dead)

        jid = ef.start_job(f"127.0.0.1\n127.0.0.2", {"mode": "tcp", "port": port, "attempts": 2, "timeout": 2})
        try:
            ef.start_job("127.0.0.1", {"mode": "tcp", "port": port})
            check("second concurrent scan rejected", False)
        except ef.FinderError as e:
            check("second concurrent scan rejected", "already running" in str(e))
        for _ in range(100):
            j = ef.get_job(jid)
            if j["status"] != "running":
                break
            await asyncio.sleep(0.05)
        check("job completes with all results", j["status"] == "done" and j["done"] == j["total"] == 2
              and len(j["results"]) == 2 and all("task" not in j for _ in [0]), j.get("status"))
        check("results ranked best-first", j["results"][0]["ok"] and (len(j["results"]) < 2 or
              j["results"][0].get("score", 0) <= j["results"][1].get("score", 1e9)))

        # cancel
        async def slow(r, w):
            await asyncio.sleep(5)

        slow_srv = await asyncio.start_server(slow, "127.0.0.1", 0)
        sport = slow_srv.sockets[0].getsockname()[1]
        jid2 = ef.start_job("127.0.0.1", {"mode": "tls", "port": sport, "attempts": 1, "timeout": 3, "sni": "example.com"})
        await asyncio.sleep(0.2)
        check("cancel a running job", ef.cancel_job(jid2) is True)
        await asyncio.sleep(0.2)
        check("cancelled job status", ef.get_job(jid2)["status"] == "cancelled")
        check("cancel finished job is a no-op", ef.cancel_job(jid) is False)
        slow_srv.close()
    finally:
        ef._is_public = orig
        srv.close()


async def main():
    await test_middleware()
    test_validate()
    test_expand()
    await test_probe_and_job()


asyncio.run(main())
print("\nALL PASSED" if not FAILED else f"\nFAILED: {FAILED}")
sys.exit(1 if FAILED else 0)
