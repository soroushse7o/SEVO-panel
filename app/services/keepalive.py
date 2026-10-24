"""
Anti-sleep / keep-alive loops.
Two modes: simple (health check) and advanced (spoofed browser requests).
Prevents free-tier providers from sleeping the service.
"""
import asyncio
import secrets
import httpx
from app.config import settings
from app import state


async def simple_loop():
    """Simple keep-alive — just ping the root endpoint."""
    while True:
        await asyncio.sleep(state.keep_alive_interval)
        if not state.keep_alive_enabled or state.keep_alive_mode != "simple":
            continue
        domain = settings.domain
        if domain == "localhost":
            continue
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"https://{domain}/")
                if resp.status_code == 200:
                    pass  # success
        except Exception:
            pass


async def advanced_loop():
    """Advanced keep-alive — spoofed browser headers + cache busting."""
    await asyncio.sleep(30)
    while True:
        if not state.keep_alive_enabled or state.keep_alive_mode != "advanced":
            await asyncio.sleep(state.keep_alive_interval)
            continue

        domain = settings.domain
        port = settings.port
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,fa;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }

        target_urls = []
        if domain and not domain.startswith(("http://", "https://")):
            target_urls.extend([f"https://{domain}/login", f"http://{domain}/login"])
        elif domain:
            target_urls.append(f"{domain}/login")
        target_urls.append(f"http://127.0.0.1:{port}/login")

        async with httpx.AsyncClient(verify=False, timeout=15.0, headers=headers) as client:
            success = False
            for url in target_urls:
                try:
                    final_url = url + ("&" if "?" in url else "?") + f"_nocache={secrets.token_hex(4)}"
                    resp = await client.get(final_url, follow_redirects=True)
                    if resp.status_code == 200:
                        success = True
                        break
                except Exception:
                    pass

        await asyncio.sleep(state.keep_alive_interval)
