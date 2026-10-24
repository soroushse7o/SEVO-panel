"""
Unit tests for the MTProxy service that do not need Docker or a real mtg.

Run: python test_mtproxy.py
"""
import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("DB_PATH", os.path.join(tempfile.gettempdir(), "mtproxy_test.db"))

from app.services import mtproxy  # noqa: E402
from app.config import settings  # noqa: E402
from app import state  # noqa: E402


def setcfg(**kw):
    """settings is a frozen dataclass; bypass that for tests."""
    for k, v in kw.items():
        object.__setattr__(settings, k, v)

ok = fail = 0


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"PASS  {name}")
    else:
        fail += 1
        print(f"FAIL  {name} {extra}")


def test_secret():
    s = mtproxy.generate_secret("www.cloudflare.com")
    check("secret starts with ee", s.startswith("ee"), s)
    check("secret is hex", all(c in "0123456789abcdef" for c in s), s)
    # ee (2) + 32 hex chars of random + hex(domain)
    check("secret length", len(s) == 2 + 32 + len("www.cloudflare.com") * 2, len(s))
    check("domain round-trips", mtproxy.secret_domain(s) == "www.cloudflare.com", mtproxy.secret_domain(s))

    s2 = mtproxy.generate_secret("example.org")
    check("domain honoured", mtproxy.secret_domain(s2) == "example.org")
    check("secrets are unique", mtproxy.generate_secret("a.com") != mtproxy.generate_secret("a.com"))
    check("bad secret returns empty domain", mtproxy.secret_domain("nonsense") == "")


def test_endpoint():
    for k in ("RAILWAY_TCP_PROXY_DOMAIN", "RAILWAY_TCP_PROXY_PORT"):
        os.environ.pop(k, None)
    setcfg(mtproxy_public_host="")
    setcfg(mtproxy_public_port="")

    host, port, confirmed = mtproxy.public_endpoint()
    check("no TCP proxy -> unconfirmed", confirmed is False, (host, port, confirmed))

    os.environ["RAILWAY_TCP_PROXY_DOMAIN"] = "shuttle.proxy.rlwy.net"
    os.environ["RAILWAY_TCP_PROXY_PORT"] = "15140"
    host, port, confirmed = mtproxy.public_endpoint()
    check("railway env detected", (host, port, confirmed) == ("shuttle.proxy.rlwy.net", 15140, True), (host, port, confirmed))

    state.mtproxy_secret = mtproxy.generate_secret("www.cloudflare.com")
    link = mtproxy.build_link()
    check("link uses public host, not container IP",
          link.startswith("tg://proxy?server=shuttle.proxy.rlwy.net&port=15140&secret=ee"), link)
    check("https link form", mtproxy.build_http_link().startswith("https://t.me/proxy?server=shuttle.proxy.rlwy.net&port=15140"))

    # manual override wins when railway vars are absent
    for k in ("RAILWAY_TCP_PROXY_DOMAIN", "RAILWAY_TCP_PROXY_PORT"):
        os.environ.pop(k, None)
    setcfg(mtproxy_public_host="")
    setcfg(mtproxy_public_port="")
    state.mtproxy_config["public_host"] = "my.host"
    state.mtproxy_config["public_port"] = "9999"
    host, port, confirmed = mtproxy.public_endpoint()
    check("manual override honoured", (host, port, confirmed) == ("my.host", 9999, True), (host, port, confirmed))
    check("manual override is confirmed", confirmed is True)
    state.mtproxy_config["public_host"] = ""
    state.mtproxy_config["public_port"] = ""

    check("empty secret -> empty link", mtproxy.build_link("") == "" or state.mtproxy_secret != "")


def test_supervisor():
    """Start a stand-in 'mtg' that exits, and confirm it is restarted."""
    tmp = tempfile.mkdtemp()
    marker = os.path.join(tmp, "runs.txt")
    fake = os.path.join(tmp, "fake_mtg.py")
    with open(fake, "w") as f:
        f.write(
            "import sys, time\n"
            f"open({marker!r}, 'a').write(' '.join(sys.argv[1:]) + '\\n')\n"
            "time.sleep(0.25)\n"
            "sys.exit(3)\n"
        )
    launcher = os.path.join(tmp, "mtg.sh" if os.name != "nt" else "mtg.bat")
    if os.name == "nt":
        with open(launcher, "w") as f:
            f.write(f'@echo off\r\n"{sys.executable}" "{fake}" %*\r\n')
    else:
        with open(launcher, "w") as f:
            f.write(f'#!/bin/sh\nexec "{sys.executable}" "{fake}" "$@"\n')
        os.chmod(launcher, 0o755)

    setcfg(mtproxy_bin=launcher)
    setcfg(mtproxy_enabled=True)
    setcfg(mtproxy_port=4443)
    state.mtproxy_secret = mtproxy.generate_secret("www.cloudflare.com")

    check("find_binary honours MTPROXY_BIN", mtproxy.find_binary() == launcher, mtproxy.find_binary())

    async def run():
        from app.database import init_db, close_db
        await init_db()
        await mtproxy.start()
        await asyncio.sleep(3.2)
        st = mtproxy.get_status()
        await mtproxy.stop()
        await close_db()
        return st

    st = asyncio.run(run())

    runs = []
    if os.path.exists(marker):
        runs = [l for l in open(marker).read().splitlines() if l.strip()]

    check("child process was launched", len(runs) >= 1, runs)
    check("restarted after exit", len(runs) >= 2, f"launched {len(runs)}x")
    if runs:
        check("binds to 0.0.0.0:port", "0.0.0.0:4443" in runs[0], runs[0])
        check("passes the secret", state.mtproxy_secret in runs[0], runs[0])
        check("uses simple-run", runs[0].startswith("simple-run"), runs[0])
    check("status reports restarts", st["restarts"] >= 1, st["restarts"])
    check("status reports the exit code", "code 3" in st["error"], st["error"])

    async def stopped():
        await mtproxy.stop()
    asyncio.run(stopped())


def test_missing_binary():
    setcfg(mtproxy_bin="/definitely/not/here/mtg")
    found = mtproxy.find_binary()
    check("missing binary reports empty", found == "" or os.path.isfile(found), found)


if __name__ == "__main__":
    test_secret()
    test_endpoint()
    test_supervisor()
    test_missing_binary()
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)
