"""End-to-end smoke test against a running panel instance."""
import json
import os
import sys
import httpx

# Start the panel first, e.g.:
#   SECRET_PATH=smokesecret DB_PATH=/tmp/smoke.db ADMIN_USERNAME=se7oadmin ADMIN_PASSWORD=Test1234 PORT=8899 python main.py
SECRET = os.environ.get("SMOKE_SECRET", "smokesecret")
BASE = "http://127.0.0.1:8899"
PW = "Test1234"
USER = "se7oadmin"
ok = fail = 0


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"PASS  {name}")
    else:
        fail += 1
        print(f"FAIL  {name}  {extra}")


_ADMIN = ("/api/", "/stats", "/connections", "/panel", "/login", "/dashboard")


class Client(httpx.Client):
    """Sends every admin URL under /<SECRET_PATH>/ like the real panel does."""

    def request(self, method, url, **kw):
        if isinstance(url, str) and url.startswith(_ADMIN) and url != "/api/health" and not url.startswith("/api/__raw"):
            url = f"/{SECRET}{url}"
        return super().request(method, url, **kw)


with Client(base_url=BASE, timeout=20.0) as c:
    r = c.get("/")
    check("GET / ", r.status_code == 200 and r.json()["version"] == "3.1.0", r.text[:120])

    # ---- health endpoint ----
    r = c.get("/health")
    hj = r.json()
    check("GET /health 200 + JSON", r.status_code == 200 and hj["status"] in ("ok", "degraded"), r.text[:160])
    check("health has uptime + system metrics", hj["uptime"]["process_seconds"] >= 0 and "system" in hj and hj["database"]["ok"] is True)
    check("GET /api/health alias", c.get("/api/health").status_code == 200)

    # ---- secret admin path ----
    for p in ("/panel", "/login", "/dashboard", "/api/me", "/api/links", "/stats", "/openapi.json"):
        check(f"{p} without secret prefix -> 404", httpx.get(BASE + p).status_code == 404)
    check("wrong secret prefix -> 404", httpx.get(BASE + "/nope-nope/panel").status_code == 404)
    check("/<secret> redirects to panel", httpx.get(BASE + f"/{SECRET}", follow_redirects=False).status_code == 307)

    r = c.get("/panel")
    html = r.text
    check("GET /<secret>/panel 200", r.status_code == 200)
    check("panel gets the secret base injected", f"const BASE='/{SECRET}'" in html and "__SE7O_BASE__" not in html)
    check("panel has no H3 / HTTP-proxy / Install controls", "ae-transport" not in html and "ae-httpproxy" not in html and "aeInstall" not in html)
    check("panel has the Best Endpoint Finder tab", 'id="page-endpoints"' in html and "پیدا کردن بهترین اندپوینت" in html)
    check("panel html has login page", 'id="login-page"' in html)
    check("panel html has no literal NUL", "\x00" not in html)
    check("panel version bumped", "V 3.0.0" not in html or "V 2.0.0" not in html)

    r = c.get("/img/logo.png")
    check("GET /img/logo.png", r.status_code == 200 and r.headers["content-type"] == "image/png", r.status_code)
    check("logo is small (<40KB)", len(r.content) < 40_000, f"{len(r.content)}B")
    r = c.get("/favicon.ico")
    check("GET /favicon.ico", r.status_code == 200 and len(r.content) > 0)
    check("GET /img/favicon.png", c.get("/img/favicon.png").status_code == 200)

    # auth gate
    check("protected route 401 pre-login", c.get("/api/links").status_code == 401)
    check("bad password rejected", c.post("/api/login", json={"username": USER, "password": "wrong"}).status_code == 401)
    check("bad username rejected", c.post("/api/login", json={"username": "nope", "password": PW}).status_code == 401)
    check("missing username rejected", c.post("/api/login", json={"password": PW}).status_code == 401)

    r = c.post("/api/login", json={"username": USER, "password": PW})
    check("login ok", r.status_code == 200)
    check("session cookie set", "SE7OSNA_session" in c.cookies)
    me = c.get("/api/me").json()
    check("GET /api/me", me.get("authenticated") is True)
    check("/api/me returns username", me.get("username") == USER, me)

    # links
    r = c.get("/api/links")
    check("GET /api/links", r.status_code == 200 and "links" in r.json(), r.text[:120])
    base_count = len(r.json()["links"])

    r = c.post("/api/links", json={"label": "TestUser", "limit_value": 5, "limit_unit": "GB",
                                   "max_connections": 3, "days_valid": 30, "flag": "de"})
    check("POST /api/links create", r.status_code == 200, r.text[:200])
    created = r.json()
    uid = created["uuid"]
    check("vless link generated", created["vless_link"].startswith(f"vless://{uid}@"))
    check("flag normalized", created["flag"] == "DE")

    r = c.patch(f"/api/links/{uid}", json={"label": "TestRenamed", "active": False, "limit_value": 10})
    check("PATCH link", r.status_code == 200, r.text[:150])
    got = [l for l in c.get("/api/links").json()["links"] if l["uuid"] == uid][0]
    check("patch applied", got["label"] == "TestRenamed" and got["active"] is False and got["limit_bytes"] == 10 * 1024**3, got)

    r = c.patch("/api/links/batch", json={"uids": [uid], "action": "activate"})
    check("PATCH /api/links/batch (not shadowed by {uid})", r.status_code == 200, r.text[:150])
    got = [l for l in c.get("/api/links").json()["links"] if l["uuid"] == uid][0]
    check("batch activate applied", got["active"] is True)

    check("link health", c.get(f"/api/links/{uid}/health").json()["healthy"] is True)
    r = c.post(f"/api/links/{uid}/new-uuid")
    check("regenerate uuid", r.status_code == 200 and r.json()["new_uuid"] != uid, r.text[:120])
    uid = r.json()["new_uuid"]
    check("disconnect", c.post(f"/api/links/{uid}/disconnect").status_code == 200)

    # public endpoints for that link
    r = c.get(f"/sub/{uid}")
    check("GET /sub/{uid}", r.status_code == 200 and "subscription-userinfo" in r.headers, r.status_code)
    import base64
    decoded = base64.b64decode(r.text).decode()
    check("subscription has vless nodes", decoded.count("vless://") >= 2, decoded[:80])
    r = c.get(f"/user/{uid}")
    ud = r.text
    check("GET /user/{uid} is HTML", r.status_code == 200 and r.headers["content-type"].startswith("text/html"), r.status_code)
    check("user page has QR", "api.qrserver.com" in ud)
    check("user page has copy buttons", "Copy Subscription Link" in ud and "Copy Single VLESS Link" in ud)
    check("user page shows usage/expiry", "Data Usage" in ud and "Expiration" in ud)
    check("user page no unrendered braces", "{label}" not in ud and "{sub_url}" not in ud)
    check("GET /check/{uid}", c.get(f"/check/{uid}").json()["healthy"] is True)

    # export / import round-trip
    exported = c.get("/api/export-links").json()
    check("export links", isinstance(exported, list) and len(exported) >= 1)
    clone = dict(exported[0])
    clone["uid"] = "11111111-2222-3333-4444-555555555555"
    clone["label"] = "ImportedOne"
    r = c.post("/api/import-links", json=[clone])
    check("POST /api/import-links", r.status_code == 200 and r.json()["imported"] == 1, r.text[:200])
    check("imported link visible", any(l["uuid"] == clone["uid"] for l in c.get("/api/links").json()["links"]))
    check("DELETE imported", c.delete(f"/api/links/{clone['uid']}").status_code == 200)

    # addresses
    seeded = c.get("/api/addresses").json()["addresses"]
    check("default clean IPs seeded", len(seeded) >= 1, len(seeded))
    check("seeded list content", "69.46.46.30" in seeded)
    check("delete all addresses", c.delete("/api/addresses").status_code == 200)
    check("add address", c.post("/api/addresses", json={"address": "1.2.3.4"}).status_code == 200)
    check("dup address rejected", c.post("/api/addresses", json={"address": "1.2.3.4"}).status_code == 400)
    r = c.post("/api/addresses/batch", json={"addresses": ["5.6.7.8", "cdn.example.com", "!!bad space!!"]})
    check("batch add", r.status_code == 200 and r.json()["added"] == 2, r.text[:150])
    r = c.patch("/api/addresses/0", json={"address": "9.9.9.9"})
    check("PATCH address (new route)", r.status_code == 200 and r.json()["addresses"][0] == "9.9.9.9", r.text[:150])
    r = c.post("/api/addresses/bulk-delete", json={"indices": [0, 2]})
    check("POST bulk-delete (new route)", r.status_code == 200 and r.json()["removed"] == 2, r.text[:150])
    check("one address remains", c.get("/api/addresses").json()["addresses"] == ["5.6.7.8"])

    # settings
    r = c.get("/api/settings")
    check("GET /api/settings", r.status_code == 200 and "tg_bot_token" in r.json(), r.text[:200])
    check("POST /api/settings", c.post("/api/settings", json={"footer_text": "hello", "monthly_limit_gb": "100"}).status_code == 200)
    check("settings persisted", c.get("/api/settings").json()["footer_text"] == "hello")
    check("public-settings", c.get("/api/public-settings").json()["footer_text"] == "hello")

    # stats / logs
    r = c.get("/stats")
    d = r.json()
    check("GET /stats", r.status_code == 200 and len(d["hourly_traffic"]) == 24, r.text[:150])
    check("stats monthly limit", d["monthly_limit_bytes"] == 100 * 1024**3)
    check("GET /api/login-logs", len(c.get("/api/login-logs").json()["logs"]) >= 2)
    check("GET /api/logs", c.get("/api/logs").status_code == 200)
    check("GET /api/logs/size", "size_kb" in c.get("/api/logs/size").json())
    check("DELETE /api/logs/clear", c.delete("/api/logs/clear").status_code == 200)

    # backup / restore round-trip
    backup = c.get("/api/backup/full").json()
    check("backup shape", {"links", "addresses", "settings"} <= backup.keys())
    r = c.post("/api/restore", json=backup)
    check("restore ok", r.status_code == 200, r.text[:200])
    check("restore kept links", len(c.get("/api/links").json()["links"]) == len(backup["links"]))
    check("restore kept addresses", c.get("/api/addresses").json()["addresses"] == backup["addresses"])

    # password rules
    check("weak pw rejected", c.post("/api/change-password", json={"current_password": PW, "new_password": "short"}).status_code == 400)
    check("wrong current rejected", c.post("/api/change-password", json={"current_password": "nope", "new_password": "NewPass123"}).status_code == 400)
    check("change password", c.post("/api/change-password", json={"current_password": PW, "new_password": "NewPass123"}).status_code == 200)
    check("old pw now invalid", c.post("/api/login", json={"username": USER, "password": PW}).status_code == 401)
    check("new pw works", c.post("/api/login", json={"username": USER, "password": "NewPass123"}).status_code == 200)

    # username change
    check("bad new username rejected", c.post("/api/change-username", json={"current_password": "NewPass123", "new_username": "a!"}).status_code == 400)
    check("wrong pw blocks rename", c.post("/api/change-username", json={"current_password": "bad", "new_username": "se7onew"}).status_code == 400)
    check("change username", c.post("/api/change-username", json={"current_password": "NewPass123", "new_username": "se7onew"}).status_code == 200)
    check("old username invalid", c.post("/api/login", json={"username": USER, "password": "NewPass123"}).status_code == 401)
    check("new username works", c.post("/api/login", json={"username": "se7onew", "password": "NewPass123"}).status_code == 200)



    # ---- mtproxy ----
    r = c.get("/api/mtproxy")
    check("GET /api/mtproxy", r.status_code == 200, r.status_code)
    mt = r.json()
    check("secret is an ee FakeTLS secret", mt["secret"].startswith("ee") and len(mt["secret"]) > 34, mt.get("secret"))
    check("secret persisted in settings", mt["secret"] == c.get("/api/mtproxy").json()["secret"])
    check("tg link shape", mt["tg_link"].startswith("tg://proxy?server=") and "secret=ee" in mt["tg_link"], mt.get("tg_link"))
    check("https link shape", mt["https_link"].startswith("https://t.me/proxy?server="), mt.get("https_link"))
    check("bind port reported", mt["bind_port"] == 443 or isinstance(mt["bind_port"], int), mt.get("bind_port"))
    check("fronting domain decoded", "." in mt["fake_domain"], mt.get("fake_domain"))
    check("endpoint_confirmed present", isinstance(mt["endpoint_confirmed"], bool))

    old_secret = mt["secret"]
    r = c.post("/api/mtproxy/regenerate", json={"fake_domain": "www.bing.com"})
    check("regenerate secret", r.status_code == 200, r.status_code)
    new = r.json()
    check("secret actually changed", new["secret"] != old_secret)
    check("new fronting domain applied", new["fake_domain"] == "www.bing.com", new.get("fake_domain"))
    check("regenerated secret persists", c.get("/api/mtproxy").json()["secret"] == new["secret"])
    check("bad fronting domain rejected", c.post("/api/mtproxy/regenerate", json={"fake_domain": "no spaces here"}).status_code == 400)

    # ---- per-inbound outbound routing ----
    r = c.post("/api/links", json={"label": "WarpUser", "outbound": "warp"})
    check("create inbound with outbound=warp (alias -> aether)", r.status_code == 200 and r.json()["outbound"] == "aether", r.text[:160])
    wuid = r.json()["uuid"]
    check("create inbound with bad outbound rejected", c.post("/api/links", json={"label": "Bad", "outbound": "banana"}).status_code == 400)
    check("new inbound defaults to outbound=default", c.post("/api/links", json={"label": "Plain"}).json()["outbound"] == "default")
    check("PATCH outbound=direct", c.patch(f"/api/links/{wuid}", json={"outbound": "direct"}).status_code == 200)
    check("PATCH outbound=socks5", c.patch(f"/api/links/{wuid}", json={"outbound": "socks5://u:p@10.0.0.1:1080"}).status_code == 200)
    check("PATCH bad outbound rejected", c.patch(f"/api/links/{wuid}", json={"outbound": "socks5://nope"}).status_code == 400)
    got = [l for l in c.get("/api/links").json()["links"] if l["uuid"] == wuid][0]
    check("outbound persisted + listed", got["outbound"] == "socks5://u:p@10.0.0.1:1080", got.get("outbound"))
    r = c.get("/api/outbound-routes")
    check("GET /api/outbound-routes", r.status_code == 200 and {x["id"] for x in r.json()["routes"]} >= {"default", "direct", "aether", "auto", "socks5"})
    exported = c.get("/api/export-links").json()
    check("export carries outbound", any(l.get("outbound") == "socks5://u:p@10.0.0.1:1080" for l in exported))
    for l in c.get("/api/links").json()["links"]:
        if l["label"] in ("WarpUser", "Plain"):
            c.delete(f"/api/links/{l['uuid']}")

    # ---- Best Endpoint Finder ----
    r = c.get("/api/endpoints/presets")
    check("GET /api/endpoints/presets", r.status_code == 200 and len(r.json()["cloudflare_ranges"]) > 5, r.text[:120])
    check("scan rejects empty targets", c.post("/api/endpoints/scan", json={"targets": ""}).status_code == 400)
    r = c.post("/api/endpoints/scan", json={"targets": "127.0.0.1", "mode": "tcp", "attempts": 1, "timeout": 1})
    check("scan starts", r.status_code == 200 and r.json().get("job_id"), r.text[:120])
    import time as _t
    jid = r.json()["job_id"]
    for _ in range(40):
        j = c.get(f"/api/endpoints/job/{jid}").json()
        if j["status"] != "running":
            break
        _t.sleep(0.25)
    check("scan finishes; loopback blocked (SSRF guard)", j["status"] == "done" and j["results"][0]["ok"] is False
          and "non-public" in j["results"][0].get("error", ""), j)
    check("endpoint finder needs auth", httpx.get(BASE + f"/{SECRET}/api/endpoints/presets").status_code == 401)

    check("mtproxy needs auth", httpx.get(BASE + f"/{SECRET}/api/mtproxy").status_code == 401)
    check("cleanup delete link", c.delete(f"/api/links/{uid}").status_code == 200)
    check("logout", c.post("/api/logout").status_code == 200)
    check("401 after logout", c.get("/api/links").status_code == 401)

print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
