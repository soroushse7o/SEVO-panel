"""
Pure utility functions — formatting, validation, time helpers.
No side effects, easy to test in isolation.
"""
import re
import ipaddress
from datetime import datetime, timezone


def fmt_bytes(b: int) -> str:
    if not b or b == 0:
        return "0 B"
    if b >= 1_073_741_824:
        return f"{b / 1_073_741_824:.2f} GB"
    if b >= 1_048_576:
        return f"{b / 1_048_576:.1f} MB"
    if b >= 1024:
        return f"{b / 1024:.1f} KB"
    return f"{b} B"


def fmt_expiry(expires_at: str | None) -> str:
    if not expires_at:
        return "\u221e"
    try:
        now = datetime.now(timezone.utc)
        exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        diff = exp - now
        if diff.total_seconds() <= 0:
            return "Expired"
        days = diff.days
        if days > 0:
            return f"{days}d"
        hours = diff.seconds // 3600
        if hours > 0:
            return f"{hours}h"
        return f"{diff.seconds // 60}m"
    except Exception:
        return "\u221e"


def time_ago(ts: str, lang: str = "en") -> str:
    try:
        then = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
        diff = int((datetime.now(timezone.utc) - then).total_seconds())
        if lang == "fa":
            if diff < 60:
                return "\u0644\u062d\u0638\u0627\u062a\u06cc \u067e\u06cc\u0634"
            if diff < 3600:
                return f"{diff // 60} \u062f\u0642\u06cc\u0642\u0647 \u067e\u06cc\u0634"
            if diff < 86400:
                return f"{diff // 3600} \u0633\u0627\u0639\u062a \u067e\u06cc\u0634"
            return then.strftime("%Y-%m-%d")
        if diff < 60:
            return "Just now"
        if diff < 3600:
            return f"{diff // 60} min ago"
        if diff < 86400:
            return f"{diff // 3600} h ago"
        return then.strftime("%Y-%m-%d")
    except Exception:
        return ts


def parse_size_to_bytes(value: float, unit: str) -> int:
    u = unit.upper()
    if u == "GB":
        return int(value * 1024**3)
    if u == "MB":
        return int(value * 1024**2)
    if u == "KB":
        return int(value * 1024)
    return int(value)


def validate_address(addr: str) -> bool:
    try:
        ipaddress.ip_address(addr.strip("[]"))
        return True
    except ValueError:
        pass
    try:
        ipaddress.ip_network(addr.strip("[]"), strict=False)
        return True
    except ValueError:
        pass
    return bool(re.match(r"^[a-zA-Z0-9\-_.%:]+$", addr))


ESCAPE_MAP = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}


def esc(text: str) -> str:
    if not text:
        return ""
    return "".join(ESCAPE_MAP.get(c, c) for c in str(text))


def format_speed(bps: float) -> str:
    if bps < 1024:
        return f"{bps:.1f} B/s"
    kbps = bps / 1024
    if kbps < 1024:
        return f"{kbps:.1f} KB/s"
    return f"{kbps / 1024:.2f} MB/s"
