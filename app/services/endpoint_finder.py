"""
Best Endpoint Finder -- network diagnosis + latency testing from the panel server.

Measures, for each candidate endpoint (IP, hostname or a random sample of a
CIDR range), over several attempts:

  tcp   TCP connect latency
  tls   TCP connect + TLS handshake (with a chosen SNI)
  http  TLS + ``GET /cdn-cgi/trace`` -> also reports the Cloudflare colo /
        country / visible IP, which proves the endpoint really is Cloudflare

and ranks them by (average latency + jitter, packet loss). Runs as a
background job so long scans survive proxy timeouts; the UI polls it.

Safety: this is an admin-only tool, but it still refuses private, loopback,
link-local, multicast and reserved destinations so it can't be used to probe
the server's internal network (SSRF).
"""
from __future__ import annotations

import asyncio
import ipaddress
import random
import re
import secrets
import socket
import ssl
import statistics
import time
from typing import Any, Optional

MODES = ("tcp", "tls", "http")
MAX_TARGETS = 300
MAX_CONCURRENCY = 50
MAX_JOBS_KEPT = 8

# Cloudflare's published IPv4 ranges (https://www.cloudflare.com/ips-v4).
CLOUDFLARE_RANGES = [
    "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22",
    "141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20",
    "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
    "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
]

_HOST_RE = re.compile(r"^(?=.{1,253}$)([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$")
_TRACE_RE = re.compile(r"^(colo|loc|ip)=(.+)$", re.M)


class FinderError(ValueError):
    """User-facing validation error."""


# ----------------------------------------------------------------- targets

def _is_public(ip: ipaddress._BaseAddress) -> bool:
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
                or ip.is_reserved or ip.is_unspecified)


def expand_targets(raw: str, sample_per_cidr: int = 10, max_total: int = MAX_TARGETS) -> list[str]:
    """Turn free text (IPs, hostnames, CIDRs; space/comma/newline separated) into a deduped list."""
    out: list[str] = []
    seen: set[str] = set()

    def add(x: str) -> None:
        if x not in seen and len(out) < max_total:
            seen.add(x)
            out.append(x)

    sample_per_cidr = max(1, min(int(sample_per_cidr), 256))
    for tok in re.split(r"[\s,;]+", raw or ""):
        tok = tok.strip().strip("[]")
        if not tok:
            continue
        if "/" in tok:
            try:
                net = ipaddress.ip_network(tok, strict=False)
            except ValueError:
                raise FinderError(f"invalid CIDR: {tok}")
            if net.version != 4:
                raise FinderError(f"only IPv4 ranges can be sampled: {tok}")
            total = net.num_addresses
            if total <= 2:
                hosts = [str(a) for a in net]
            else:
                lo, hi = 1, total - 2  # skip network + broadcast
                n = min(sample_per_cidr, hi - lo + 1)
                hosts = [str(net.network_address + i) for i in random.sample(range(lo, hi + 1), n)]
            for h in hosts:
                add(h)
            continue
        try:
            add(str(ipaddress.ip_address(tok)))
            continue
        except ValueError:
            pass
        if _HOST_RE.match(tok):
            add(tok.lower())
        else:
            raise FinderError(f"invalid address: {tok[:60]}")
    if not out:
        raise FinderError("no targets given")
    return out


async def _resolve(host: str) -> tuple[str, float]:
    """Return (ip, dns_ms). IP literals resolve instantly."""
    try:
        ip = ipaddress.ip_address(host)
        return str(ip), 0.0
    except ValueError:
        pass
    t0 = time.monotonic()
    loop = asyncio.get_running_loop()
    infos = await asyncio.wait_for(loop.getaddrinfo(host, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM), 5.0)
    if not infos:
        raise OSError("no DNS answer")
    # prefer IPv4 for predictable results
    infos.sort(key=lambda i: 0 if i[0] == socket.AF_INET else 1)
    return infos[0][4][0], (time.monotonic() - t0) * 1000


# ----------------------------------------------------------------- probing

