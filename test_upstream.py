"""
Offline tests for the Aether outbound integration (no web stack, no network):

  * upstream.socks5_connect / open_upstream against a fake SOCKS5 server
    (domain, IPv4, IPv6 targets, refusal, fail-closed mode, auto fallback)
  * aether.parse_options / build_args / parse_line / backoff
  * aether process lifecycle with a fake "aether" binary: start -> connected
    -> kill -> watchdog restart, then stop
Run:  python test_upstream.py
"""
import asyncio
import os
import stat
import sys
import tempfile
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services import upstream, aether  # noqa: E402

FAILED = []


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))
    if not cond:
        FAILED.append(name)


# ---------------------------------------------------------------- fake SOCKS5
class FakeSocks:
    """Minimal SOCKS5 server: records requested targets, echoes bytes back."""

    def __init__(self, refuse_code=0):
        self.requests = []
        self.refuse_code = refuse_code
        self.server = None
        self.port = 0

    async def _handle(self, r, w):
        try:
            ver, n = await r.readexactly(2)
            await r.readexactly(n)
            w.write(b"\x05\x00")
            hdr = await r.readexactly(4)
            atyp = hdr[3]
            if atyp == 1:
                host = ".".join(map(str, await r.readexactly(4)))
            elif atyp == 4:
                import ipaddress
                host = str(ipaddress.IPv6Address(await r.readexactly(16)))
            else:
                ln = (await r.readexactly(1))[0]
                host = (await r.readexactly(ln)).decode()
            port = int.from_bytes(await r.readexactly(2), "big")
            self.requests.append((atyp, host, port))
            w.write(bytes([5, self.refuse_code, 0, 1]) + b"\x00\x00\x00\x00\x00\x00")
            await w.drain()
            if self.refuse_code:
                return
            while True:
                data = await r.read(4096)
                if not data:
                    break
                w.write(data)
                await w.drain()
        except Exception:
            pass
        finally:
            w.close()

    async def start(self):
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self

    async def close(self):
        self.server.close()
        await self.server.wait_closed()


async def test_socks():
    fs = await FakeSocks().start()
    for host, atyp in (("example.com", 3), ("93.184.216.34", 1), ("2606:2800:220:1:248:1893:25c8:1946", 4)):
        r, w = await upstream.socks5_connect(host, 443, "127.0.0.1", fs.port, timeout=3)
        w.write(b"ping")
        await w.drain()
        echo = await asyncio.wait_for(r.readexactly(4), 3)
        w.close()
        got = fs.requests[-1]
        check(f"socks5 CONNECT {host}", echo == b"ping" and got[0] == atyp and got[2] == 443 and got[1] == host, got)
    await fs.close()

    fs = await FakeSocks(refuse_code=5).start()
    try:
        await upstream.socks5_connect("example.com", 80, "127.0.0.1", fs.port, timeout=3)
        check("socks5 refusal raises", False)
    except upstream.UpstreamError as e:
        check("socks5 refusal raises UpstreamError", "code 5" in str(e), str(e))
    await fs.close()


async def test_modes():
    # a real "destination" so direct mode has something to connect to
    async def dest(r, w):
        w.write(b"direct-hello")
        await w.drain()
        w.close()

    dsrv = await asyncio.start_server(dest, "127.0.0.1", 0)
    dport = dsrv.sockets[0].getsockname()[1]
    fs = await FakeSocks().start()
    ready = {"v": False}
    upstream.configure(mode="direct", socks_port=fs.port, ready=lambda: ready["v"])

    r, w = await upstream.open_upstream("127.0.0.1", dport)
    check("direct mode connects directly", await r.readexactly(12) == b"direct-hello" and not fs.requests)
    w.close()

    upstream.configure(mode="aether")
    try:
        await upstream.open_upstream("127.0.0.1", dport)
        check("aether mode is fail-closed when tunnel is down", False)
    except upstream.UpstreamError:
        check("aether mode is fail-closed when tunnel is down", not fs.requests)

    ready["v"] = True
    r, w = await upstream.open_upstream("example.org", 443)
    w.write(b"x")
    await w.drain()
    check("aether mode routes via SOCKS when connected", fs.requests and fs.requests[-1][1] == "example.org")
    w.close()

    upstream.configure(mode="auto")
    ready["v"] = False
    r, w = await upstream.open_upstream("127.0.0.1", dport)
    check("auto mode falls back to direct when tunnel is down", await r.readexactly(12) == b"direct-hello")
    w.close()
    n = len(fs.requests)
    ready["v"] = True
    r, w = await upstream.open_upstream("example.net", 80)
    w.write(b"x")
    await w.drain()
    check("auto mode uses SOCKS once tunnel is up", len(fs.requests) == n + 1)
    w.close()

    try:
        upstream.configure(mode="bogus")
        check("invalid mode rejected", False)
    except ValueError:
        check("invalid mode rejected", True)
    upstream.configure(mode="direct")
    dsrv.close()
    await fs.close()


