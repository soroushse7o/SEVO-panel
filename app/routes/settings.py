"""
Panel settings routes.
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from app.security import require_auth
from app import state
from app.database import execute as db_exec, fetchall, fetchone

router = APIRouter()


SETTING_KEYS = [
    "tg_bot_token", "tg_chat_id", "footer_text", "default_path",
    "log_enabled", "timezone_offset", "default_limit_bytes",
    "default_expiry_days", "default_max_connections",
    "telegram_events", "telegram_interval", "keep_alive_interval",
    "keep_alive_enabled", "keep_alive_mode", "theme_color",
    "telegram_templates_en", "telegram_templates_fa", "telegram_lang",
    "default_lang", "auto_disable_enabled", "telegram_report_enabled",
    "telegram_notify_enabled", "monthly_limit_gb",
]


@router.get("/api/settings")
async def get_settings(_=Depends(require_auth)):
    rows = await fetchall("SELECT key, value FROM settings", "SELECT key, value FROM settings")
    stored = {r["key"]: r["value"] for r in rows}
    return {k: stored.get(k, "") or "" for k in SETTING_KEYS}


@router.post("/api/settings")
async def save_settings(request: Request, _=Depends(require_auth)):
    body = await request.json()
    for k in SETTING_KEYS:
        if k in body:
            val = str(body[k]).strip()
            await db_exec(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                "INSERT INTO settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value = $2",
                (k, val),
            )

    # Update runtime state
    if "log_enabled" in body:
        state.logging_enabled = body["log_enabled"] == "1"
    if "keep_alive_enabled" in body:
        state.keep_alive_enabled = body["keep_alive_enabled"] == "1"
    if "keep_alive_mode" in body:
        state.keep_alive_mode = body["keep_alive_mode"]
    if "keep_alive_interval" in body:
        try:
            state.keep_alive_interval = max(60, int(body["keep_alive_interval"]))
        except Exception:
            pass
    if "timezone_offset" in body:
        try:
            state.timezone_offset = float(body["timezone_offset"])
        except Exception:
            state.timezone_offset = 0.0
    return {"ok": True}


@router.post("/api/settings/reset")
async def reset_settings(_=Depends(require_auth)):
    PROTECTED = {"jwt_secret_key", "admin_password_hash"}
    all_rows = await fetchall("SELECT key FROM settings", "SELECT key FROM settings")
    for row in all_rows:
        if row["key"] not in PROTECTED:
            await db_exec("DELETE FROM settings WHERE key = ?", "DELETE FROM settings WHERE key = $1", (row["key"],))
    state.logging_enabled = True
    state.keep_alive_interval = 300
    state.timezone_offset = 0.0
    state.keep_alive_enabled = True
    state.keep_alive_mode = "simple"
    return {"ok": True}


@router.get("/api/public-settings")
async def public_settings():
    row = await fetchone(
        "SELECT value FROM settings WHERE key = 'footer_text'",
        "SELECT value FROM settings WHERE key = 'footer_text'",
    )
    return {"footer_text": row["value"] if row else ""}


@router.post("/api/telegram/test")
async def test_telegram(request: Request, _=Depends(require_auth)):
    """
    Sends the Telegram test message from the SERVER, not the browser.
    The panel's old Test button called api.telegram.org directly from
    client-side JS, which the browser blocks as a cross-origin request
    (Telegram's API doesn't answer the CORS preflight) -- so the button
    always failed silently with a generic "Error" toast no matter how
    correct the token/chat ID were. Routing it through the backend avoids
    CORS entirely and returns Telegram's actual error message on failure.
    """
    from app.services.telegram import send_test_message

    body = await request.json()
    token = str(body.get("tg_bot_token", "")).strip()
    chat_id = str(body.get("tg_chat_id", "")).strip()
    lang = str(body.get("lang", "en")).strip() or "en"

    if not token or not chat_id:
        raise HTTPException(status_code=400, detail="tg_bot_token and tg_chat_id are required")

    ok, err = await send_test_message(token, chat_id, lang)
    if not ok:
        raise HTTPException(status_code=502, detail=err)
    return {"ok": True}