def _tls_ctx() -> ssl.SSLContext:
    # Verification is off on purpose: we measure reachability/handshake time to
    # arbitrary IPs with an arbitrary SNI; no credentials are ever sent.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.set_alpn_protocols(["http/1.1"])
    return ctx


async def _probe_once(ip: str, port: int, mode: str, sni: str, timeout: float) -> dict[str, Any]:
    t0 = time.monotonic()
    reader = writer = None
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout)
        tcp_ms = (time.monotonic() - t0) * 1000
        res: dict[str, Any] = {"ok": True, "ms": tcp_ms, "tcp_ms": tcp_ms}
        if mode in ("tls", "http"):
            t1 = time.monotonic()
            await asyncio.wait_for(writer.start_tls(_tls_ctx(), server_hostname=sni), timeout)
            tls_ms = (time.monotonic() - t1) * 1000
            res["tls_ms"] = tls_ms
            res["ms"] = tcp_ms + tls_ms
            if mode == "http":
                t2 = time.monotonic()
                writer.write(f"GET /cdn-cgi/trace HTTP/1.1\r\nHost: {sni}\r\nUser-Agent: se7o-sna-finder\r\n"
                             "Accept: */*\r\nConnection: close\r\n\r\n".encode())
                await writer.drain()
                data = await asyncio.wait_for(reader.read(2048), timeout)
                res["ttfb_ms"] = (time.monotonic() - t2) * 1000
                res["ms"] = tcp_ms + tls_ms + res["ttfb_ms"]
                head, _, body = data.decode("latin-1", "replace").partition("\r\n\r\n")
                status = head.split(" ", 2)[1] if head.startswith("HTTP/") and " " in head else ""
                res["http_status"] = status
                trace = dict(_TRACE_RE.findall(body))
                if trace:
                    res["cf"] = {"colo": trace.get("colo", "").strip(), "loc": trace.get("loc", "").strip(),
                                 "ip": trace.get("ip", "").strip()}
        return res
    except Exception as e:
        return {"ok": False, "error": (type(e).__name__ if not str(e) else str(e))[:80]}
    finally:
        if writer is not None:
            try:
                writer.close()
            except Exception:
                pass


async def probe_endpoint(target: str, port: int, mode: str, sni: str, attempts: int, timeout: float) -> dict[str, Any]:
    """Probe one endpoint ``attempts`` times and aggregate the numbers."""
    row: dict[str, Any] = {"target": target, "port": port, "ok": False}
    try:
        ip, dns_ms = await _resolve(target)
        if not _is_public(ipaddress.ip_address(ip)):
            row.update(error="blocked: non-public address", ip=ip, loss=100.0, score=1e9)
            return row
        row.update(ip=ip, dns_ms=round(dns_ms, 1))
    except Exception as e:
        row.update(error=f"DNS: {str(e) or type(e).__name__}"[:80], loss=100.0, score=1e9)
        return row

    samples = []
    last_err = ""
    extra: dict[str, Any] = {}
    for i in range(attempts):
        r = await _probe_once(ip, port, mode, sni, timeout)
        if r["ok"]:
            samples.append(r["ms"])
            for k in ("tcp_ms", "tls_ms", "ttfb_ms", "http_status", "cf"):
                if k in r:
                    extra.setdefault(k, []).append(r[k])
        else:
            last_err = r["error"]
        if i < attempts - 1:
            await asyncio.sleep(0.05)

    sent, got = attempts, len(samples)
    loss = round((sent - got) * 100.0 / sent, 1)
    row.update(sent=sent, received=got, loss=loss)
    if samples:
        avg = statistics.fmean(samples)
        jitter = statistics.pstdev(samples) if len(samples) > 1 else 0.0
        row.update(ok=True, min=round(min(samples), 1), avg=round(avg, 1), max=round(max(samples), 1),
                   jitter=round(jitter, 1), score=round(avg + jitter + loss * 20, 1))
        for k in ("tcp_ms", "tls_ms", "ttfb_ms"):
            if k in extra:
                row[k] = round(statistics.fmean(extra[k]), 1)
        if "http_status" in extra:
            row["http_status"] = extra["http_status"][-1]
        if "cf" in extra:
            row["cf"] = extra["cf"][-1]
        if loss:
            row["error"] = f"{loss:g}% loss ({last_err})"
    else:
        row.update(error=last_err or "unreachable", score=1e9)
    return row