class FakeSocksAuth(FakeSocks):
    """SOCKS5 server that requires RFC1929 username/password."""

    def __init__(self, user, pw):
        super().__init__()
        self.user, self.pw = user, pw
        self.auth_seen = None

    async def _handle(self, r, w):
        try:
            ver, n = await r.readexactly(2)
            methods = await r.readexactly(n)
            if 2 not in methods:
                w.write(b"\x05\xff")
                await w.drain()
                return
            w.write(b"\x05\x02")
            await r.readexactly(1)
            u = await r.readexactly((await r.readexactly(1))[0])
            p = await r.readexactly((await r.readexactly(1))[0])
            self.auth_seen = (u.decode(), p.decode())
            ok = self.auth_seen == (self.user, self.pw)
            w.write(b"\x01" + (b"\x00" if ok else b"\x01"))
            await w.drain()
            if not ok:
                return
            hdr = await r.readexactly(4)
            ln = (await r.readexactly(1))[0] if hdr[3] == 3 else 0
            host = (await r.readexactly(ln)).decode() if ln else ""
            port = int.from_bytes(await r.readexactly(2), "big")
            self.requests.append((hdr[3], host, port))
            w.write(bytes([5, 0, 0, 1]) + b"\x00" * 6)
            await w.drain()
            while True:
                data = await r.read(4096)
                if not data:
                    break
                w.write(data)
                await w.drain()
        except Exception:
            pass
        finally:
            w.close()


def test_parse_route():
    pr = upstream.parse_route
    check("route '' / None / default -> default", pr("") == pr(None) == pr("default") == "default")
    check("route keywords", pr("direct") == "direct" and pr("AETHER") == "aether" and pr("auto") == "auto")
    check("route aliases warp/cloudflare -> aether", pr("warp") == "aether" and pr("Cloudflare") == "aether")
    check("route socks5 normalised", pr("socks5://u:p@1.2.3.4:1080") == "socks5://u:p@1.2.3.4:1080"
          and pr("socks5h://proxy.example.com:9050") == "socks5://proxy.example.com:9050")
    for bad in ("socks5://nohost", "socks5://h:99999", "http://x:1", "banana", "socks5://" + "a" * 300 + ":1"):
        try:
            pr(bad)
            check(f"route rejects {bad[:30]!r}", False)
        except ValueError:
            check(f"route rejects {bad[:30]!r}", True)
    check("describe_route hides credentials", upstream.describe_route("socks5://u:secret@h:1") == "socks5://h:1"
          and upstream.describe_route(None) == "default")


