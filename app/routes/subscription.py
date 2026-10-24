"""
User-facing subscription and dashboard routes.
No auth required — these are public endpoints for VPN clients.
"""
import base64
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import Response, HTMLResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from app import state
from urllib.parse import quote
from app.vless import (
    generate_vless_link, generate_subscription_content, encode_subscription,
    get_domain, _fmt_bytes, LinkConfigError,
)
from app.utils import esc
from app.templates.user_html import USER_PAGE_TEMPLATE
from app.database import fetchone
from datetime import datetime, timezone

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


def _get_link(uid: str):
    """Get active, non-expired link by UID."""
    from asyncio import Lock

    async def _get():
        async with state.links_lock:
            link = state.links.get(uid)
            if not link or not link["active"]:
                return None
            return dict(link)
    return _get


@router.get("/user/{uid}", response_class=HTMLResponse)
async def user_dashboard(uid: str, request: Request):
    """Public per-user page: status, usage, expiry, QR code and copy buttons."""
    async with state.links_lock:
        link = state.links.get(uid)
        if not link or not link["active"]:
            raise HTTPException(status_code=404, detail="User not found or disabled")
        link = dict(link)

    expires = _parse_dt(link.get("expires_at"))
    if expires and expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=403, detail="User expired")

    used = link["used_bytes"]
    limit = link["limit_bytes"]
    usage_percent = 0 if limit == 0 else min(100, round(used / limit * 100, 1))
    bar_color = "#4ade80" if usage_percent < 80 else ("#fbbf24" if usage_percent < 95 else "#f87171")

    status = "Active"
    if limit > 0 and used >= limit:
        status = "Quota Exceeded"
    elif not link["active"]:
        status = "Blocked"

    try:
        vless_link = await generate_vless_link(uid, remark=link["label"], extra={
            "custom_path": link.get("custom_path", ""),
            "custom_sni": link.get("custom_sni", ""),
            "custom_host": link.get("custom_host", ""),
            "custom_fp": link.get("custom_fp", "chrome"),
            "fragment": link.get("fragment", ""),
            "transport": link.get("transport", "ws"),
        })
    except LinkConfigError:
        vless_link = ""
    sub_url = f"https://{get_domain()}/sub/{uid}"
    qr_url = "https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=" + quote(sub_url, safe="")
    expiry_str = "Unlimited" if not expires else expires.strftime("%Y-%m-%d %H:%M (UTC)")
    limit_str = "Unlimited" if limit == 0 else _fmt_bytes(limit)

    label = esc(link["label"])
    html = USER_PAGE_TEMPLATE.format(
        label=label,
        status=esc(status),
        used=esc(_fmt_bytes(used)),
        limit=esc(limit_str),
        usage_percent=usage_percent,
        bar_color=bar_color,
        expiry=esc(expiry_str),
        qr_url=esc(qr_url),
        sub_url=esc(sub_url),
        vless_link=esc(vless_link),
    )
    return HTMLResponse(content=html)


@router.get("/sub/{uid}")
@limiter.limit("10/minute")
async def subscription_endpoint(uid: str, request: Request):
    async with state.links_lock:
        link = state.links.get(uid)
        if not link or not link["active"]:
            raise HTTPException(status_code=404, detail="Not found")
        link = dict(link)

    expires = _parse_dt(link.get("expires_at"))
    if expires and expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=403, detail="Expired")

    async with state.addresses_lock:
        addresses = list(state.addresses)

    extra = {
        "custom_path": link.get("custom_path", ""),
        "custom_sni": link.get("custom_sni", ""),
        "custom_host": link.get("custom_host", ""),
        "custom_fp": link.get("custom_fp", "chrome"),
        "fragment": link.get("fragment", ""),
        "transport": link.get("transport", "ws"),
    }

    status = "active"
    if link.get("limit_bytes", 0) > 0 and link["used_bytes"] >= link["limit_bytes"]:
        status = "quota_exceeded"
    elif expires and expires < datetime.now(timezone.utc):
        status = "expired"

    try:
        content = await generate_subscription_content(link, uid, addresses, extra, status)
    except LinkConfigError as e:
        # Don't 500 the whole subscription URL (clients poll this
        # periodically) just because e.g. this link is set to tcp and
        # RAW_TCP_PUBLIC_HOST/PORT aren't configured yet -- return a
        # single-line remark explaining it instead so at least the
        # subscription still loads.
        content = f"# SE7O-SNA: {e}"
    encoded = encode_subscription(content)

    total = link["limit_bytes"] if link["limit_bytes"] > 0 else 53_687_091_200_000
    expire_ts = int(expires.timestamp()) if expires else 0

    headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "Content-Disposition": 'attachment; filename="sub.txt"',
        "profile-update-interval": "6",
        "subscription-userinfo": f"upload={link['used_bytes']}; download=0; total={total}; expire={expire_ts}",
        "X-Status": status,
    }
    return Response(content=encoded, headers=headers)


@router.get("/check/{uid}")
async def public_link_check(uid: str):
    async with state.links_lock:
        link = state.links.get(uid)
    if not link:
        return {"healthy": False, "reason": "not_found"}
    if not link.get("active"):
        return {"healthy": False, "reason": "disabled"}
    expires = _parse_dt(link.get("expires_at"))
    if expires and expires < datetime.now(timezone.utc):
        return {"healthy": False, "reason": "expired"}
    limit = link.get("limit_bytes", 0)
    used = link.get("used_bytes", 0)
    if limit and used >= limit:
        return {"healthy": False, "reason": "quota_exceeded"}
    return {"healthy": True, "reason": "ok"}


def _parse_dt(raw):
    if not raw:
        return None
    try:
        s = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return None
