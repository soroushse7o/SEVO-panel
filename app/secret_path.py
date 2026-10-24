"""
Secret admin path.

The admin panel and every admin API are reachable ONLY under
``/<SECRET_PATH>/...`` (for example ``https://example.com/<SECRET_PATH>/panel``).
The same URLs without the prefix (``/panel``, ``/login``, ``/dashboard``,
``/api/*``, ``/stats``, ``/connections``) are answered with a plain 404, so the
login form and the admin API are invisible to scanners that do not know the
secret.

Public endpoints are untouched: ``/``, ``/health``, ``/api/health``,
``/sub/*``, ``/user/*``, ``/check/*``, ``/ws/*`` and the static images.

Configuration
-------------
* ``SECRET_PATH`` environment variable (3-64 chars: letters, digits, ``-`` ``_``).
* When it is not set, a random value is generated once, persisted in the
  settings table and printed in the startup log, so the panel is never exposed
  on a guessable default.

The middleware is a pure ASGI middleware: it rewrites ``/<secret>/x`` to ``/x``
before routing, so the existing routers keep working unchanged.
"""
import json
import re
import secrets

from app import state

_VALID = re.compile(r"^[A-Za-z0-9_-]{3,64}$")

# A secret equal to one of these would shadow a real public route.
RESERVED = frozenset({
    "api", "panel", "login", "dashboard", "stats", "connections", "ws", "sub",
    "user", "check", "health", "img", "favicon.ico", "static", "docs",
    "openapi.json", "redoc",
})

ADMIN_PREFIXES = ("/panel", "/login", "/dashboard", "/stats", "/connections", "/api/")
PUBLIC_EXACT = frozenset({"/api/health"})


def normalize(raw: str | None) -> str:
    return (raw or "").strip().strip("/")


def validate(raw: str | None) -> str:
    """Return the cleaned secret, or raise ValueError with a readable reason."""
    s = normalize(raw)
    if not _VALID.match(s):
        raise ValueError("SECRET_PATH must be 3-64 characters: letters, digits, '-' or '_'")
    if s.lower() in RESERVED:
        raise ValueError(f"SECRET_PATH '{s}' is reserved; choose another value")
    return s


def generate() -> str:
    return secrets.token_urlsafe(12).replace("=", "")


def base_prefix() -> str:
    """'/<secret>' for building URLs, '' while no secret is configured yet."""
    return f"/{state.secret_path}" if state.secret_path else ""


def panel_url(domain: str) -> str:
    return f"https://{domain}{base_prefix()}/panel"


def is_admin_path(path: str) -> bool:
    if path in PUBLIC_EXACT:
        return False
    return path.startswith(ADMIN_PREFIXES) or path == "/openapi.json"


class SecretPathMiddleware:
    """Pure ASGI middleware (HTTP only; WebSockets are only used on /ws/*)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope["path"]
        sp = state.secret_path

        if sp and (path == f"/{sp}" or path.startswith(f"/{sp}/")):
            rest = path[len(sp) + 1:]
            if not rest or rest == "/":
                await _redirect(send, f"/{sp}/panel")
                return
            scope = dict(scope)
            scope["path"] = rest
            scope["raw_path"] = rest.encode("utf-8")
            scope["se7o_admin"] = True
            await self.app(scope, receive, send)
            return

        if is_admin_path(path):
            await _not_found(send)
            return

        await self.app(scope, receive, send)


async def _not_found(send):
    body = json.dumps({"detail": "Not Found"}).encode()
    await send({"type": "http.response.start", "status": 404, "headers": [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode()),
        (b"cache-control", b"no-store"),
    ]})
    await send({"type": "http.response.body", "body": body})


async def _redirect(send, location: str):
    await send({"type": "http.response.start", "status": 307, "headers": [
        (b"location", location.encode()),
        (b"content-length", b"0"),
        (b"cache-control", b"no-store"),
    ]})
    await send({"type": "http.response.body", "body": b""})


async def resolve_at_startup(logger) -> str:
    """Pick the secret: env var > value persisted in DB > freshly generated."""
    from app.database import get_setting, set_setting

    env = normalize(__import__("os").environ.get("SECRET_PATH", ""))
    if env:
        try:
            sp = validate(env)
        except ValueError as e:
            logger.error("%s - ignoring the environment value", e)
            env = ""
        else:
            if sp != await get_setting("secret_path", ""):
                await set_setting("secret_path", sp)
            state.secret_path = sp
            logger.info("Admin panel path: /%s/panel (from SECRET_PATH)", sp)
            return sp

    stored = await get_setting("secret_path", "")
    try:
        sp = validate(stored) if stored else ""
    except ValueError:
        sp = ""
    if not sp:
        sp = generate()
        await set_setting("secret_path", sp)
        logger.warning("SECRET_PATH is not set - generated one. Admin panel: /%s/panel "
                       "(set the SECRET_PATH environment variable to choose your own)", sp)
    else:
        logger.info("Admin panel path: /%s/panel (persisted; set SECRET_PATH to override)", sp)
    state.secret_path = sp
    return sp