async def test_per_inbound_routes():
    async def dest(r, w):
        w.write(b"direct-hello")
        await w.drain()
        w.close()

    dsrv = await asyncio.start_server(dest, "127.0.0.1", 0)
    dport = dsrv.sockets[0].getsockname()[1]
    warp = await FakeSocks().start()          # stands in for Aether's local SOCKS5
    ext = await FakeSocksAuth("bob", "pw").start()  # an external proxy with auth
    ready = {"v": True}
    upstream.configure(mode="direct", socks_port=warp.port, ready=lambda: ready["v"])

    # global=direct: only inbounds that ask for WARP use it
    r, w = await upstream.open_upstream("127.0.0.1", dport, route="default")
    check("route default follows global (direct)", await r.readexactly(12) == b"direct-hello" and not warp.requests)
    w.close()
    r, w = await upstream.open_upstream("example.org", 443, route="aether")
    w.write(b"x"); await w.drain()
    check("inbound route=aether uses WARP while global=direct", warp.requests and warp.requests[-1][1] == "example.org")
    w.close()

    # global=aether: an inbound can still opt out with direct
    upstream.configure(mode="aether")
    n = len(warp.requests)
    r, w = await upstream.open_upstream("127.0.0.1", dport, route="direct")
    check("inbound route=direct overrides global=aether", await r.readexactly(12) == b"direct-hello"
          and len(warp.requests) == n)
    w.close()
    r, w = await upstream.open_upstream("example.net", 80)
    w.write(b"x"); await w.drain()
    check("route=None follows global=aether", len(warp.requests) == n + 1)
    w.close()

    # route=aether is fail-closed when the tunnel is down, even if global=direct
    upstream.configure(mode="direct")
    ready["v"] = False
    try:
        await upstream.open_upstream("127.0.0.1", dport, route="aether")
        check("route=aether fail-closed when tunnel down", False)
    except upstream.UpstreamError:
        check("route=aether fail-closed when tunnel down", True)
    r, w = await upstream.open_upstream("127.0.0.1", dport, route="auto")
    check("route=auto falls back to direct when tunnel down", await r.readexactly(12) == b"direct-hello")
    w.close()
    ready["v"] = True

    # custom SOCKS5 proxy with RFC1929 auth
    r, w = await upstream.open_upstream("example.com", 443, route=f"socks5://bob:pw@127.0.0.1:{ext.port}")
    w.write(b"x"); await w.drain()
    check("custom socks5 route with auth", ext.auth_seen == ("bob", "pw") and ext.requests
          and ext.requests[-1][1] == "example.com")
    w.close()
    try:
        await upstream.open_upstream("example.com", 443, route=f"socks5://bob:WRONG@127.0.0.1:{ext.port}")
        check("custom socks5 wrong password rejected", False)
    except upstream.UpstreamError:
        check("custom socks5 wrong password rejected", True)

    upstream.configure(mode="direct")
    dsrv.close()
    await warp.close()
    await ext.close()


# ---------------------------------------------------------------- aether pure logic
def test_pure():
    o = aether.parse_options({"protocol": "evil", "port": 80, "ip": "6", "http_proxy": True,
                              "transport": "h3", "noize": "gfw"})
    check("parse_options rejects bad values", o["protocol"] == "masque" and o["port"] == 1819 and o["ip"] == "6"
          and o["noize"] == "gfw")
    check("H3 transport and HTTP proxy are gone", o["transport"] == "h2" and "http_proxy" not in o
          and aether.TRANSPORTS == ("h2",))
    a = aether.build_args(aether.parse_options({}))
    check("build_args defaults", a == ["--protocol", "masque", "--scan", "turbo", "-4", "--h2",
                                        "--bind", "127.0.0.1:1819", "--quick-reconnect"], a)
    a = aether.build_args(aether.parse_options({"protocol": "wg", "port": 2000, "http_proxy": True,
                                                "quick_reconnect": False, "ip": "dual"}))
    check("build_args wg (no transport flag, never an http proxy)", "--h2" not in a and "--h3" not in a
          and "--dual" in a and "--http-proxy" not in a and a[-1] == "--no-quick-reconnect", a)
    a = aether.build_args(aether.parse_options({"transport": "h3", "http_proxy": True}))
    check("build_args never emits --h3 / --http-proxy", "--h3" not in a and "--http-proxy" not in a and "--h2" in a, a)
    check("backoff", [aether.backoff_sec(i) for i in (0, 1, 2, 10)] == [2, 4, 8, 300])

    aether.S.phase = "stopped"
    aether.parse_line("\x1b[32m[+] scan mode=turbo\x1b[0m")
    check("phase scanning", aether.S.phase == "scanning")
    aether.parse_line("using cloudflare edge 162.159.1.1:443")
    check("phase connecting + gateway", aether.S.phase == "connecting" and aether.S.gateway == "162.159.1.1:443")
    aether.parse_line("socks5 server listening on 127.0.0.1:1819")
    check("phase connected", aether.S.phase == "connected" and aether.is_connected() is False)  # no proc yet
    aether.parse_line("exit: 104.28.1.2, DE via FRA, 87ms to cloudflare, warp on")
    check("exit parsed", aether.S.exit == {"ip": "104.28.1.2", "country": "DE", "colo": "FRA",
                                           "latency_ms": 87, "warp": "on"}, aether.S.exit)
    aether.parse_line("[ERROR] boom")
    check("error captured", aether.S.last_error == "boom" or "boom" in (aether.S.last_error or ""))
    aether.parse_line("tunnel ended, reconnecting")
    check("phase reconnecting", aether.S.phase == "reconnecting")


