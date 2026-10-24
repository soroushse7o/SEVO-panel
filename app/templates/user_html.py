"""Public per-user subscription page, styled to match the panel theme."""

USER_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Dashboard | {label}</title>
<link rel="icon" type="image/png" href="/img/favicon.png">
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
:root{{
  --primary:#ff9d1c; --primary-dim:rgba(255,157,28,0.14);
  --bg:#0c0705; --surface:rgba(24,14,9,0.9);
  --border:rgba(255,157,28,0.14); --border2:rgba(255,140,0,0.28);
  --text:#f2e4d8; --text2:#c9ab8e; --text3:#8a6f5c;
}}
body{{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px;-webkit-font-smoothing:antialiased;}}
.card{{background:var(--surface);border:1px solid var(--border2);border-radius:24px;padding:36px 24px;max-width:420px;width:100%;box-shadow:0 0 40px var(--primary-dim);text-align:center;backdrop-filter:blur(20px);}}
.logo{{width:76px;height:76px;border-radius:50%;box-shadow:0 0 24px var(--primary-dim);margin-bottom:14px;}}
h1{{color:var(--primary);font-size:1.6rem;margin-bottom:6px;font-weight:800;word-break:break-word;}}
.subtitle{{color:var(--text3);font-size:0.88rem;margin-bottom:24px;}}
.info-box{{background:rgba(255,255,255,0.03);border:1px solid var(--border);border-radius:16px;padding:16px;margin-bottom:22px;text-align:left;}}
.row{{display:flex;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.05);font-size:0.94rem;}}
.row:last-of-type{{border-bottom:none;}}
.label{{color:var(--text3);font-weight:600;}}
.value{{color:var(--text);font-weight:700;text-align:right;}}
.progress-bar-bg{{height:8px;background:rgba(255,255,255,0.1);border-radius:4px;margin-top:12px;overflow:hidden;}}
.progress-bar-fill{{height:100%;width:{usage_percent}%;background:{bar_color};border-radius:4px;}}
.progress-text{{font-size:0.78rem;color:var(--text3);margin-top:6px;text-align:right;}}
.qr{{background:#fff;padding:12px;border-radius:16px;display:inline-block;margin-bottom:22px;}}
.qr img{{display:block;border-radius:8px;}}
.btn{{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;padding:14px;background:var(--primary);color:#1a0d04;font-weight:800;border-radius:12px;transition:all 0.2s;margin-bottom:12px;border:none;cursor:pointer;font-family:inherit;font-size:0.98rem;}}
.btn:hover{{filter:brightness(1.08);box-shadow:0 0 20px var(--primary-dim);}}
.btn-outline{{background:transparent;color:var(--primary);border:2px solid var(--border2);}}
.btn-outline:hover{{background:var(--primary-dim);box-shadow:none;}}
.footer{{margin-top:6px;font-size:0.76rem;color:var(--text3);}}
#toast{{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:var(--primary);color:#1a0d04;padding:10px 22px;border-radius:30px;font-weight:700;opacity:0;transition:opacity 0.3s;pointer-events:none;}}
</style>
</head>
<body>
<div class="card">
    <img class="logo" src="/img/logo.png" alt="SE7O-SNA">
    <h1>{label}</h1>
    <div class="subtitle">Secure Subscription Dashboard</div>
    <div class="info-box">
        <div class="row"><span class="label">Status</span><span class="value">{status}</span></div>
        <div class="row"><span class="label">Data Usage</span><span class="value">{used} / {limit}</span></div>
        <div class="progress-bar-bg"><div class="progress-bar-fill"></div></div>
        <div class="progress-text">{usage_percent}% used</div>
        <div class="row"><span class="label">Expiration</span><span class="value">{expiry}</span></div>
    </div>
    <div class="qr">
        <img src="{qr_url}" alt="Scan to import" width="200" height="200">
    </div>
    <button class="btn" onclick="copyToClip('{sub_url}','Subscription link copied')">Copy Subscription Link</button>
    <button class="btn btn-outline" onclick="copyToClip('{vless_link}','VLESS link copied')">Copy Single VLESS Link</button>
    <div class="footer">Scan the QR code with your VPN client to import automatically.</div>
</div>
<div id="toast">Copied</div>
<script>
function copyToClip(text, msg) {{
    const done = () => {{
        const t = document.getElementById('toast');
        t.innerText = msg;
        t.style.opacity = '1';
        setTimeout(() => t.style.opacity = '0', 2200);
    }};
    if (navigator.clipboard && window.isSecureContext) {{
        navigator.clipboard.writeText(text).then(done).catch(() => fallback(text, done));
    }} else {{
        fallback(text, done);
    }}
}}
function fallback(text, done) {{
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try {{ document.execCommand('copy'); done(); }} catch (e) {{}}
    document.body.removeChild(ta);
}}
</script>
</body>
</html>"""