# ----------------------------------------------------------------- jobs

JOBS: dict[str, dict[str, Any]] = {}


def _public(job: dict[str, Any], with_results: bool = True) -> dict[str, Any]:
    out = {k: v for k, v in job.items() if k not in ("task", "results")}
    if with_results:
        out["results"] = sorted(job["results"], key=lambda r: (not r["ok"], r.get("score", 1e9)))
    return out


def get_job(job_id: str) -> Optional[dict[str, Any]]:
    j = JOBS.get(job_id)
    return _public(j) if j else None


def running_job() -> Optional[str]:
    for jid, j in JOBS.items():
        if j["status"] == "running":
            return jid
    return None


def validate_params(p: dict) -> dict[str, Any]:
    mode = str(p.get("mode") or "tls").lower()
    if mode not in MODES:
        raise FinderError(f"mode must be one of: {', '.join(MODES)}")
    def num(key, default, cast):
        v = p.get(key)
        return default if v is None or v == "" else cast(v)

    try:
        port = num("port", 443, int)
        attempts = num("attempts", 3, int)
        timeout = num("timeout", 4.0, float)
        conc = num("concurrency", 20, int)
        sample = num("sample", 10, int)
    except (TypeError, ValueError):
        raise FinderError("port, attempts, timeout, concurrency and sample must be numbers")
    if not 1 <= port <= 65535:
        raise FinderError("port must be 1-65535")
    sni = str(p.get("sni") or "").strip().lower() or "www.cloudflare.com"
    if not _HOST_RE.match(sni):
        raise FinderError("invalid SNI / Host")
    return {
        "mode": mode, "port": port, "sni": sni,
        "attempts": max(1, min(attempts, 10)),
        "timeout": max(1.0, min(timeout, 10.0)),
        "concurrency": max(1, min(conc, MAX_CONCURRENCY)),
        "sample": max(1, min(sample, 256)),
    }


def start_job(raw_targets: str, params: dict) -> str:
    prm = validate_params(params)
    targets = expand_targets(raw_targets, prm["sample"])
    if running_job():
        raise FinderError("another scan is already running; wait for it or cancel it")

    job_id = secrets.token_urlsafe(8)
    job: dict[str, Any] = {
        "id": job_id, "status": "running", "total": len(targets), "done": 0,
        "params": prm, "started": time.time(), "finished": None, "error": None, "results": [],
    }
    JOBS[job_id] = job
    for old in sorted(JOBS, key=lambda k: JOBS[k]["started"])[:-MAX_JOBS_KEPT]:
        if JOBS[old]["status"] != "running":
            JOBS.pop(old, None)
    job["task"] = asyncio.create_task(_run(job, targets))
    return job_id


async def _run(job: dict[str, Any], targets: list[str]) -> None:
    prm = job["params"]
    sem = asyncio.Semaphore(prm["concurrency"])

    async def one(t: str) -> None:
        async with sem:
            r = await probe_endpoint(t, prm["port"], prm["mode"], prm["sni"], prm["attempts"], prm["timeout"])
        job["results"].append(r)
        job["done"] += 1

    try:
        await asyncio.gather(*(one(t) for t in targets))
        job["status"] = "done"
    except asyncio.CancelledError:
        job["status"] = "cancelled"
    except Exception as e:  # pragma: no cover - defensive
        job["status"] = "error"
        job["error"] = str(e)[:200]
    finally:
        job["finished"] = time.time()


def cancel_job(job_id: str) -> bool:
    j = JOBS.get(job_id)
    if not j or j["status"] != "running":
        return False
    j["task"].cancel()
    return True