# ---------------------------------------------------------------- fake aether binary lifecycle
FAKE_AETHER = textwrap.dedent('''\
    #!/usr/bin/env python3
    import sys, time, socket, threading
    args = sys.argv[1:]
    port = int(args[args.index("--bind") + 1].split(":")[1])
    print("[*] scan mode=turbo", flush=True)
    print("using cloudflare edge 1.2.3.4:443", flush=True)
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", port)); s.listen(8)
    print("socks5 server listening on 127.0.0.1:%d" % port, flush=True)
    print("exit: 9.9.9.9, NL via AMS, 12ms to cloudflare", flush=True)
    while True:
        c, _ = s.accept(); c.close()
''')


async def test_lifecycle():
    tmp = tempfile.mkdtemp()
    binp = os.path.join(tmp, "aether")
    with open(binp, "w") as f:
        f.write(FAKE_AETHER)
    os.chmod(binp, os.stat(binp).st_mode | stat.S_IEXEC)
    os.environ["AETHER_BIN"] = binp
    os.environ["AETHER_DIR"] = tmp
    os.environ["WATCHDOG_TICK_SEC"] = "0.2"
    os.environ["WATCHDOG_BACKOFF_BASE_SEC"] = "0.2"
    os.environ["WATCHDOG_INTERVAL_SEC"] = "3600"  # skip health probes (no internet here)
    upstream.configure(ready=aether.is_connected)

    # persistence is DB-backed in the app; stub it so no DB is needed
    saved = {}

    async def fake_save(**patch):
        saved.update(patch)
        aether.S.cfg.update(patch)

    aether._save_cfg = fake_save
    aether.S.watchdog_task = asyncio.create_task(aether._watchdog_loop())

    port = 18199
    await aether.start({"port": port}, persist=True)
    for _ in range(50):
        if aether.is_connected():
            break
        await asyncio.sleep(0.1)
    check("fake aether reaches 'connected'", aether.is_connected() and aether.S.exit and aether.S.exit["country"] == "NL")
    check("upstream SOCKS port follows tunnel options", upstream.socks_port() == port)
    check("options persisted", saved.get("options", {}).get("port") == port)

    try:
        await aether.start({"port": port})
        check("double start rejected", False)
    except aether.AetherError:
        check("double start rejected", True)

    old_pid = aether.S.proc.pid
    os.kill(old_pid, 9)  # crash the tunnel; watchdog must bring it back
    for _ in range(80):
        if aether.is_connected() and aether.S.proc and aether.S.proc.pid != old_pid:
            break
        await asyncio.sleep(0.1)
    check("watchdog restarts a crashed tunnel", aether.is_connected() and aether.S.proc.pid != old_pid
          and aether.W.restarts >= 1, f"restarts={aether.W.restarts} phase={aether.S.phase}")

    await aether.stop()
    await asyncio.sleep(0.6)
    check("stop leaves it stopped (watchdog does not resurrect)", aether.S.proc is None and aether.S.phase == "stopped")

    aether.S.watchdog_task.cancel()


async def main():
    await test_socks()
    await test_modes()
    test_parse_route()
    await test_per_inbound_routes()
    test_pure()
    await test_lifecycle()


asyncio.run(main())
print("\nALL PASSED" if not FAILED else f"\nFAILED: {FAILED}")
sys.exit(1 if FAILED else 0)
