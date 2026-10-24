<div align="center">

<img src="app/static/img/logo.png" alt="SE7O-SNA" width="140">

# SE7O-SNA Panel v3

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/self-hosted-panel?utm_medium=integration&utm_source=template&utm_campaign=generic)

**A self-hosted subscription panel for VLESS over WebSocket, with an optional Aether tunnel exit.**

Modular Python application · FastAPI · SQLite or PostgreSQL

[English](README.md) · [فارسی](README.fa.md)

</div>

---

## Overview

SE7O-SNA Panel manages VLESS inbounds and subscription links from one dashboard. The code is a
modular package: configuration, database access, state, security, routes, and background services
each live in their own module, while the web UI remains a single embedded HTML template.
Deployment is simple — push the repository to Railway and set a handful of environment variables.
No database server, reverse proxy, or build pipeline is required.

Besides the panel itself, the container also runs two optional helpers as child processes: an
MTProto proxy (`mtg`) for Telegram, and the [Aether](https://github.com/CluvexStudio/Aether)
tunnel client, which can carry all of your users' outbound traffic through Cloudflare instead of
the server's own IP.

## Features

**Access control**
Username and password login, JWT sessions in HTTP-only cookies (valid for 7 days), a login endpoint
limited to 10 attempts per minute, a password policy enforced when you change the password
(8+ characters with upper case, lower case, and a digit), and an audit log of every login attempt
with IP and user agent.

**Inbound management**
Create, edit, enable, disable, and delete VLESS configurations. Set per-inbound traffic quotas,
expiry dates, and concurrent-connection limits. Override path, SNI, host, and TLS fingerprint
individually, add packet-fragmentation ranges against DPI, and assign country flags. Rotate an
inbound's UUID, disconnect its live sessions, or fetch its client JSON. Bulk actions cover
activation, quota resets, and deletion. Inbounds can be exported to and imported from JSON, and the
whole panel can be backed up and restored from a single file.

**Analytics**
Live upload and download charts, 24-hour timezone-aware traffic history, per-inbound
distribution, monthly quota tracking, and CPU, memory, and disk monitoring.

**Clean IP list**
Add, edit, bulk-import, and bulk-delete IPv4 addresses, IPv6 addresses, and hostnames that are
attached to generated subscriptions. A default set is seeded on first run and can be cleared or
replaced entirely from the dashboard.

**Subscriptions and per-user page**
Every inbound has a subscription endpoint at `/sub/{uid}` and a public page at `/user/{uid}`
showing status, data usage, expiry, a QR code, and one-tap copy buttons for the subscription and
single VLESS links — shareable with end users without granting panel access.

**Transport**
WebSocket is the only transport. It runs on the platform's HTTPS port, so no extra port is needed.

| Transport | Endpoint | Notes |
|-----------|----------|-------|
| WebSocket | `/ws/{uuid}` | The only supported transport. |

Default path, TLS fingerprint, SNI, host, and ALPN can be changed through the outbound settings
(`/api/outbound-config`).

**Aether tunnel exit**
The **Aether** tab starts, stops, and restarts the Aether tunnel client and shows its live phase,
gateway, exit, and logs. Aether exposes a local SOCKS5 proxy on `127.0.0.1` (port `1819` by
default), and the panel can route every user connection
through it. Details are in [Aether tunnel](#6-aether-tunnel-optional) below.

**Telegram MTProxy**
An MTProto proxy (`mtg`) runs as a child process inside the same container. The FakeTLS secret is
generated on first start and persisted, and the panel builds the `tg://proxy` link automatically
from the platform's TCP proxy address. The MTProxy tab shows process state, the public endpoint,
a QR code, and lets you rotate the secret or change the fronting domain.

**Telegram notifications**
Bilingual (English/Persian) templates for panel logins, expired inbounds, errors, 90% quota
warnings, and tunnel-down alerts, with a live template preview and a periodic usage report whose
interval you choose in the dashboard.

**Keep-alive**
Simple and advanced anti-sleep modes with a configurable interval, for instances that get idled
out after a period of inactivity.

---

## Quick start

### 1. Deploy on Railway

Click the button to deploy from the template:

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/self-hosted-panel?utm_medium=integration&utm_source=template&utm_campaign=generic)

Or deploy manually: fork this repository to your GitHub account, create a new Railway project from
the fork, and let Railway build it. The included `Dockerfile` is detected automatically; no start
command is needed (the `Procfile` runs `python main.py` as a fallback).

### 2. Configure

Add these environment variables in the Railway service's **Variables** tab. A ready-to-copy list
with comments is also in [`SE7O-SNA-config.toml`](SE7O-SNA-config.toml).

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `ADMIN_USERNAME` | Recommended | `se7oadmin` | Panel login username. Defaults to `admin`. |
| `ADMIN_PASSWORD` | Yes | `StrongPass!123` | Panel login password. Defaults to `admin` if unset, so always set your own. |
| `SECRET_KEY` | Yes | *(long random string)* | Signs JWT session cookies. If unset, a new key is generated on first start and stored in the database. |
| `DOMAIN` | Recommended | `se7o-sna.up.railway.app` | Public domain, used to build subscription links correctly. Detected automatically from Railway's `RAILWAY_PUBLIC_DOMAIN` when unset. |
| `DB_PATH` | Recommended | `/data/panel.db` | SQLite file location. Mount a Railway volume at `/data` to keep data across redeploys. |
| `DATABASE_URL` | Optional | `postgres://…` | External PostgreSQL connection string. Overrides `DB_PATH`. |
| `PORT` | Optional | `8080` | Listening port. Railway injects its own value. |
| `MTPROXY_ENABLED` | Optional | `true` | Set to `false` to run the panel without the Telegram proxy. |
| `MTPROXY_PORT` | Optional | `443` | Port mtg binds to *inside* the container. This is the value you enter when creating the TCP proxy. |
| `MTPROXY_FAKE_DOMAIN` | Optional | `www.cloudflare.com` | Domain the FakeTLS secret impersonates. |
| `MTPROXY_SECRET` | Optional | `ee…` | Pin a specific secret instead of generating one. |
| `MTPROXY_CONCURRENCY` | Optional | `4096` | Maximum concurrent MTProxy connections. |
| `MTPROXY_PUBLIC_HOST` | Optional | `shuttle.proxy.rlwy.net` | Override the public host if it is not detected automatically. |
| `MTPROXY_PUBLIC_PORT` | Optional | `15140` | Override the public port. |

The Aether-related variables are all optional and listed in the
[Aether section](#6-aether-tunnel-optional).

`ADMIN_USERNAME`, `ADMIN_PASSWORD`, and `SECRET_KEY` are read from the environment on **every**
startup, not just the first one: if you change one in Railway and redeploy, it overrides whatever
is currently stored in the database. Leave a variable unset to keep whatever is already stored
(or, on a brand-new deployment, the built-in default).

### 3. Keep your data

Add a volume to the Railway service, mount it at `/data`, and set `DB_PATH=/data/panel.db`. The
SQLite database, the generated MTProxy secret, and Aether's settings and binary directory all live
under that path, so they survive redeploys. Without a volume, use `DATABASE_URL` pointing to a
PostgreSQL instance instead; the application detects it at startup and uses it in place of SQLite.

### 4. Enable the Telegram proxy

In the Railway service settings open **Networking → TCP Proxy** and enter the *internal* port
`443` (or whatever `MTPROXY_PORT` is set to). Railway responds with a public address such as
`shuttle.proxy.rlwy.net:15140`.

Nothing else is required. Railway injects `RAILWAY_TCP_PROXY_DOMAIN` and `RAILWAY_TCP_PROXY_PORT`
into the container, the panel reads them, and the MTProxy tab shows the finished link:

```
tg://proxy?server=shuttle.proxy.rlwy.net&port=15140&secret=ee…
```

The link must always carry that public address. The container's own IP is private and unreachable
from the internet, so it never appears in the link. Until a TCP proxy exists the tab shows a
warning and a provisional address. If the variables are ever missing, set `MTPROXY_PUBLIC_HOST`
and `MTPROXY_PUBLIC_PORT` yourself.

### 5. Second public domain (optional)

**Railway TCP proxy budget.** A Railway project currently allows up to 3 TCP proxies and 2 public
domains per service. This project uses them like this:

| # | Used by | Internal port | Set from Railway's output |
|---|---|---|---|
| 1 | MTProxy | `MTPROXY_PORT` (443) | `MTPROXY_PUBLIC_HOST` / `MTPROXY_PUBLIC_PORT` |
| 2 | *free* | — | not used by the panel today |
| 3 | *free* | — | not used by the panel today |

Aether's SOCKS5 listener binds to `127.0.0.1` only, so it needs no TCP proxy.

**Using the second public domain.** Railway can also give a service a second public HTTP domain
(Settings → Networking → Public Networking → "+ Domain"). No new code is needed — every link can
carry its own `Host` / `SNI` (Advanced Options, or `custom_host` / `custom_sni` via the API). Point
new `ws` links at the second domain by filling those two fields with it; the panel serves both
domains from the same process, so if one domain gets blocked you can immediately hand out links on
the other without redeploying anything.

### 6. Aether tunnel (optional)

Aether is a Cloudflare-based tunnel client. The Docker image ships a pinned, sha256-verified
release (`v1.5.0`, amd64 and arm64) at `/usr/local/bin/aether`. If the binary is missing, the
**Install** button in the Aether tab downloads and verifies it for you.

1. Open the **Aether** tab and press **Start**. Wait until the phase reads `connected`.
2. Choose an **Exit mode** and save it:

| Mode | Behaviour |
|------|-----------|
| `direct` (default) | Connections leave straight from the server's IP, as if Aether were not there. |
| `auto` | Through Aether while it is connected, directly otherwise. |
| `aether` | Always through Aether. If the tunnel is down, connections are **refused** (fail-closed), so the server's IP never leaks. |

3. Optionally enable **auto start** so the tunnel comes up after every restart.

The tab also lets you pick the protocol (`masque`, `wg`, `gool`, `mim`), transport (`h2`, `h3`),
scan mode (`turbo`, `balanced`, `thorough`, `verified`, `ironclad`), IP family (`4`, `6`, `dual`),
noize profile, local SOCKS port, and an optional local HTTP proxy. A watchdog probes the tunnel
through its SOCKS5 port, restarts it with exponential backoff, and falls back to the last known-good
preset after repeated failed starts. Enable the **Tunnel down** event in the Telegram tab to be
notified.

Aether carries TCP only; UDP does not go through it. While Aether is scanning or connecting for the
first time in `aether` mode, user connections are refused.

| Variable | Default | Description |
|----------|---------|-------------|
| `AETHER_OUTBOUND` | *(panel setting)* | `direct`, `auto`, or `aether`. When set, it overrides the choice saved in the panel. |
| `AETHER_AUTO_START` | *(panel setting)* | `1` to start the tunnel automatically after every restart. |
| `AETHER_BIN` | `/usr/local/bin/aether` | Path to the Aether binary. |
| `AETHER_DIR` | `<DB directory>/aether` | Where Aether keeps its working files and downloaded binary. |
| `AETHER_VERSION` | `v1.5.0` | Release used by the in-panel **Install** button. |
| `WATCHDOG_TICK_SEC` | `5` | How often the watchdog loop wakes up. |
| `WATCHDOG_INTERVAL_SEC` | `30` | Seconds between health probes. |
| `WATCHDOG_MAX_FAILURES` | `3` | Failed probes in a row before a restart. |
| `WATCHDOG_STUCK_SEC` | `300` | Restart if the tunnel is stuck in a non-connected phase this long. |
| `WATCHDOG_STABLE_SEC` | `60` | Time connected before a run counts as stable. |
| `WATCHDOG_FALLBACK_AFTER` | `3` | Failed starts before falling back to the last known-good preset. |
| `WATCHDOG_BACKOFF_BASE_SEC` | `2` | First restart delay; doubles on each failure. |
| `WATCHDOG_BACKOFF_MAX_SEC` | `300` | Upper limit for the restart delay. |
| `WATCHDOG_PROBE_TIMEOUT_SEC` | `10` | Timeout of a single probe. |

More background on how Aether was merged into this panel is in
[`AETHER-MERGE.md`](AETHER-MERGE.md) (Persian).

### 7. Sign in

Open your deployment URL at `/panel` and log in with `ADMIN_USERNAME` and `ADMIN_PASSWORD`.
Changing the password from **Settings** afterwards takes effect immediately and persists in the
database — just don't leave a stale `ADMIN_PASSWORD` variable set to the old value, since that
will overwrite your in-panel change on the next redeploy.

---

## Repository layout

| Path | Purpose |
|------|---------|
| `main.py` | Entry point: logging, lifespan, app factory, and router registration. |
| `Dockerfile` | Builds the image with the `mtg` and pinned Aether binaries included. |
| `Procfile` | `web: python main.py` fallback start command. |
| `SE7O-SNA-config.toml` | Commented list of every environment variable to copy into Railway. |
| `AETHER-MERGE.md` | Notes on the Aether integration (Persian). |
| `app/config.py` | Environment-driven configuration singleton. |
| `app/database.py` | Async SQLite/PostgreSQL abstraction and schema. |
| `app/state.py` | Centralized in-memory state and event log. |
| `app/security.py` | Bcrypt hashing, JWT creation, and the auth dependency. |
| `app/vless.py` | VLESS link generation, subscription content, and header parsing. |
| `app/utils.py` | Pure formatting and validation helpers. |
| `app/models.py` | Pydantic request models. |
| `app/routes/` | HTTP and WebSocket endpoints, grouped by domain (auth, links, addresses, stats, settings, subscription, backup, mtproxy, panel, transports, aether). |
| `app/routes/tunnel.py` | WebSocket VLESS tunnel endpoint — the core proxy engine. |
| `app/routes/aether.py` | Aether control API under `/api/aether/*`. |
| `app/services/` | Background loops and helpers: traffic, keep-alive, Telegram, link expiry. |
| `app/services/mtproxy.py` | MTProto proxy supervisor, secret handling, link building. |
| `app/services/aether.py` | Aether process manager: install, start/stop, log parsing, watchdog. |
| `app/services/upstream.py` | Single outbound connector used by the tunnel (direct or via Aether SOCKS5). |
| `app/templates/panel_html.py` | The embedded single-page admin frontend. |
| `app/templates/user_html.py` | The public per-user subscription page. |
| `app/static/img/`, `img/` | Logo and favicon assets. |
| `smoke_test.py` | End-to-end test suite against a running instance. |
| `test_mtproxy.py` | Unit tests for secrets, endpoint resolution, and the MTProxy supervisor. |
| `test_upstream.py` | Unit tests for the outbound connector, Aether log parsing, and the watchdog. |
| `test_linkgen.py`, `test_audit_transports.py` | Check that generated links match the endpoints the server serves. |
| `test_endpoints_defined.py` | Checks that every transport and `/api/aether/*` route is registered. |

## Local development

```bash
pip install -r requirements.txt
DB_PATH=./panel.db ADMIN_USERNAME=admin ADMIN_PASSWORD=Test1234 python main.py
```

The panel is then served at `http://127.0.0.1:8080/panel`.

To run the end-to-end suite, start the server on port 8899 with username `se7oadmin` and password
`Test1234`, then run:

```bash
python smoke_test.py
```

The remaining tests need no running server and no Docker:

```bash
python test_mtproxy.py
python test_upstream.py
python test_linkgen.py
python test_audit_transports.py
python test_endpoints_defined.py   # needs requirements installed
```

## Bandwidth costs

The panel is free; outbound bandwidth is billed by Railway. At the time of writing that is roughly
$0.10 per GB on pay-as-you-go usage, but pricing changes — always confirm on Railway's pricing
page. Use per-inbound quotas to keep consumption predictable.

---

## Disclaimer

This software is provided free of charge for personal, educational, and experimental use.
It is not for sale, and it must not be used to sell VPN subscriptions or to abuse the free tiers
of hosting providers through duplicate accounts. You are solely responsible for your traffic and
for compliance with your provider's terms of service. The author accepts no liability for
damages, billing overages, or service violations.

## Credits

Original project by **Standing In Heaven**. Maintained and updated by
[soroushse7o](https://github.com/soroushse7o).

## Acknowledgements

Built with [FastAPI](https://fastapi.tiangolo.com/). Charts by [Chart.js](https://www.chartjs.org/).
Icons are inline SVG in the Lucide/Feather style, themed with `currentColor`. The tunnel client is
[Aether](https://github.com/CluvexStudio/Aether), and the Telegram proxy is
[mtg](https://github.com/9seconds/mtg).

## License

See [LICENSE](LICENSE).
