"""Panel HTML frontend -- extracted from v1.0.3 monolith."""
PANEL_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>SE7O-SNA Panel</title>
<link rel="icon" type="image/png" href="/img/favicon.png">
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&family=Inter:wght@400;500;600;700&family=Vazirmatn:wght@400;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --primary:#22d3ee; --primary-dim:rgba(34,211,238,0.14);
  --bg:#0b1120; --bg2:#111827; --bg3:#1e293b;
  --surface:rgba(17,24,39,0.85); --surface2:rgba(30,41,59,0.9); --surface3:rgba(51,65,85,0.8);
  --border:rgba(34,211,238,0.12); --border2:rgba(34,211,238,0.30);
  --text:#e2e8f0; --text2:#94a3b8; --text3:#64748b;
  --green:#4ade80; --red:#f87171; --yellow:#fbbf24;
  --header-h:60px; --footer-h:50px;
}
body.light-mode {
  --primary:#c2560a; --primary-dim:rgba(194,86,10,0.14);
  --bg:#fff8f2; --bg2:#ffffff; --bg3:#fbebdd;
  --surface:rgba(255,255,255,0.85); --surface2:rgba(255,255,255,0.9); --surface3:rgba(255,246,237,0.9);
  --border:rgba(0,0,0,0.08); --border2:rgba(0,0,0,0.16);
  --text:#241407; --text2:#5a4130; --text3:#8a7562;
}
body.blue-mode {
  --primary:#3b82f6; --primary-dim:rgba(59,130,246,0.16);
  --bg:#070b16; --bg2:#0c1322; --bg3:#111b30;
  --surface:rgba(17,27,48,0.82); --surface2:rgba(22,34,58,0.9); --surface3:rgba(30,44,74,0.8);
  --border:rgba(59,130,246,0.14); --border2:rgba(59,130,246,0.32);
  --text:#e6edf7; --text2:#a9b8d0; --text3:#6b7d9c;
}
html,body{height:100%; overflow-x:hidden;}
body{font-family:'Inter','Vazirmatn',sans-serif;color:var(--text);display:flex;flex-direction:column;background:var(--bg);transition:background 0.3s,color 0.3s;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;line-height:1.5;}
/* Inline SVG icons – inherit colour via currentColor, identical on every OS */
.ic{width:1.1em;height:1.1em;display:inline-block;vertical-align:-0.18em;flex-shrink:0;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;}
.nav-icon .ic{width:1.25em;height:1.25em;}
.btn-icon .ic{width:1.15em;height:1.15em;}
.status-glass-card .ic{width:1.5rem;height:1.5rem;}
body[dir="rtl"]{direction:rtl;text-align:right}
body[dir="rtl"] .fl, body[dir="rtl"] label {float: right !important;text-align: right !important;margin-bottom: 6px;}
body[dir="rtl"] .fi, body[dir="rtl"] select, body[dir="rtl"] input {direction: ltr !important;text-align: left !important;}
body[dir="rtl"] .glass-btn-group {direction: rtl !important;}
a{text-decoration:none;color:inherit;}
.header{height:var(--header-h);background:var(--surface);border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:center;padding:0 12px;backdrop-filter:blur(20px);position:relative;z-index:101;}
.header-inner{display:flex;align-items:center;justify-content:space-between;width:100%;max-width:1400px;}
.logo{font-family:'Orbitron',sans-serif;font-size:1.6rem;font-weight:900;color:var(--primary);letter-spacing:1px;}
.version-tag{font-size:0.7rem;color:var(--primary);margin-left:6px;font-weight:400;}
.header-nav{display:flex;align-items:center;gap:6px;}
.nav-link{padding:8px 14px;border-radius:12px;color:var(--text3);font-size:0.9rem;font-weight:600;transition:all 0.2s;border:1px solid transparent;background:none;cursor:pointer;font-family:inherit;}
.nav-link:hover{color:var(--primary);border-color:var(--primary-dim);background:var(--primary-dim);}
.nav-link.active{color:var(--primary);background:var(--primary-dim);border-color:var(--primary-dim);backdrop-filter:blur(10px);}
.header-right{display:flex;align-items:center;gap:8px;}
.btn-icon{background:transparent;border:1px solid var(--border);color:var(--text3);border-radius:10px;padding:8px;cursor:pointer;transition:all 0.2s;font-size:1rem;}
.btn-icon:hover{color:var(--primary);border-color:var(--primary);}
.lang-switch{display:flex;gap:2px;background:var(--surface3);border-radius:10px;padding:2px;}
.lang-btn{padding:5px 10px;border:none;background:transparent;color:var(--text3);font-size:0.8rem;font-weight:700;border-radius:8px;cursor:pointer;font-family:inherit;}
.lang-btn.active{background:var(--primary);color:#000;}
.hamburger{display:none;background:transparent;border:1px solid var(--border);color:var(--text3);font-size:1.8rem;cursor:pointer;padding:4px 10px;border-radius:10px;}
.main{flex:1;min-height:calc(100vh - var(--header-h) - var(--footer-h));padding:20px 20px;overflow-y:auto;overflow-x:hidden;}
.page{display:none;animation:pgIn .35s ease}
.page.active{display:block}
@keyframes pgIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
.page-header{margin-bottom:16px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;}
.page-title{font-size:1.3rem;font-weight:700;color:var(--primary);letter-spacing:.04em}
.page-title[data-fa]{font-family:'Vazirmatn';}
.page-sub{font-size:0.9rem;color:var(--text3);margin-top:4px}
.stats-row{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}
.stat-card{background:var(--surface2);border:1px solid var(--border);border-radius:16px;padding:20px;position:relative;overflow:hidden;transition:all 0.25s;backdrop-filter:blur(12px);}
.stat-card:hover{border-color:var(--border2);transform:translateY(-2px);box-shadow:0 0 25px var(--primary-dim);}
.stat-label{font-size:0.75rem;color:var(--text3);font-weight:700;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px}
.stat-val{font-size:1.5rem;font-weight:700;color:var(--text);}
.stat-unit{font-size:0.9rem;font-weight:400;color:var(--text3)}
.card{background:var(--surface2);border:1px solid var(--border);border-radius:16px;padding:20px;margin-bottom:12px;transition:all 0.25s;backdrop-filter:blur(10px);}
.card-hd{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.card-title{font-size:1rem;font-weight:600;color:var(--text);}
.chart-container{height:200px;width:100%}
.btn{font-family:inherit;font-size:0.9rem;font-weight:700;border-radius:10px;padding:6px 16px;cursor:pointer;display:inline-flex;align-items:center;gap:4px;border:none;transition:all 0.2s;}
.btn-primary{background:linear-gradient(135deg,#39ff14,#1a8c1a);color:#000;box-shadow:0 0 16px rgba(57,255,20,0.3)}
.btn-primary:hover{filter:brightness(1.2);box-shadow:0 0 24px rgba(57,255,20,0.5)}
.btn-outline{background:var(--surface3);color:var(--text);border:1px solid var(--border)}
.btn-danger{background:rgba(248,113,113,0.1);color:var(--red);border:1px solid rgba(248,113,113,0.2)}
.btn-sm{padding:5px 12px;font-size:0.8rem}
.tbl-wrap{overflow-x:auto}
.tbl{width:100%;border-collapse:collapse;table-layout:auto}
.tbl th, .tbl td{text-align:center; font-size:0.8rem; font-weight:700; color:var(--text3); padding:10px; text-transform:uppercase; border-bottom:1px solid var(--border); background:var(--surface3)}
.tbl td{padding:10px;border-bottom:1px solid var(--border);font-size:0.85rem;word-break:break-word;font-weight:400;text-transform:none;background:none}
#inbound-table th:first-child, #inbound-table td:first-child { width: 36px; }
.tbl th:nth-child(2) { min-width: 80px; }
.tbl th:nth-child(4), .tbl td:nth-child(4) { text-align: left; width: 18%; word-break: keep-all; }
.tbl th:nth-child(8), .tbl td:nth-child(8) { min-width: 140px; }
.tbl input[type="checkbox"] { width: 15px; height: 15px; }
.time-col { white-space: nowrap; min-width: 90px; text-align: left; }
.tag{display:inline-flex;align-items:center;padding:2px 6px;border-radius:4px;font-size:0.7rem;font-weight:800;text-transform:uppercase}
.tag-vless{background:var(--primary-dim);color:var(--primary);border:1px solid var(--border)}
.tag-on{background:rgba(74,222,128,0.1);color:var(--green);border:1px solid rgba(74,222,128,0.2)}
.tag-off{background:rgba(248,113,113,0.1);color:var(--red);border:1px solid rgba(248,113,113,0.2)}
.pill{display:flex;align-items:center;gap:6px;font-size:0.8rem}
.pill-used{color:var(--text);font-weight:600}
.pill-bar{flex:1;height:4px;background:var(--border);border-radius:2px;min-width:30px}
.pill-fill{height:100%;border-radius:2px;transition:width 0.4s}
.pill-lim{color:var(--text3);font-size:0.75rem}
@media (max-width: 600px) {
  .pill { flex-direction: column; gap: 2px; align-items: flex-start; }
  .pill-bar { width: 100%; height: 6px; min-width: 0; }
  .pill-used, .pill-lim { font-size: 0.75rem; }
}
.toggle{width:40px;height:22px;border-radius:11px;background:var(--surface3);position:relative;cursor:pointer;transition:all 0.3s;border:2px solid var(--border);flex-shrink:0}
.toggle::after{content:'';position:absolute;width:16px;height:16px;border-radius:50%;background:var(--text3);top:1px;left:2px;transition:all 0.3s}
.toggle.on{background:var(--green);border-color:var(--green);box-shadow:0 0 12px rgba(74,222,128,0.4)}
.toggle.on::after{left:20px;background:#fff}
.sys-bar{height:6px;background:var(--border);border-radius:3px;overflow:hidden}
.sys-fill{height:100%;border-radius:3px;transition:width 0.4s}
.sl-item{display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--border)}
.sl-k{color:var(--text3);font-size:0.9rem}
.sl-v{color:var(--text);font-weight:600;font-size:0.9rem}
.fg{display:flex;flex-direction:column;gap:5px;margin-bottom:16px}
.fl{font-size:0.8rem;font-weight:700;color:var(--text2);text-transform:uppercase}
.fi,.fs{padding:10px 14px;border-radius:10px;border:1px solid var(--border);font-family:inherit;font-size:0.9rem;outline:none;color:var(--text);background:var(--surface);transition:all 0.2s}
.fi:focus,.fs:focus{border-color:var(--primary);box-shadow:0 0 0 3px var(--primary-dim)}
.act-btn{font-family:inherit;font-size:0.7rem;font-weight:700;padding:3px 6px;border-radius:6px;cursor:pointer;border:1px solid;transition:all 0.18s;display:inline-flex;align-items:center;gap:3px;background:transparent}
.act-copy{color:var(--primary);border-color:var(--border)}
.act-sub{color:var(--green);border-color:rgba(74,222,128,0.2)}
.act-qr{color:#a78bfa;border-color:rgba(167,139,250,0.2)}
.act-edit{color:var(--yellow);border-color:rgba(251,191,36,0.2)}
.act-del{color:var(--red);border-color:rgba(248,113,113,0.2)}
.toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%) translateY(16px);background:var(--surface);color:var(--text);border:1px solid var(--border2);border-radius:14px;padding:14px 28px;font-size:0.9rem;font-weight:600;opacity:0;transition:all 0.3s;z-index:999;backdrop-filter:blur(24px);box-shadow:0 0 30px var(--primary-dim)}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.mo{position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:200;display:none;align-items:center;justify-content:center;backdrop-filter:blur(8px)}
.mo.show{display:flex}
.mo-box{background:var(--surface2);border:1px solid var(--border2);border-radius:24px;padding:24px;width:100%;max-width:480px;max-height:90vh;overflow-y:auto;box-shadow:0 0 40px var(--primary-dim);backdrop-filter:blur(20px);position:relative;}
.mo-title{font-size:1.2rem;font-weight:700;margin-bottom:18px;color:var(--primary)}
.mo-close{position:absolute;top:12px;right:12px;background:var(--surface3);border:1px solid var(--border);color:var(--text3);width:32px;height:32px;border-radius:10px;cursor:pointer;}
.qr-box{text-align:center;padding:20px;background:var(--surface3);border-radius:16px;border:1px solid var(--border);margin-top:10px}
.qr-box img{max-width:180px;border-radius:12px;border:3px solid var(--border);box-shadow:0 0 15px var(--primary-dim)}
.footer{height:var(--footer-h);display:flex;align-items:center;justify-content:center;font-size:0.8rem;color:var(--text3);border-top:1px solid var(--border);background:var(--surface);backdrop-filter:blur(10px);margin-top:auto;}
.footer-inner { display: flex; align-items: center; justify-content: center; gap: 16px; flex-wrap: wrap; }
.footer-inner a { color: var(--primary); text-decoration: none; font-weight: 600; }
.footer-inner a:hover { text-shadow: 0 0 8px var(--primary); }
textarea.fi{resize:vertical;min-height:90px;}
.chip{padding:6px 12px;border-radius:8px;font-size:0.8rem;font-weight:700;color:var(--text3);cursor:pointer;border:none;background:none;font-family:inherit;transition:all 0.18s;}
.chip.active{background:var(--primary);color:#000;}
.pill-group{display:flex;flex-wrap:wrap;gap:6px;}
.pill-btn{padding:6px 12px;border-radius:20px;border:1px solid var(--border);background:var(--surface3);color:var(--text3);cursor:pointer;font-size:0.8rem;font-weight:600;transition:all 0.2s;font-family:inherit;backdrop-filter:blur(4px);}
.pill-btn:hover{border-color:var(--primary);color:var(--primary);}
.pill-btn.active{background:var(--primary-dim);color:var(--primary);border-color:var(--primary);box-shadow:0 0 10px var(--primary-dim);}
.adv-toggle{cursor:pointer;color:var(--primary);font-weight:600;margin-bottom:10px;display:inline-flex;align-items:center;gap:4px;border:none;background:none;font-size:0.85rem;font-family:inherit;}
.adv-section{display:none;}
.addr-list-scroll{max-height:300px;overflow-y:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--border);border-radius:12px;padding:6px;}
.logs-table-container {max-height: 350px; overflow-y: auto; -webkit-overflow-scrolling: touch;}
.mobile-nav{display:none; position:fixed; bottom:0; left:0; right:0; background:var(--surface); border-top:1px solid var(--border); z-index:9999; backdrop-filter:blur(20px); padding-bottom:env(safe-area-inset-bottom);}
.mobile-nav .nav-items{display:flex; padding:8px 6px; justify-content: space-around; align-items: center; width: 100%;}
.mobile-nav .nav-item{flex:1; display:flex; flex-direction:column; align-items:center; gap:4px; padding:2px; color:var(--text3); font-size:0.65rem; cursor:pointer; transition:all 0.2s;}
.glass-btn-group {display: flex;flex-wrap: wrap;gap: 8px;background: rgba(255, 255, 255, 0.03);border: 1px solid var(--border);padding: 4px;border-radius: 12px;backdrop-filter: blur(10px);}
.glass-btn {flex: 1;min-width: 80px;background: transparent;border: none;color: var(--text3);padding: 8px 12px;border-radius: 8px;cursor: pointer;font-weight: 600;font-family: inherit;font-size: 0.85rem;transition: all 0.3s;}
.glass-btn.active {background: var(--primary);color: #000 !important;box-shadow: 0 0 15px var(--primary-dim);}
.glass-btn:hover:not(.active) {background: rgba(255, 255, 255, 0.08);color: var(--text);}
.status-cards-grid {display: grid;grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));gap: 10px;margin-top: 10px;}
.status-glass-card {padding: 14px;border-radius: 12px;text-align: center;cursor: pointer;font-weight: 700;transition: all 0.3s;user-select: none;display: flex;flex-direction: column;align-items: center;gap: 6px;font-size: 0.8rem;}
.status-glass-card.inactive {background: rgba(255, 255, 255, 0.02);border: 1px solid var(--border);color: var(--text3);}
.status-glass-card.active {background: rgba(57, 255, 20, 0.1);border: 1px solid rgba(57, 255, 20, 0.3);color: var(--primary);box-shadow: 0 0 12px var(--primary-dim);}
.railway-hl {background: rgba(168, 85, 247, 0.15) !important;color: #d8b4fe !important;border: 1px solid #a855f7 !important;font-weight: 800;box-shadow: 0 0 10px rgba(168, 85, 247, 0.2);}
@media(max-width:768px){
  .header .header-nav{display:none;}
  .mobile-nav{display:block;}
  .main{padding-bottom:100px;} 
  .footer{display:none;}
  .header{justify-content:center;}
  .logo{font-size:1.3rem;}
  .version-tag{font-size:0.6rem;}
  .header-right{gap:4px;}
  .btn-icon{padding:6px;}
  .lang-btn{padding:4px 8px; font-size:0.7rem;}
  .glass-btn {min-width:60px; padding:6px; font-size:0.75rem;}
}
@media(max-width:500px){
  .stats-row{grid-template-columns:1fr;}
  .glass-btn-group {flex-direction: column;}
  .glass-btn {width: 100%;}
}
.mt-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px;}
.mt-kv{display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-bottom:1px solid var(--border);font-size:0.9rem;}
.mt-kv:last-child{border-bottom:none;}
.mt-kv span{color:var(--text3);}
.mt-kv b{color:var(--text);font-weight:700;text-align:right;word-break:break-all;}
</style>
</head>
<body>
<svg width="0" height="0" style="position:absolute" aria-hidden="true">
  <symbol id="ic-dashboard" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/></symbol>
  <symbol id="ic-inbounds" viewBox="0 0 24 24"><path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M1.42 9a16 16 0 0 1 21.16 0"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><line x1="12" y1="20" x2="12" y2="20"/><circle cx="12" cy="20" r="1"/></symbol>
  <symbol id="ic-transports" viewBox="0 0 24 24"><path d="M3 12h18"/><path d="M3 6h18"/><path d="M3 18h18"/><circle cx="7" cy="12" r="1.5"/><circle cx="14" cy="6" r="1.5"/><circle cx="11" cy="18" r="1.5"/></symbol>
  <symbol id="ic-link" viewBox="0 0 24 24"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></symbol>
  <symbol id="ic-logs" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/></symbol>
  <symbol id="ic-telegram" viewBox="0 0 24 24"><path d="M21.5 3.5 3 11l5 2 2 6 3-4 5 4z"/><path d="M21.5 3.5 9 13"/></symbol>
  <symbol id="ic-settings" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></symbol>
  <symbol id="ic-moon" viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></symbol>
  <symbol id="ic-sun" viewBox="0 0 24 24"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></symbol>
  <symbol id="ic-copy" viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></symbol>
  <symbol id="ic-qr" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><line x1="14" y1="14" x2="14" y2="21"/><line x1="21" y1="14" x2="21" y2="21"/><line x1="17.5" y1="17.5" x2="17.5" y2="17.5"/></symbol>
  <symbol id="ic-edit" viewBox="0 0 24 24"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4z"/></symbol>
  <symbol id="ic-trash" viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></symbol>
  <symbol id="ic-refresh" viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></symbol>
  <symbol id="ic-unplug" viewBox="0 0 24 24"><path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/><line x1="2" y1="22" x2="22" y2="22"/></symbol>
  <symbol id="ic-paperclip" viewBox="0 0 24 24"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></symbol>
  <symbol id="ic-close" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></symbol>
  <symbol id="ic-dice" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8.5" cy="8.5" r="1.2" fill="currentColor"/><circle cx="15.5" cy="15.5" r="1.2" fill="currentColor"/><circle cx="12" cy="12" r="1.2" fill="currentColor"/><circle cx="15.5" cy="8.5" r="1.2" fill="currentColor"/><circle cx="8.5" cy="15.5" r="1.2" fill="currentColor"/></symbol>
  <symbol id="ic-menu" viewBox="0 0 24 24"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></symbol>
  <symbol id="ic-github" viewBox="0 0 24 24"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/></symbol>
  <symbol id="ic-bolt" viewBox="0 0 24 24"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></symbol>
  <symbol id="ic-ban" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></symbol>
  <symbol id="ic-bell" viewBox="0 0 24 24"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></symbol>
  <symbol id="ic-bot" viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><line x1="8" y1="16" x2="8" y2="16"/><line x1="16" y1="16" x2="16" y2="16"/></symbol>
  <symbol id="ic-check" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></symbol>
  <symbol id="ic-x" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></symbol>
  <symbol id="ic-users" viewBox="0 0 24 24"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></symbol>
  <symbol id="ic-json" viewBox="0 0 24 24"><path d="M8 3H6a2 2 0 0 0-2 2v4a2 2 0 0 1-2 2 2 2 0 0 1 2 2v4a2 2 0 0 0 2 2h2"/><path d="M16 3h2a2 2 0 0 1 2 2v4a2 2 0 0 0 2 2 2 2 0 0 0-2 2v4a2 2 0 0 1-2 2h-2"/><line x1="9" y1="9" x2="9" y2="15"/><line x1="15" y1="9" x2="15" y2="15"/></symbol>
</svg>
<div class="toast" id="toast"></div>
<div id="login-page" style="display:none;width:100%">
  <div style="display:flex;align-items:center;justify-content:center;min-height:100vh;">
    <div style="background:var(--surface2);border:1px solid var(--border2);border-radius:28px;padding:48px 40px;width:100%;max-width:400px;box-shadow:0 0 40px var(--primary-dim);backdrop-filter:blur(20px);">
      <div style="text-align:center;margin-bottom:32px;">
        <img src="/img/logo.png" alt="SE7O-SNA" width="120" height="120" style="border-radius:50%;box-shadow:0 0 30px var(--primary-dim);">
        <div style="font-family:'Orbitron',sans-serif;font-size:1.5rem;font-weight:900;color:var(--primary);margin-top:12px;display:flex;align-items:center;justify-content:center;gap:8px;">
          SE7O-SNA Panel <span style="font-size:0.8rem; font-family:'Inter'; color:var(--bg); background:var(--primary); padding:2px 6px; border-radius:4px;">V 3.0.4</span>
        </div>
        <div style="font-size:1rem;color:var(--text3);margin-top:8px;" data-en="Enter your credentials" data-fa="نام کاربری و رمز عبور را وارد کنید">Enter your credentials</div>
        <div id="login-custom-message" style="margin-top:20px; text-align:center; color:var(--text3); font-size:0.9rem;"></div>
      </div>
      <div class="fg"><label class="fl">USERNAME</label><input class="fi" type="text" id="login-user" placeholder="admin" onkeydown="if(event.key==='Enter')doLogin()"></div>
      <div class="fg"><label class="fl">PASSWORD</label><input class="fi" type="password" id="login-pw" placeholder="••••••••" onkeydown="if(event.key==='Enter')doLogin()"></div>
      <button class="btn btn-primary" onclick="doLogin()" style="width:100%;justify-content:center;padding:14px;margin-top:16px;">LOGIN</button>
      <div id="login-err" style="color:var(--red);font-size:0.9rem;margin-top:10px;text-align:center;display:none">Invalid password</div>
      <div style="margin-top:20px; text-align:center; display:flex; justify-content:center; gap:20px;">
        <a href="https://github.com/SE7O-SNA" target="_blank" style="color:var(--text3); text-decoration:none; font-size:0.9rem; display:inline-flex; align-items:center; gap:6px;" title="GitHub"><svg class="ic"><use href="#ic-github"/></svg> GitHub</a>
        <a href="https://t.me/SE7O_SNA" target="_blank" style="color:var(--text3); text-decoration:none; font-size:0.9rem; display:inline-flex; align-items:center; gap:6px;" title="Telegram"><svg class="ic"><use href="#ic-telegram"/></svg> Telegram</a>
      </div>
    </div>
  </div>
</div>
<div id="dashboard-page" style="display:none;width:100%">
  <header class="header">
    <div class="header-inner">
      <div style="display:flex;align-items:center;gap:16px;">
        <img src="/img/logo.png" alt="SE7O-SNA" style="height:32px;width:32px;border-radius:50%;vertical-align:middle;"> <span class="logo">SE7O-SNA</span><span class="version-tag">v3.0.4</span>
        <span id="panel-clock" style="font-weight:600;color:var(--primary);margin-left:8px;font-size:0.9rem;"></span>
        <nav class="header-nav" id="mainNav">
          <button class="nav-link active" data-page="dashboard"><svg class="ic"><use href="#ic-dashboard"/></svg> <span data-en="Dashboard" data-fa="داشبورد">Dashboard</span></button>
          <button class="nav-link" data-page="inbounds"><svg class="ic"><use href="#ic-inbounds"/></svg> <span data-en="Inbounds" data-fa="اینباندها">Inbounds</span></button>
          <button class="nav-link" data-page="addresses"><svg class="ic"><use href="#ic-link"/></svg> <span data-en="Clean IP" data-fa="آی‌پی تمیز">Clean IP</span></button>
          <button class="nav-link" data-page="logs"><svg class="ic"><use href="#ic-logs"/></svg> <span data-en="Logs" data-fa="لاگ‌ها">Logs</span></button>
          <button class="nav-link" data-page="telegram"><svg class="ic"><use href="#ic-telegram"/></svg> <span data-en="Telegram" data-fa="تلگرام">Telegram</span></button>
          <button class="nav-link" data-page="aether"><svg class="ic"><use href="#ic-bolt"/></svg> <span data-en="Aether" data-fa="Aether">Aether</span></button>
          <button class="nav-link" data-page="mtproxy"><svg class="ic"><use href="#ic-bolt"/></svg> <span data-en="MTProxy" data-fa="ام‌تی پراکسی">MTProxy</span></button>
          <button class="nav-link" data-page="settings"><svg class="ic"><use href="#ic-settings"/></svg> <span data-en="Settings" data-fa="تنظیمات">Settings</span></button>
        </nav>
      </div>
      <div class="header-right">
        <button class="btn btn-outline btn-sm" onclick="randomInbound()" data-en="+ Random User" data-fa="+ کاربر تصادفی">+ Random User</button>
        <div class="lang-switch">
          <button class="lang-btn lang-en active" onclick="setLang('en')">EN</button>
          <button class="lang-btn lang-fa" onclick="setLang('fa')">FA</button>
        </div>
        <button class="btn-icon" onclick="toggleTheme()" title="Toggle theme"><svg class="ic"><use href="#ic-moon"/></svg></button>
        <button class="btn btn-danger btn-sm" onclick="doLogout()" data-en="Logout" data-fa="خروج">Logout</button>
        <button class="hamburger" id="hamburger-btn"><svg class="ic"><use href="#ic-menu"/></svg></button>
      </div>
    </div>
  </header>
  <main class="main">
    <section class="page active" id="page-dashboard">
      <div class="page-header"><div><div class="page-title" data-en="Dashboard" data-fa="داشبورد">Dashboard</div><div class="page-sub" id="last-up">–</div></div></div>
      <div class="stats-row">
        <div class="stat-card"><div class="stat-label" data-en="Traffic" data-fa="ترافیک">Traffic</div><div class="stat-val" id="sv-traffic">–<span class="stat-unit"> MB</span></div></div>
        <div class="stat-card"><div class="stat-label" data-en="Requests" data-fa="درخواست‌ها">Requests</div><div class="stat-val" id="sv-requests">–</div></div>
        <div class="stat-card"><div class="stat-label" data-en="Uptime" data-fa="آپتایم">Uptime</div><div class="stat-val" id="sv-uptime" style="font-size:1.2rem;">–</div></div>
        <div class="stat-card"><div class="stat-label" data-en="Disk Free" data-fa="فضای دیسک">Disk Free</div><div class="stat-val" id="sv-disk">–<span class="stat-unit"> GB</span></div></div>
      </div>
      <div class="stats-row">
        <div class="stat-card"><div class="stat-label" data-en="Download Speed" data-fa="سرعت دانلود">Download Speed</div><div class="stat-val" id="sv-down-speed">–<span class="stat-unit"> KB/s</span></div></div>
        <div class="stat-card"><div class="stat-label" data-en="Upload Speed" data-fa="سرعت آپلود">Upload Speed</div><div class="stat-val" id="sv-up-speed">–<span class="stat-unit"> KB/s</span></div></div>
        <div class="stat-card"><div class="stat-label" data-en="Monthly Usage" data-fa="مصرف ماهانه">Monthly Usage</div><div class="stat-val" id="sv-monthly">–<span class="stat-unit"> GB</span></div></div>
        <div class="stat-card" style="font-size:0.8rem;">
          <div class="stat-label" data-en="Settings Status" data-fa="وضعیت تنظیمات">Settings Status</div>
          <div class="status-cards-grid" id="settings-status">
            <div class="status-glass-card inactive" id="st-log" data-en="Logging" data-fa="لاگ"><svg class="ic"><use href="#ic-logs"/></svg> <span>Logging</span></div>
            <div class="status-glass-card inactive" id="st-auto" data-en="Auto Disable" data-fa="غیرفعال‌سازی"><svg class="ic"><use href="#ic-ban"/></svg> <span>Auto Disable</span></div>
            <div class="status-glass-card inactive" id="st-tgrep" data-en="TG Reports" data-fa="گزارش تلگرام"><svg class="ic"><use href="#ic-telegram"/></svg> <span>TG Reports</span></div>
            <div class="status-glass-card inactive" id="st-tgnot" data-en="TG Notify" data-fa="اعلان تلگرام"><svg class="ic"><use href="#ic-bell"/></svg> <span>TG Notify</span></div>
            <div class="status-glass-card inactive" id="st-bot" data-en="Bot" data-fa="ربات"><svg class="ic"><use href="#ic-bot"/></svg> <span>Bot</span></div>
          </div>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
        <div class="card"><div class="card-hd"><span class="card-title" data-en="CPU" data-fa="پردازنده">CPU</span><span id="cpu-v" style="font-weight:700;color:var(--primary);">–%</span></div><div class="sys-bar"><div class="sys-fill" id="cpu-b" style="background:var(--primary);width:0%"></div></div></div>
        <div class="card"><div class="card-hd"><span class="card-title" data-en="Memory" data-fa="حافظه">Memory</span><span id="mem-v" style="font-weight:700;color:var(--green);">–%</span></div><div class="sys-bar"><div class="sys-fill" id="mem-b" style="background:var(--green);width:0%"></div></div></div>
      </div>
      <div class="card"><div class="card-hd"><span class="card-title" data-en="Hourly Traffic" data-fa="ترافیک ساعتی">Hourly Traffic</span></div><div class="chart-container"><canvas id="tc"></canvas></div></div>
      <div class="card"><div class="card-hd"><span class="card-title" data-en="Usage Distribution" data-fa="توزیع مصرف">Usage Distribution</span></div><div class="chart-container"><canvas id="doughnut-chart"></canvas></div></div>
      <div class="card"><div class="card-hd"><span class="card-title" data-en="Live Speed" data-fa="سرعت زنده">Live Speed</span></div><div class="chart-container"><canvas id="speed-chart"></canvas></div></div>
      <div class="card">
        <div class="card-hd"><span class="card-title" data-en="Recent Activity" data-fa="فعالیت‌های اخیر">Recent Activity</span></div>
        <div class="tbl-wrap"><table class="tbl" id="login-logs-table"><thead><tr><th class="time-col" data-en="Time" data-fa="زمان">Time</th><th data-en="IP / Agent" data-fa="آی‌پی / عامل کاربر">IP / Agent</th><th data-en="Status" data-fa="وضعیت">Status</th></tr></thead><tbody id="login-logs-tbody"></tbody></table></div>
      </div>
    </section>
    <section class="page" id="page-inbounds">
      <div class="page-header">
        <div><div class="page-title" data-en="Inbounds" data-fa="اینباندها">Inbounds</div><div class="page-sub" data-en="Manage VLESS Configs" data-fa="مدیریت کانفیگ‌های VLESS">Manage VLESS Configs</div></div>
        <div style="display:flex;gap:6px;">
          <button class="btn btn-primary" onclick="showAddMo()" data-en="+ Create" data-fa="+ ایجاد">+ Create</button>
          <button class="btn btn-outline btn-sm" onclick="exportLinks()" data-en="Export" data-fa="خروجی">Export</button>
          <button class="btn btn-outline btn-sm" onclick="document.getElementById('import-file').click()" data-en="Import" data-fa="ورودی">Import</button>
          <input type="file" id="import-file" style="display:none" accept=".json" onchange="importLinks(this)">
        </div>
      </div>
      <div style="display:flex;gap:10px;margin-bottom:16px;">
        <input id="srch" placeholder="Search…" oninput="filterLinks()" class="fi" style="flex:1;">
        <button class="chip active" data-filter="all" data-en="All" data-fa="همه" onclick="setFilter('all',this)">All</button>
        <button class="chip" data-filter="active" data-en="Active" data-fa="فعال" onclick="setFilter('active',this)">Active</button>
        <button class="chip" data-filter="off" data-en="Off" data-fa="خاموش" onclick="setFilter('off',this)">Off</button>
      </div>
      <div style="display:flex;gap:6px;margin-bottom:10px;">
        <button class="btn btn-outline btn-sm" onclick="batchAction('activate')" data-en="Activate Selected" data-fa="فعال‌سازی انتخاب">Activate Selected</button>
        <button class="btn btn-outline btn-sm" onclick="batchAction('deactivate')" data-en="Deactivate Selected" data-fa="غیرفعال‌سازی انتخاب">Deactivate Selected</button>
        <button class="btn btn-outline btn-sm" onclick="batchAction('reset_usage')" data-en="Reset Usage Selected" data-fa="بازنشانی مصرف انتخاب">Reset Usage Selected</button>
        <button class="btn btn-danger btn-sm" onclick="batchAction('delete')" data-en="Delete Selected" data-fa="حذف انتخاب">Delete Selected</button>
      </div>
      <div class="card" style="padding:0;overflow:hidden;">
        <div class="tbl-wrap"><table class="tbl" id="inbound-table"><thead><tr><th><input type="checkbox" id="select-all" onchange="toggleSelectAll()"></th><th data-sort="label" onclick="sortLinks('label')"><span data-en="Name" data-fa="نام">Name</span> ↕</th><th data-en="Type" data-fa="نوع">Type</th><th data-sort="used_bytes" onclick="sortLinks('used_bytes')"><span data-en="Usage" data-fa="مصرف">Usage</span> ↕</th><th data-en="Conns" data-fa="اتصالات">Conns</th><th data-en="Connections" data-fa="اتصالات فعال">Connections</th><th data-sort="expires_at" onclick="sortLinks('expires_at')"><span data-en="Expiry" data-fa="انقضا">Expiry</span> ↕</th><th data-en="Status" data-fa="وضعیت">Status</th><th data-en="Actions" data-fa="عملیات">Actions</th></tr></thead><tbody id="ltb"></tbody></table></div>
        <div class="empty" id="lempty" style="display:none;padding:30px;">No inbounds found</div>
      </div>
    </section>
    <section class="page" id="page-addresses">
      <div class="page-header"><div class="page-title" data-en="Clean IP" data-fa="آی‌پی تمیز">Clean IP</div></div>
      <div class="card">
        <div class="fg"><label class="fl" data-en="Add Addresses (one per line)" data-fa="افزودن آدرس (هر خط یک)">Add Addresses (one per line)</label><textarea class="fi" id="batch-addrs" rows="4" placeholder="8.8.8.8
example.com"></textarea></div>
        <button class="btn btn-primary" onclick="addBatchAddrs()" data-en="Add All" data-fa="افزودن همه">Add All</button>
        <button class="btn btn-danger btn-sm" onclick="deleteAllAddrs()" style="margin-left:6px;" data-en="Delete All" data-fa="حذف همه">Delete All</button>
        <button class="btn btn-danger btn-sm" onclick="bulkDeleteAddrs()" style="margin-left:6px;" data-en="Delete Selected" data-fa="حذف انتخاب‌شده">Delete Selected</button>
        <div class="addr-list-scroll" id="addr-list" style="margin-top:16px;"></div>
      </div>
    </section>
    <section class="page" id="page-logs">
      <div class="page-header"><div class="page-title" data-en="Logs" data-fa="لاگ‌ها">Logs</div></div>
      <div style="display:flex;gap:10px;margin-bottom:16px;">
        <input id="log-search" placeholder="Search logs…" oninput="filterLogs()" class="fi" style="flex:1;">
        <button class="btn btn-outline btn-sm" onclick="clearLogSearch()"><svg class="ic"><use href="#ic-close"/></svg></button>
      </div>
      <div class="card" style="padding:0;overflow:hidden;">
        <div class="logs-table-container">
          <table class="tbl">
            <thead><tr><th>#</th><th data-en="Time (UTC)" data-fa="زمان (UTC)">Time (UTC)</th><th data-en="Type" data-fa="نوع">Type</th><th data-en="Event" data-fa="رویداد">Event</th></tr></thead>
            <tbody id="logs-tbody"></tbody>
          </table>
        </div>
        <div class="empty" id="logs-empty" style="display:none;padding:30px;">No events recorded</div>
      </div>
      <div style="display:flex;gap:6px;margin-top:8px;">
        <button class="btn btn-outline btn-sm" onclick="fetchLogSize()"><svg class="ic"><use href="#ic-logs"/></svg> <span data-en="Log Size" data-fa="حجم لاگ">Log Size</span></button>
        <button class="btn btn-danger btn-sm" onclick="clearLogs()"><svg class="ic"><use href="#ic-trash"/></svg> <span data-en="Clear Logs" data-fa="پاک‌سازی لاگ‌ها">Clear Logs</span></button>
      </div>
    </section>
    <section class="page" id="page-mtproxy">
      <div class="page-header">
        <div>
          <div class="page-title" data-en="Telegram MTProxy" data-fa="پراکسی تلگرام">Telegram MTProxy</div>
          <div class="page-sub" data-en="MTProto proxy running beside the panel" data-fa="پراکسی MTProto در کنار پنل">MTProto proxy running beside the panel</div>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <button class="btn btn-sm" onclick="loadMtproxy()"><svg class="ic"><use href="#ic-refresh"/></svg> <span data-en="Refresh" data-fa="بازخوانی">Refresh</span></button>
          <button class="btn btn-sm" onclick="restartMtproxy()"><svg class="ic"><use href="#ic-bolt"/></svg> <span data-en="Restart" data-fa="ریستارت">Restart</span></button>
        </div>
      </div>

      <div id="mt-warn" class="card" style="display:none;border-color:#e0a33e;margin-bottom:14px;">
        <div style="font-weight:700;color:#e0a33e;margin-bottom:6px;" data-en="TCP Proxy not detected" data-fa="تی‌سی‌پی پراکسی پیدا نشد">TCP Proxy not detected</div>
        <div style="font-size:0.86rem;line-height:1.7;color:var(--text2)" data-en="Open your Railway service &rarr; Settings &rarr; Networking &rarr; TCP Proxy and enter the internal port shown below. Railway then returns a public domain and port, which appear here automatically." data-fa="در Railway به Settings و سپس Networking و TCP Proxy بروید و پورت داخلی زیر را وارد کنید. Railway یک دامنه و پورت عمومی می‌دهد که خودکار اینجا نمایش داده می‌شود.">Open your Railway service &rarr; Settings &rarr; Networking &rarr; TCP Proxy and enter the internal port shown below. Railway then returns a public domain and port, which appear here automatically.</div>
      </div>

      <div class="mt-grid">
        <div class="card">
          <div class="mo-title" data-en="Status" data-fa="وضعیت" style="margin-bottom:14px;">Status</div>
          <div class="mt-kv"><span data-en="Process" data-fa="پروسه">Process</span><b id="mt-running">-</b></div>
          <div class="mt-kv"><span data-en="Internal port" data-fa="پورت داخلی">Internal port</span><b id="mt-bind">-</b></div>
          <div class="mt-kv"><span data-en="Public endpoint" data-fa="آدرس عمومی">Public endpoint</span><b id="mt-endpoint">-</b></div>
          <div class="mt-kv"><span data-en="Fronting domain" data-fa="دامنه پوششی">Fronting domain</span><b id="mt-front">-</b></div>
          <div class="mt-kv"><span data-en="Restarts" data-fa="تعداد ریستارت">Restarts</span><b id="mt-restarts">-</b></div>
          <div class="mt-kv" id="mt-err-row" style="display:none;"><span data-en="Error" data-fa="خطا">Error</span><b id="mt-err" style="color:#f87171"></b></div>
        </div>

        <div class="card">
          <div class="mo-title" data-en="Connection" data-fa="اتصال" style="margin-bottom:14px;">Connection</div>
          <div class="fg"><label class="fl" data-en="Secret" data-fa="سکرت">Secret</label><input class="fi" id="mt-secret" readonly></div>
          <div class="fg"><label class="fl" data-en="Telegram link" data-fa="لینک تلگرام">Telegram link</label><input class="fi" id="mt-link" readonly></div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;">
            <button class="btn btn-primary btn-sm" onclick="copyMt('mt-link')"><svg class="ic"><use href="#ic-copy"/></svg> <span data-en="Copy link" data-fa="کپی لینک">Copy link</span></button>
            <button class="btn btn-sm" onclick="copyMt('mt-secret')"><svg class="ic"><use href="#ic-copy"/></svg> <span data-en="Copy secret" data-fa="کپی سکرت">Copy secret</span></button>
            <button class="btn btn-sm" onclick="qrMt()"><svg class="ic"><use href="#ic-qr"/></svg> QR</button>
          </div>
          <hr style="border-color:var(--border);margin:14px 0;">
          <div class="fg"><label class="fl" data-en="New fronting domain" data-fa="دامنه پوششی جدید">New fronting domain</label><input class="fi" id="mt-newdomain" placeholder="www.cloudflare.com"></div>
          <button class="btn btn-danger btn-sm" onclick="regenMt()"><svg class="ic"><use href="#ic-refresh"/></svg> <span data-en="Regenerate secret" data-fa="ساخت سکرت جدید">Regenerate secret</span></button>
          <div style="font-size:0.78rem;color:var(--text3);margin-top:8px;" data-en="Existing users must re-import the new link." data-fa="کاربران فعلی باید لینک جدید را دوباره وارد کنند.">Existing users must re-import the new link.</div>
        </div>

        <div class="card">
          <div class="mo-title" data-en="Endpoint configuration" data-fa="تنظیم آدرس پراکسی" style="margin-bottom:14px;">Endpoint configuration</div>
          <div style="font-size:0.8rem;color:var(--text3);margin-bottom:12px;line-height:1.7;" data-en="Internal port = the port mtg binds to inside this container (the value you enter when creating the TCP proxy). Public host/port = what clients use in the link. Leave public fields empty to use Railway's auto-detected address." data-fa="پورت داخلی = پورتی که mtg داخل کانتینر روی آن گوش می‌دهد (همان مقداری که موقع ساخت TCP Proxy وارد می‌کنید). دامنه/پورت عمومی = چیزی که کاربران در لینک استفاده می‌کنند. فیلدهای عمومی را خالی بگذارید تا آدرس خودکار Railway استفاده شود.">Internal port = the port mtg binds to inside this container (the value you enter when creating the TCP proxy). Public host/port = what clients use in the link. Leave public fields empty to use Railway's auto-detected address.</div>
          <div class="fg"><label class="fl" data-en="Internal port (bind)" data-fa="پورت داخلی (bind)">Internal port (bind)</label><input class="fi" id="mt-bind-port" type="number" min="1" max="65535" placeholder="443"></div>
          <div class="fg"><label class="fl" data-en="Public host" data-fa="دامنه عمومی">Public host</label><input class="fi" id="mt-pub-host" placeholder="shuttle.proxy.rlwy.net"></div>
          <div class="fg"><label class="fl" data-en="Public port" data-fa="پورت عمومی">Public port</label><input class="fi" id="mt-pub-port" type="number" min="1" max="65535" placeholder="15140"></div>
          <button class="btn btn-primary btn-sm" onclick="saveEndpoint()"><svg class="ic"><use href="#ic-check"/></svg> <span data-en="Save endpoint" data-fa="ذخیره آدرس">Save endpoint</span></button>
          <div style="font-size:0.78rem;color:var(--text3);margin-top:8px;" data-en="Changes persist and restart the proxy. Clear the public fields to revert to automatic detection." data-fa="تغییرات ذخیره می‌شوند و پراکسی ریستارت می‌شود. فیلدهای عمومی را خالی کنید تا به تشخیص خودکار بازگردد.">Changes persist and restart the proxy. Clear the public fields to revert to automatic detection.</div>
        </div>
      </div>
    </section>
    <section class="page" id="page-aether">
      <div class="page-header">
        <div>
          <div class="page-title" data-en="Aether Tunnel" data-fa="تونل Aether">Aether Tunnel</div>
          <div class="page-sub" data-en="Cloudflare tunnel that can serve as the exit for all panel users" data-fa="تونل کلودفلر به‌عنوان خروجی کاربران پنل">Cloudflare tunnel that can serve as the exit for all panel users</div>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <button class="btn btn-sm" onclick="loadAether()"><svg class="ic"><use href="#ic-refresh"/></svg> <span data-en="Refresh" data-fa="بازخوانی">Refresh</span></button>
        </div>
      </div>

      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
          <div style="font-size:1.1rem;font-weight:700;"><span data-en="Status" data-fa="وضعیت">Status</span>: <span id="ae-phase">—</span></div>
          <div id="ae-out" style="font-size:.85rem;"></div>
        </div>
        <div id="ae-info" style="font-size:.85rem;color:var(--text2);margin-top:8px;line-height:1.8;direction:ltr;text-align:left;"></div>
        <div id="ae-err" style="display:none;margin-top:8px;color:var(--red);font-size:.85rem;direction:ltr;text-align:left;"></div>
        <div id="ae-nobin" style="display:none;margin-top:8px;color:var(--yellow);font-size:.85rem;" data-en="Aether binary not found. Click Install to download the pinned release." data-fa="فایل اجرایی Aether پیدا نشد. روی Install بزنید.">Aether binary not found. Click Install to download the pinned release.</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;">
          <button class="btn btn-primary btn-sm" onclick="aeStart()" data-en="Start" data-fa="شروع">Start</button>
          <button class="btn btn-outline btn-sm" onclick="aeRestart()" data-en="Restart" data-fa="ریستارت">Restart</button>
          <button class="btn btn-danger btn-sm" onclick="aeStop()" data-en="Stop" data-fa="توقف">Stop</button>
          <button class="btn btn-outline btn-sm" onclick="aeInstall()" data-en="Install" data-fa="نصب">Install</button>
        </div>
      </div>

      <div class="card">
        <div style="font-weight:700;margin-bottom:10px;" data-en="Tunnel options" data-fa="تنظیمات تونل">Tunnel options</div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;">
          <div class="fg"><label class="fl">Protocol</label><select class="fi" id="ae-protocol"></select></div>
          <div class="fg"><label class="fl">Transport</label><select class="fi" id="ae-transport"></select></div>
          <div class="fg"><label class="fl">Scan</label><select class="fi" id="ae-scan"></select></div>
          <div class="fg"><label class="fl">IP</label><select class="fi" id="ae-ip"></select></div>
          <div class="fg"><label class="fl">Noize</label><select class="fi" id="ae-noize"></select></div>
          <div class="fg"><label class="fl">Port</label><input class="fi" type="number" id="ae-port" min="1024" max="65534" value="1819"></div>
        </div>
        <div style="display:flex;gap:18px;flex-wrap:wrap;">
          <label><input type="checkbox" id="ae-httpproxy"> HTTP proxy (port+1)</label>
          <label><input type="checkbox" id="ae-quick" checked> Quick reconnect</label>
        </div>
      </div>

      <div class="card">
        <div style="font-weight:700;margin-bottom:10px;" data-en="Outbound for panel users" data-fa="خروجی کاربران پنل">Outbound for panel users</div>
        <div class="fg"><label class="fl" data-en="Exit mode" data-fa="حالت خروج">Exit mode</label>
          <select class="fi" id="ae-mode">
            <option value="direct">direct — connect from this server (default)</option>
            <option value="auto">auto — use Aether while connected, else direct</option>
            <option value="aether">aether — always via Aether (fail-closed)</option>
          </select>
        </div>
        <div id="ae-mode-note" style="font-size:.8rem;color:var(--text3);margin-bottom:10px;"></div>
        <label style="display:block;margin-bottom:12px;"><input type="checkbox" id="ae-auto"> <span data-en="Start the tunnel automatically after every restart" data-fa="شروع خودکار تونل پس از هر ری‌استارت">Start the tunnel automatically after every restart</span></label>
        <button class="btn btn-primary btn-sm" onclick="aeSaveSettings()" data-en="Save" data-fa="ذخیره">Save</button>
      </div>

      <div class="card">
        <div style="font-weight:700;margin-bottom:6px;">Watchdog</div>
        <div id="ae-wd" style="font-size:.85rem;color:var(--text2);direction:ltr;text-align:left;"></div>
      </div>

      <div class="card">
        <div style="font-weight:700;margin-bottom:6px;" data-en="Tunnel log" data-fa="لاگ تونل">Tunnel log</div>
        <pre id="ae-logs" style="max-height:280px;overflow:auto;font-size:.74rem;line-height:1.5;white-space:pre-wrap;word-break:break-all;direction:ltr;text-align:left;margin:0;"></pre>
      </div>
    </section>

    <section class="page" id="page-telegram">
      <div class="page-header"><div class="page-title" data-en="Telegram Bot" data-fa="ربات تلگرام">Telegram Bot</div></div>
      <div class="card">
        <div class="fg"><label class="fl" data-en="Bot Token" data-fa="توکن ربات">Bot Token</label><input class="fi" id="tg-token"></div>
        <div class="fg"><label class="fl" data-en="Chat ID" data-fa="شناسه چت">Chat ID</label><input class="fi" id="tg-chat-id"></div>
        <div class="fg"><label class="fl" data-en="Notify Events" data-fa="رویدادهای اطلاع‌رسانی">Notify Events</label>
          <div style="display:flex;flex-wrap:wrap;gap:6px;">
            <label><input type="checkbox" value="quota_90" class="tg-event"> <span data-en="Quota 90%" data-fa="کوتا ۹۰٪">Quota 90%</span></label>
            <label><input type="checkbox" value="login" class="tg-event"> <span data-en="Login" data-fa="ورود">Login</span></label>
            <label><input type="checkbox" value="expiry" class="tg-event"> <span data-en="Expiry" data-fa="انقضا">Expiry</span></label>
            <label><input type="checkbox" value="tunnel_down" class="tg-event"> <span data-en="Tunnel down" data-fa="قطع تونل">Tunnel down</span></label>
            <label><input type="checkbox" value="error" class="tg-event"> <span data-en="Error" data-fa="خطا">Error</span></label>
          </div>
        </div>
        <div class="fg"><label class="fl" data-en="Report Interval (hours)" data-fa="فاصله گزارش (ساعت)">Report Interval (hours)</label><input class="fi" type="number" id="tg-interval" value="1" min="0.5" step="0.5"></div>
        <div class="fg"><label class="fl">Telegram Language</label>
          <div class="toggle on" id="tg-lang-toggle" onpointerdown="toggleTgLang()"></div>
          <span id="tg-lang-label">English</span>
          <input type="hidden" id="tg-lang-hidden" value="en">
        </div>
        <div class="fg"><label class="fl">Custom Templates (EN)</label>
          <textarea class="fi" id="tg-templates-en" rows="4">{"quota_90":"⚠️ {label} ({uid}) used 90% of quota","login":"🔐 SE7O-SNA Panel login\n🌐 IP: {ip}\n🤖 UA: {ua}\n📅 {time}","expiry":"⏰ {label} expired","error":"❌ Error on {label}: check logs"}</textarea>
        </div>
        <div class="fg"><label class="fl">Custom Templates (FA)</label>
          <textarea class="fi" id="tg-templates-fa" rows="4">{"quota_90":"⚠️ {label} ({uid}) ۹۰٪ کوتا","login":"🔐 ورود SE7O-SNA\n🌐 IP: {ip}\n🤖 UA: {ua}\n📅 {time}","expiry":"⏰ {label} منقضی شد","error":"❌ خطا در {label}: بررسی شود"}</textarea>
        </div>
        <div style="margin:6px 0;">
          <button class="btn btn-outline btn-sm" onclick="previewTemplate()">Preview</button>
          <div id="tg-preview" style="margin-top:6px; padding:8px; background:var(--surface3); border-radius:8px; white-space:pre-wrap;"></div>
        </div>
        <div style="display:flex;gap:6px;"><button class="btn btn-primary" onclick="saveTelegramSettings()" data-en="Save" data-fa="ذخیره">Save</button><button class="btn btn-outline btn-sm" onclick="testTelegram()" data-en="Test" data-fa="تست">Test</button></div>
      </div>
    </section>
    <section class="page" id="page-settings">
      <div class="page-header"><div class="page-title" data-en="Settings" data-fa="تنظیمات">Settings</div></div>
      <div class="card">
        <div class="fg"><label class="fl" data-en="Login Text" data-fa="متن ورود">Login Text</label><input class="fi" id="set-footer"></div>
        <div class="fg"><label class="fl" data-en="Default Path" data-fa="مسیر پیش‌فرض">Default Path</label><input class="fi" id="set-default-path" placeholder="/ws/{uid}"></div>
        <div class="fg">
          <label class="fl" data-en="Timezone / Region" data-fa="منطقه زمانی / ساعت">Timezone / Region</label>
          <div class="glass-btn-group" id="tz-glass-group">
            <button type="button" class="glass-btn active" id="btn-tz-utc" onclick="setPanelTZ(0, 'UTC')">UTC (00:00)</button>
            <button type="button" class="glass-btn" id="btn-tz-tehran" onclick="setPanelTZ(3.5, 'Tehran')">Tehran (+3:30)</button>
            <button type="button" class="glass-btn" id="btn-tz-custom" onclick="toggleCustomTZInput(true)">Custom</button>
          </div>
          <div id="custom-tz-container" style="display:none; margin-top:10px;">
            <input type="text" class="fi" id="custom-tz-value" placeholder="e.g. Asia/Tehran or +3.5" oninput="applyCustomTZ(this.value)">
          </div>
        </div>
        <div class="fg">
          <label class="fl" data-en="Interface Theme" data-fa="تم محیط کاربری">Interface Theme</label>
          <div class="glass-btn-group" id="theme-glass-group">
            <button type="button" class="glass-btn active" id="btn-theme-dark" onclick="setPanelTheme('dark')">Dark</button>
            <button type="button" class="glass-btn" id="btn-theme-light" onclick="setPanelTheme('light')">Light</button>
            <button type="button" class="glass-btn" id="btn-theme-blue-dark" onclick="setPanelTheme('blue-dark')">Blue</button>
          </div>
          <input type="hidden" id="set-theme-color" value="dark">
        </div>
        <div class="fg">
          <label class="fl" data-en="Panel Language" data-fa="زبان پنل">Panel Language</label>
          <div class="glass-btn-group" id="lang-glass-group">
            <button type="button" class="glass-btn active" id="btn-lang-en" onclick="setPanelLanguage('en')">English</button>
            <button type="button" class="glass-btn" id="btn-lang-fa" onclick="setPanelLanguage('fa')">فارسی</button>
          </div>
        </div>
        <div class="fg"><label class="fl" data-en="Keep Alive" data-fa="ضدخواب">Keep Alive</label>
          <div class="glass-btn-group" id="keepalive-mode-group">
            <button type="button" class="glass-btn active" id="btn-keepalive-simple" onclick="setKeepAliveMode('simple')">Simple</button>
            <button type="button" class="glass-btn" id="btn-keepalive-advanced" onclick="setKeepAliveMode('advanced')">Advanced</button>
          </div>
          <input type="hidden" id="set-keepalive-mode" value="simple">
          <div class="status-cards-grid" style="margin-top:8px;">
            <div class="status-glass-card active" id="card-keepalive" onclick="toggleSettingCard('card-keepalive', 'set-keepalive-enabled')">
              <svg class="ic"><use href="#ic-bolt"/></svg><span data-en="Keep-Alive Enabled" data-fa="ضدخواب فعال">Keep-Alive</span>
              <input type="hidden" id="set-keepalive-enabled" value="1">
            </div>
          </div>
        </div>
        <div class="fg"><label class="fl" data-en="Keep Alive Interval (seconds)" data-fa="فاصله ضدخواب (ثانیه)">Interval</label>
          <input class="fi" type="number" id="set-keep-alive-interval" placeholder="300" min="60">
        </div>
        <div class="fg"><label class="fl" data-en="Default Traffic Limit (GB)" data-fa="محدودیت ترافیک پیش‌فرض (گیگابایت)">Default Traffic Limit (GB)</label><input class="fi" type="number" id="set-default-limit" placeholder="0 = Unlimited"></div>
        <div class="fg"><label class="fl" data-en="Default Expiry (Days)" data-fa="انقضای پیش‌فرض (روز)">Default Expiry (Days)</label><input class="fi" type="number" id="set-default-expiry" placeholder="0 = Unlimited"></div>
        <div class="fg"><label class="fl" data-en="Default Max Connections" data-fa="حداکثر اتصالات پیش‌فرض">Default Max Connections</label><input class="fi" type="number" id="set-default-maxconn" placeholder="0 = Unlimited"></div>
        <div class="fg"><label class="fl" data-en="Monthly Limit (GB)" data-fa="محدودیت ماهانه (گیگابایت)">Monthly Limit (GB)</label><input class="fi" type="number" id="set-monthly-limit" placeholder="0 = Unlimited"></div>

        <div class="fg" style="margin-top:20px;">
          <label class="fl" data-en="System Toggles" data-fa="وضعیت تنظیمات">System Toggles</label>
          <div class="status-cards-grid">
            <div class="status-glass-card active" id="card-log" onclick="toggleSettingCard('card-log', 'set-log-toggle')">
              <svg class="ic"><use href="#ic-logs"/></svg><span data-en="Logs" data-fa="لاگ سیستم">Logs</span>
              <input type="hidden" id="set-log-toggle" value="1">
            </div>
            <div class="status-glass-card active" id="card-auto" onclick="toggleSettingCard('card-auto', 'set-auto-disable')">
              <svg class="ic"><use href="#ic-ban"/></svg><span data-en="Auto Disable" data-fa="غیرفعال‌سازی">Auto Disable</span>
              <input type="hidden" id="set-auto-disable" value="1">
            </div>
            <div class="status-glass-card active" id="card-tgrep" onclick="toggleSettingCard('card-tgrep', 'set-tg-report')">
              <svg class="ic"><use href="#ic-telegram"/></svg><span data-en="TG Reports" data-fa="گزارش تلگرام">TG Reports</span>
              <input type="hidden" id="set-tg-report" value="1">
            </div>
            <div class="status-glass-card active" id="card-tgnot" onclick="toggleSettingCard('card-tgnot', 'set-tg-notify')">
              <svg class="ic"><use href="#ic-bell"/></svg><span data-en="TG Alerts" data-fa="اعلان تلگرام">TG Alerts</span>
              <input type="hidden" id="set-tg-notify" value="1">
            </div>
          </div>
        </div>

        <hr style="border-color:var(--border);margin:14px 0;">
        <div class="mo-title" data-en="Change Password" data-fa="تغییر رمز عبور" style="margin-bottom:14px;">Change Password</div>
        <div class="fg"><label class="fl" data-en="Current Password" data-fa="رمز فعلی">Current Password</label><input class="fi" type="password" id="cpw"></div>
        <div class="fg"><label class="fl" data-en="New Password" data-fa="رمز جدید">New Password</label><input class="fi" type="password" id="npw"></div>
        <button class="btn btn-primary btn-sm" onclick="chgPw()" data-en="Update Password" data-fa="بروزرسانی رمز">Update Password</button>
        <div style="margin-top:16px;">
          <button class="btn btn-primary" onclick="saveGeneralSettings()" data-en="Save All Settings" data-fa="ذخیره همه تنظیمات" style="width:100%; justify-content:center; padding:12px;">Save All Settings</button>
        </div>
        <hr style="border-color:var(--border);margin:14px 0;">
        <div style="display:flex;align-items:center;gap:10px;">
          <button class="btn btn-danger" onclick="resetAllSettings()" data-en="Reset to Defaults" data-fa="بازنشانی به پیش‌فرض">Reset to Defaults</button>
          <span style="font-size:0.8rem;color:var(--text3);" data-en="Resets all settings except password." data-fa="همه تنظیمات به جز رمز عبور بازنشانی می‌شود."></span>
        </div>
        <hr style="border-color:var(--border);margin:14px 0;">
        <div style="display:flex;align-items:center;gap:10px;">
          <button class="btn btn-warning" onclick="restartPanel()" data-en="Restart Panel" data-fa="ری‌استارت پنل">Restart Panel</button>
          <span style="font-size:0.8rem;color:var(--text3);" data-en="Restarts the whole panel process. Active connections drop for a few seconds." data-fa="کل پروسه پنل ری‌استارت می‌شود. اتصالات فعال برای لحظاتی قطع خواهند شد."></span>
        </div>
      </div>
    </section>
  </main>
  <nav class="mobile-nav">
    <div class="nav-items">
      <div class="nav-item active" data-page="dashboard" onclick="switchPage('dashboard')"><span class="nav-icon"><svg class="ic"><use href="#ic-dashboard"/></svg></span><span data-en="Home" data-fa="خانه">Home</span></div>
      <div class="nav-item" data-page="inbounds" onclick="switchPage('inbounds')"><span class="nav-icon"><svg class="ic"><use href="#ic-inbounds"/></svg></span><span data-en="Inbound" data-fa="اینباند">Inbound</span></div>
      <div class="nav-item" data-page="addresses" onclick="switchPage('addresses')"><span class="nav-icon"><svg class="ic"><use href="#ic-link"/></svg></span><span data-en="Clean IP" data-fa="آی‌پی تمیز">Clean IP</span></div>
      <div class="nav-item" data-page="logs" onclick="switchPage('logs')"><span class="nav-icon"><svg class="ic"><use href="#ic-logs"/></svg></span><span data-en="Logs" data-fa="لاگ">Logs</span></div>
      <div class="nav-item" data-page="telegram" onclick="switchPage('telegram')"><span class="nav-icon"><svg class="ic"><use href="#ic-telegram"/></svg></span><span data-en="Bot" data-fa="ربات">Bot</span></div>
      <div class="nav-item" data-page="aether" onclick="switchPage('aether')"><span class="nav-icon"><svg class="ic"><use href="#ic-bolt"/></svg></span><span data-en="Aether" data-fa="Aether">Aether</span></div>
      <div class="nav-item" data-page="mtproxy" onclick="switchPage('mtproxy')"><span class="nav-icon"><svg class="ic"><use href="#ic-bolt"/></svg></span><span data-en="MTProxy" data-fa="پراکسی">MTProxy</span></div>
      <div class="nav-item" data-page="settings" onclick="switchPage('settings')"><span class="nav-icon"><svg class="ic"><use href="#ic-settings"/></svg></span><span data-en="Settings" data-fa="تنظیمات">Settings</span></div>
    </div>
  </nav>
  <footer class="footer">
    <div class="footer-inner">
      <span id="footer-dedication"></span>
      <a href="https://t.me/SE7O_SNA" target="_blank">Telegram</a>
      <a href="https://github.com/SE7O-SNA" target="_blank">GitHub</a>
      <a href="https://github.com/SE7O-SNA/SE7O-SNA-panel" target="_blank">Project Repo</a>
    </div>
  </footer>
</div>

<div class="mo" id="mo-add">
  <div class="mo-box">
    <button class="mo-close" onclick="document.getElementById('mo-add').classList.remove('show')"><svg class="ic"><use href="#ic-close"/></svg></button>
    <div class="mo-title" data-en="Create Inbound" data-fa="ایجاد اینباند">Create Inbound</div>
    <div class="fg"><label class="fl" data-en="Name" data-fa="نام">Name</label><input class="fi" id="nl" placeholder="This Server is Free" maxlength="60"></div>
    <div class="fg"><label class="fl" data-en="Flag / Country" data-fa="پرچم / کشور">Flag / Country</label>
      <select class="fs" id="flag-select-create" onchange="applyFlagCreate()">
        <option value="">None</option>
        <option value="cn">🇨🇳 China</option>
        <option value="nl">🇳🇱 Netherlands</option>
        <option value="ru">🇷🇺 Russia</option>
        <option value="us">🇺🇸 United States</option>
        <option value="ca">🇨🇦 Canada</option>
        <option value="ir">🇮🇷 Iran</option>
        <option value="de">🇩🇪 Germany</option>
        <option value="gb">🇬🇧 United Kingdom</option>
        <option value="it">🇮🇹 Italy</option>
        <option value="fr">🇫🇷 France</option>
        <option value="tr">🇹🇷 Turkey</option>
        <option value="ae">🇦🇪 UAE</option>
        <option value="custom">Custom (2-letter)</option>
      </select>
      <input class="fi" id="flag-custom-create" placeholder="e.g. jp" style="display:none; margin-top:5px;" maxlength="2">
      <input type="hidden" id="flag-code-create" value="">
    </div>
    <div class="fg"><label class="fl">UUID</label><div style="display:flex;gap:6px;"><input class="fi" id="auuid" placeholder="Leave empty for auto-generate" style="flex:1;"><button class="btn btn-outline btn-sm" onclick="generateUUID('auuid')"><svg class="ic"><use href="#ic-dice"/></svg> Generate</button></div></div>
    <div class="fg"><button class="adv-toggle" onclick="toggleAdv('adv-create')">▼ <span data-en="Advanced Options" data-fa="گزینه‌های پیشرفته">Advanced Options</span></button>
      <div id="adv-create" class="adv-section">
        <div class="fg"><label class="fl" data-en="Profile" data-fa="پروفایل">Profile</label><select class="fs" id="ares-profile" onchange="applyProfileCreate()"><option value="">Custom</option><option value="default">Default</option><option value="youtube">YouTube</option><option value="instagram">Instagram</option><option value="twitter">Twitter</option><option value="tiktok">TikTok</option><option value="whatsapp">WhatsApp</option><option value="telegram">Telegram</option><option value="netflix">Netflix</option><option value="spotify">Spotify</option><option value="google">Google</option></select></div>
        <div class="fg"><label class="fl" data-en="Transport" data-fa="ترنسپورت">Transport</label>
          <select class="fs" id="atransport" onchange="onTransportChange('a')">
            <option value="ws" selected>WebSocket (ws)</option>
            <option value="xhttp">XHTTP / splithttp (xhttp)</option>
            <option value="http">HTTP (http)</option>
            <option value="tcp">Raw TCP (tcp)</option>
          </select>
        </div>
        <div class="fg" id="atcp-fields" style="display:none;">
          <label class="fl" data-en="Raw TCP public host:port" data-fa="هاست:پورت عمومی TCP">Raw TCP public host:port</label>
          <input class="fi" id="atcpinfo" placeholder="set RAW_TCP_PUBLIC_HOST / RAW_TCP_PUBLIC_PORT in config" disabled>
          <span style="font-size:0.78rem;color:var(--text3);" data-en="Raw TCP needs RAW_TCP_ENABLED=true and RAW_TCP_PUBLIC_HOST/PORT configured on the server." data-fa="Raw TCP نیازمند RAW_TCP_ENABLED=true و تنظیم RAW_TCP_PUBLIC_HOST/PORT روی سرور است.">Raw TCP needs RAW_TCP_ENABLED=true and RAW_TCP_PUBLIC_HOST/PORT configured on the server.</span>
        </div>
        <div class="fg"><label class="fl" data-en="Encryption" data-fa="رمزنگاری">Encryption</label>
          <select class="fs" id="aenc">
            <option value="none">none (default)</option>
            <option value="aes-128-gcm">aes-128-gcm</option>
            <option value="aes-256-gcm">aes-256-gcm</option>
            <option value="chacha20-poly1305">chacha20-poly1305</option>
            <option value="zero">zero</option>
          </select>
        </div>
        <div class="fg"><label class="fl">Path</label><input class="fi" id="ap" placeholder="/ws/{uid}"></div>
        <div class="fg"><label class="fl">SNI</label><input class="fi" id="asni" placeholder="example.com"></div>
        <div class="fg"><label class="fl">Host</label><input class="fi" id="ahost" placeholder="example.com"></div>
        <div class="fg"><label class="fl">Fingerprint</label>
          <select class="fs" id="afp">
            <option value="chrome">chrome</option>
            <option value="firefox">firefox</option>
            <option value="safari">safari</option>
            <option value="ios">ios</option>
            <option value="edge">edge</option>
            <option value="opera">opera</option>
            <option value="android">android</option>
            <option value="random">random</option>
            <option value="none">none</option>
          </select>
        </div>
        <div class="fg"><label class="fl">Fragment</label>
          <select class="fs" id="afrag">
            <option value="">none</option>
            <option value="1-3">1-3</option>
            <option value="10-20">10-20</option>
            <option value="50-100">50-100</option>
            <option value="100-200">100-200</option>
          </select>
        </div>
      </div>
    </div>
    <div class="fg"><label class="fl" data-en="Traffic Limit (GB)" data-fa="محدودیت ترافیک (گیگابایت)">Traffic Limit (GB)</label><input class="fi" type="number" id="nv" min="0" step="0.1" value="0" placeholder="0 = Unlimited"></div>
    <div class="fg"><label class="fl" data-en="Max Connections" data-fa="حداکثر اتصالات">Max Connections</label><input class="fi" type="number" id="nc" min="0" value="0" placeholder="0 = Unlimited"></div>
    <div class="fg"><label class="fl" data-en="Validity (Days)" data-fa="اعتبار (روز)">Validity (Days)</label><input class="fi" type="number" id="nd" min="0" value="0" placeholder="0 = Unlimited"></div>
    <div class="fg"><label class="fl" data-en="Color" data-fa="رنگ">Color</label><input type="color" id="alink-color" value="#39ff14"></div>
    <div style="display:flex;gap:6px;margin-top:10px;"><button class="btn btn-primary" onclick="createLink()" style="flex:1;" data-en="Create" data-fa="ایجاد">Create</button><button class="btn btn-outline" onclick="document.getElementById('mo-add').classList.remove('show')" data-en="Cancel" data-fa="انصراف">Cancel</button></div>
  </div>
</div>

<div class="mo" id="mo-edit">
  <div class="mo-box">
    <button class="mo-close" onclick="document.getElementById('mo-edit').classList.remove('show')"><svg class="ic"><use href="#ic-close"/></svg></button>
    <div class="mo-title" id="et" data-en="Edit Inbound" data-fa="ویرایش اینباند">Edit Inbound</div>
    <input type="hidden" id="eu">
    <div class="fg"><label class="fl">UUID</label><input class="fi" id="euuid" readonly></div>
    <div class="fg"><label class="fl" data-en="Name" data-fa="نام">Name</label><input class="fi" id="en2" maxlength="60"></div>
    <div class="fg"><label class="fl" data-en="Flag / Country" data-fa="پرچم / کشور">Flag / Country</label>
      <select class="fs" id="flag-select-edit" onchange="applyFlagEdit()">
        <option value="">None</option>
        <option value="cn">🇨🇳 China</option>
        <option value="nl">🇳🇱 Netherlands</option>
        <option value="ru">🇷🇺 Russia</option>
        <option value="us">🇺🇸 United States</option>
        <option value="ca">🇨🇦 Canada</option>
        <option value="ir">🇮🇷 Iran</option>
        <option value="de">🇩🇪 Germany</option>
        <option value="gb">🇬🇧 United Kingdom</option>
        <option value="it">🇮🇹 Italy</option>
        <option value="fr">🇫🇷 France</option>
        <option value="tr">🇹🇷 Turkey</option>
        <option value="ae">🇦🇪 UAE</option>
        <option value="custom">Custom (2-letter)</option>
      </select>
      <input class="fi" id="flag-custom-edit" placeholder="e.g. jp" style="display:none; margin-top:5px;" maxlength="2">
      <input type="hidden" id="flag-code-edit" value="">
    </div>
    <div class="fg"><button class="adv-toggle" onclick="toggleAdv('adv-edit')">▼ <span data-en="Advanced Options" data-fa="گزینه‌های پیشرفته">Advanced Options</span></button>
      <div id="adv-edit" class="adv-section">
        <div class="fg"><label class="fl" data-en="Profile" data-fa="پروفایل">Profile</label><select class="fs" id="eres-profile" onchange="applyProfile()"><option value="">Custom</option><option value="default">Default</option><option value="youtube">YouTube</option><option value="instagram">Instagram</option><option value="twitter">Twitter</option><option value="tiktok">TikTok</option><option value="whatsapp">WhatsApp</option><option value="telegram">Telegram</option><option value="netflix">Netflix</option><option value="spotify">Spotify</option><option value="google">Google</option></select></div>
        <div class="fg"><label class="fl" data-en="Transport" data-fa="ترنسپورت">Transport</label>
          <select class="fs" id="etransport" onchange="onTransportChange('e')">
            <option value="ws">WebSocket (ws)</option>
            <option value="xhttp">XHTTP / splithttp (xhttp)</option>
            <option value="http">HTTP (http)</option>
            <option value="tcp">Raw TCP (tcp)</option>
          </select>
        </div>
        <div class="fg" id="etcp-fields" style="display:none;">
          <label class="fl" data-en="Raw TCP public host:port" data-fa="هاست:پورت عمومی TCP">Raw TCP public host:port</label>
          <input class="fi" id="etcpinfo" placeholder="set RAW_TCP_PUBLIC_HOST / RAW_TCP_PUBLIC_PORT in config" disabled>
          <span style="font-size:0.78rem;color:var(--text3);" data-en="Raw TCP needs RAW_TCP_ENABLED=true and RAW_TCP_PUBLIC_HOST/PORT configured on the server." data-fa="Raw TCP نیازمند RAW_TCP_ENABLED=true و تنظیم RAW_TCP_PUBLIC_HOST/PORT روی سرور است.">Raw TCP needs RAW_TCP_ENABLED=true and RAW_TCP_PUBLIC_HOST/PORT configured on the server.</span>
        </div>
        <div class="fg"><label class="fl" data-en="Encryption" data-fa="رمزنگاری">Encryption</label>
          <select class="fs" id="eenc">
            <option value="none">none (default)</option>
            <option value="aes-128-gcm">aes-128-gcm</option>
            <option value="aes-256-gcm">aes-256-gcm</option>
            <option value="chacha20-poly1305">chacha20-poly1305</option>
            <option value="zero">zero</option>
          </select>
        </div>
        <div class="fg"><label class="fl">Path</label><input class="fi" id="ep"></div>
        <div class="fg"><label class="fl">SNI</label><input class="fi" id="esni"></div>
        <div class="fg"><label class="fl">Host</label><input class="fi" id="ehost"></div>
        <div class="fg"><label class="fl">Fingerprint</label>
          <select class="fs" id="efp">
            <option value="chrome">chrome</option>
            <option value="firefox">firefox</option>
            <option value="safari">safari</option>
            <option value="ios">ios</option>
            <option value="edge">edge</option>
            <option value="opera">opera</option>
            <option value="android">android</option>
            <option value="random">random</option>
            <option value="none">none</option>
          </select>
        </div>
        <div class="fg"><label class="fl">Fragment</label>
          <select class="fs" id="efrag">
            <option value="">none</option>
            <option value="1-3">1-3</option>
            <option value="10-20">10-20</option>
            <option value="50-100">50-100</option>
            <option value="100-200">100-200</option>
          </select>
        </div>
      </div>
      <hr style="border-color:var(--border);margin:12px 0;">
      <button class="btn btn-outline" onclick="addTransportToUser()" data-en="+ Add transport to this user" data-fa="+ افزودن ترنسپورت به این کاربر">+ Add transport to this user</button>
    </div>
    <div class="fg"><label class="fl" data-en="Traffic Limit (GB)" data-fa="محدودیت ترافیک (گیگابایت)">Traffic Limit (GB)</label><input class="fi" type="number" id="el" min="0" step="0.1" placeholder="0 = Unlimited"></div>
    <div class="fg"><label class="fl" data-en="Max Connections" data-fa="حداکثر اتصالات">Max Connections</label><input class="fi" type="number" id="ec" min="0" placeholder="0 = Unlimited"></div>
    <div class="fg"><label class="fl" data-en="Validity (Days)" data-fa="اعتبار (روز)">Validity (Days)</label><input class="fi" type="number" id="ed" min="0" placeholder="0 = Unlimited"></div>
    <div class="fg"><label class="fl" data-en="Color" data-fa="رنگ">Color</label><input type="color" id="e-color" value="#39ff14"></div>
    <div style="display:flex;gap:6px;margin-top:10px;"><button class="btn btn-primary" onclick="saveEdit()" style="flex:1;" data-en="Save" data-fa="ذخیره">Save</button><button class="btn btn-danger btn-sm" onclick="resetTraf()" data-en="Reset Traffic" data-fa="بازنشانی ترافیک">Reset Traffic</button><button class="btn btn-outline" onclick="document.getElementById('mo-edit').classList.remove('show')" data-en="Cancel" data-fa="انصراف">Cancel</button></div>
  </div>
</div>

<div class="mo" id="mo-qr">
  <div class="mo-box" style="max-width:360px;">
    <button class="mo-close" onclick="document.getElementById('mo-qr').classList.remove('show')"><svg class="ic"><use href="#ic-close"/></svg></button>
    <div class="mo-title">QR Code</div>
    <div class="qr-box"><img id="qr-img" src="" alt="QR Code"></div>
    <button class="btn btn-primary" onclick="dlQR()" style="width:100%;margin-top:10px;justify-content:center;" data-en="Download" data-fa="دانلود">Download</button>
  </div>
</div>

<div class="mo" id="mo-json">
  <div class="mo-box" style="max-width:520px;">
    <button class="mo-close" onclick="document.getElementById('mo-json').classList.remove('show')"><svg class="ic"><use href="#ic-close"/></svg></button>
    <div class="mo-title" data-en="Client Config (JSON)" data-fa="کانفیگ کلاینت (JSON)">Client Config (JSON)</div>
    <div style="font-size:0.78rem;color:var(--text3);margin-bottom:8px;" data-en="Import this file directly into v2rayN / v2rayNG / NekoBox / Streisand." data-fa="این فایل را مستقیماً در v2rayN / v2rayNG / NekoBox / Streisand ایمپورت کنید.">Import this file directly into v2rayN / v2rayNG / NekoBox / Streisand.</div>
    <textarea id="json-text" class="fi" readonly style="min-height:300px;font-family:monospace;font-size:0.75rem;white-space:pre;"></textarea>
    <button id="json-dl" class="btn btn-primary" style="width:100%;margin-top:10px;justify-content:center;" data-en="Download .json" data-fa="دانلود .json">Download .json</button>
  </div>
</div>

<div class="mo" id="mo-addr-edit">
  <div class="mo-box">
    <button class="mo-close" onclick="document.getElementById('mo-addr-edit').classList.remove('show')"><svg class="ic"><use href="#ic-close"/></svg></button>
    <div class="mo-title" data-en="Edit Address" data-fa="ویرایش آدرس">Edit Address</div>
    <div class="fg"><label class="fl" data-en="New Address" data-fa="آدرس جدید">New Address</label><input class="fi" id="edit-addr-input"></div>
    <button class="btn btn-primary" onclick="saveAddrEdit()" style="width:100%;justify-content:center;margin-top:10px;" data-en="Save" data-fa="ذخیره">Save</button>
  </div>
</div>

<script>
const $=s=>document.querySelector(s),$m=id=>document.getElementById(id);
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');}
function svgic(name){return '<svg class="ic" style="width:1em;height:1em;vertical-align:-0.15em"><use href="#ic-'+name+'"/></svg>';}
const i18n = {
  en:{
    hoursAgo:'{n} h ago', minsAgo:'{n} min ago', justNow:'Just now', updatedAt:'Updated {time}',
    success:'Success', failed:'Failed',
    mb:'MB', gb:'GB', kb:'KB', b:'B',
    active:'Active', inactive:'Inactive', expired:'Expired', unlimited:'∞',
    create:'Create', save:'Save', cancel:'Cancel', edit:'Edit', copy:'Copy', sub:'Sub', qr:'QR', del:'Del',
    on:'On', off:'Off', reachable:'Reachable', failed:'Failed'
  },
  fa:{
    hoursAgo:'{n} ساعت پیش', minsAgo:'{n} دقیقه پیش', justNow:'لحظاتی پیش', updatedAt:'بروزرسانی {time}',
    success:'موفق', failed:'ناموفق',
    mb:'مگابایت', gb:'گیگابایت', kb:'کیلوبایت', b:'بایت',
    active:'فعال', inactive:'غیرفعال', expired:'منقضی', unlimited:'∞',
    create:'ایجاد', save:'ذخیره', cancel:'انصراف', edit:'ویرایش', copy:'کپی', sub:'اشتراک', qr:'QR', del:'حذف',
    on:'روشن', off:'خاموش', reachable:'در دسترس', failed:'خطا'
  }
};
function t(key,params={}){
  let str = (i18n[lang] && i18n[lang][key]) || i18n['en'][key] || key;
  for(let p in params) str = str.replace(`{${p}}`, params[p]);
  return str;
}
function codeToFlag(code) {
    if (!code || code.length !== 2) return '';
    code = code.toUpperCase();
    return String.fromCodePoint(0x1F1E6 + code.charCodeAt(0) - 65) + String.fromCodePoint(0x1F1E6 + code.charCodeAt(1) - 65);
}
let lang=localStorage.getItem('ll')||'en',theme=localStorage.getItem('theme')||'dark';
let allLinks=[],cf='all',sData={},tChart=null,allAddrs=[],isAuthenticated=false,liveConns={};
let prevUploadBytes = null, prevDownloadBytes = null, prevStatsTime = null;
let timezoneOffset = 0;
let editingAddrIndex = -1;
let selectedUids = new Set();
let selectedAddrIndices = new Set();
let uploadSpeedAvg = 0, downloadSpeedAvg = 0;
const footerTexts = {
  en: 'Dedicated to the people of my homeland Iran from <a href="https://github.com/SE7O-SNA" target="_blank">SE7O</a>',
  fa: 'تقدیم به مردم سرزمینم ایران از طرف <a href="https://github.com/SE7O-SNA" target="_blank">SE7O</a>'
};


const OPERATIONAL_PROFILES = {
    "instagram": { sni: "www.instagram.com", host: "www.instagram.com", path: "/graphql", fp: "chrome" },
    "youtube": { sni: "www.youtube.com", host: "www.youtube.com", path: "/youtubei/v1/image", fp: "chrome" },
    "twitter": { sni: "twitter.com", host: "twitter.com", path: "/ws", fp: "chrome" },
    "tiktok": { sni: "www.tiktok.com", host: "www.tiktok.com", path: "/ws", fp: "chrome" },
    "whatsapp": { sni: "web.whatsapp.com", host: "web.whatsapp.com", path: "/ws/chat/v4", fp: "safari" },
    "telegram": { sni: "telegram.org", host: "telegram.org", path: "/ws", fp: "chrome" },
    "netflix": { sni: "www.netflix.com", host: "www.netflix.com", path: "/ws", fp: "chrome" },
    "spotify": { sni: "www.spotify.com", host: "www.spotify.com", path: "/ws", fp: "chrome" },
    "google": { sni: "www.google.com", host: "www.google.com", path: "/ws", fp: "chrome" },
    "default": { sni: "", host: "", path: "", fp: "chrome" }
};

const profiles = {
  default: {path:'',sni:'',host:'',fp:'chrome'},
  youtube: {path:'/youtubei/v1/image',sni:'www.youtube.com',host:'www.youtube.com',fp:'chrome'},
  instagram: {path:'/graphql',sni:'www.instagram.com',host:'www.instagram.com',fp:'chrome'},
  twitter: {path:'/ws',sni:'twitter.com',host:'twitter.com',fp:'chrome'},
  tiktok: {path:'/ws',sni:'www.tiktok.com',host:'www.tiktok.com',fp:'chrome'},
  whatsapp: {path:'/ws/chat/v4',sni:'web.whatsapp.com',host:'web.whatsapp.com',fp:'safari'},
  telegram: {path:'/ws',sni:'telegram.org',host:'telegram.org',fp:'chrome'},
  netflix: {path:'/ws',sni:'www.netflix.com',host:'www.netflix.com',fp:'chrome'},
  spotify: {path:'/ws',sni:'www.spotify.com',host:'www.spotify.com',fp:'chrome'},
  google: {path:'/ws',sni:'www.google.com',host:'www.google.com',fp:'chrome'}
};

function applyProfile() {
  const p = $m('eres-profile').value;
  if (!p) return;
  const pr = OPERATIONAL_PROFILES[p] || profiles[p];
  if (pr) {
    $m('ep').value = pr.path || '';
    $m('esni').value = pr.sni || '';
    $m('ehost').value = pr.host || '';
    $m('efp').value = pr.fp || 'chrome';
  }
}

function applyProfileCreate() {
  const p = $m('ares-profile').value;
  if (!p) return;
  const pr = OPERATIONAL_PROFILES[p] || profiles[p];
  if (pr) {
    $m('ap').value = pr.path || '';
    $m('asni').value = pr.sni || '';
    $m('ahost').value = pr.host || '';
    $m('afp').value = pr.fp || 'chrome';
  }
}

function applyFlagCreate() {
    const sel = $m('flag-select-create').value;
    const customInput = $m('flag-custom-create');
    const hidden = $m('flag-code-create');
    if (sel === 'custom') {
        customInput.style.display = 'block';
        hidden.value = customInput.value.trim().toLowerCase();
    } else {
        customInput.style.display = 'none';
        hidden.value = sel;
    }
}

function applyFlagEdit() {
    const sel = $m('flag-select-edit').value;
    const customInput = $m('flag-custom-edit');
    const hidden = $m('flag-code-edit');
    if (sel === 'custom') {
        customInput.style.display = 'block';
        hidden.value = customInput.value.trim().toLowerCase();
    } else {
        customInput.style.display = 'none';
        hidden.value = sel;
    }
}

function setPanelLanguage(l) {
    document.querySelectorAll('#lang-glass-group .glass-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(`btn-lang-${l}`).classList.add('active');
    setLang(l);
}
function setPanelTheme(th) {
    document.querySelectorAll('#theme-glass-group .glass-btn').forEach(b => b.classList.remove('active'));
    const btn = document.getElementById(`btn-theme-${th}`);
    if (btn) btn.classList.add('active');
    const hiddenInput = $m('set-theme-color');
    if (hiddenInput) hiddenInput.value = th;
    setTheme(th);
    localStorage.setItem('theme', th);
}
function setPanelTZ(offset, name) {
    document.querySelectorAll('#tz-glass-group .glass-btn').forEach(b => b.classList.remove('active'));
    if (name === 'Tehran') document.getElementById('btn-tz-tehran').classList.add('active');
    else if (name === 'UTC') document.getElementById('btn-tz-utc').classList.add('active');
    else if (name === 'Custom') document.getElementById('btn-tz-custom').classList.add('active');
    toggleCustomTZInput(false);
    timezoneOffset = offset;
    localStorage.setItem('timezone_offset', offset);
    saveSingleSetting('timezone_offset', offset);
}
function toggleCustomTZInput(show) {
    const container = $m('custom-tz-container');
    const customBtn = document.getElementById('btn-tz-custom');
    if (show) {
        document.querySelectorAll('#tz-glass-group .glass-btn').forEach(b => b.classList.remove('active'));
        customBtn.classList.add('active');
        container.style.display = 'block';
    } else {
        container.style.display = 'none';
    }
}
function applyCustomTZ(val) {
    let parsedOffset = parseFloat(val);
    if (!isNaN(parsedOffset)) {
        timezoneOffset = parsedOffset;
        localStorage.setItem('timezone_offset', parsedOffset);
        saveSingleSetting('timezone_offset', parsedOffset);
    }
}
function saveSingleSetting(key, value) {
    fetch('/api/settings', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({[key]: value}) });
}
function setKeepAliveMode(mode) {
    document.querySelectorAll('#keepalive-mode-group .glass-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(`btn-keepalive-${mode}`).classList.add('active');
    var el = $m('set-keepalive-mode');
    if (el) el.value = mode;
}

function setTheme(t){
  theme=t;
  document.body.classList.toggle('light-mode',t==='light');
  document.body.classList.toggle('blue-mode',t==='blue-dark');
  localStorage.setItem('theme',t);
  const ti=document.querySelector('.btn-icon');
  if(ti){ti.innerHTML=t==='light'?'<svg class="ic"><use href="#ic-sun"/></svg>':(t==='blue-dark'?'<svg class="ic"><use href="#ic-moon"/></svg>':'<svg class="ic"><use href="#ic-moon"/></svg>');}
  updChartColors();
  syncGlassThemeButtons();
}
function toggleTheme(){
  const themes=['dark','light','blue-dark'];
  const idx=themes.indexOf(theme);
  setTheme(themes[(idx+1)%themes.length]);
}
function syncGlassThemeButtons() {
    document.querySelectorAll('#theme-glass-group .glass-btn').forEach(b => b.classList.remove('active'));
    const btn = document.getElementById(`btn-theme-${theme}`);
    if (btn) btn.classList.add('active');
}

function toggleSettingCard(cardId, inputId) {
    const card = $m(cardId);
    const input = $m(inputId);
    if (card.classList.contains('active')) {
        card.classList.remove('active');
        card.classList.add('inactive');
        input.value = '0';
    } else {
        card.classList.remove('inactive');
        card.classList.add('active');
        input.value = '1';
    }
}

function updateDashboardStatusCards(settings) {
    if (!settings) return;
    const cards = {
        'st-log': settings.log_enabled === '1',
        'st-auto': settings.auto_disable_enabled === '1',
        'st-tgrep': settings.telegram_report_enabled === '1',
        'st-tgnot': settings.telegram_notify_enabled === '1',
        'st-bot': !!(settings.tg_bot_token && settings.tg_chat_id)
    };
    for (const [id, enabled] of Object.entries(cards)) {
        const card = document.getElementById(id);
        if (card) {
            card.classList.toggle('active', enabled);
            card.classList.toggle('inactive', !enabled);
        }
    }
    updateSettingsStatusLabels();
}

function updateSettingsStatus(settings){
    if(!settings)return;
    const setCard = (cardId, enabled) => {
        const card = $m(cardId);
        if(card){
            card.classList.toggle('active', enabled);
            card.classList.toggle('inactive', !enabled);
        }
    };
    setCard('card-log', settings.log_enabled==='1');
    setCard('card-auto', settings.auto_disable_enabled==='1');
    setCard('card-tgrep', settings.telegram_report_enabled==='1');
    setCard('card-tgnot', settings.telegram_notify_enabled==='1');
    $m('set-log-toggle').value = settings.log_enabled==='1' ? '1' : '0';
    $m('set-auto-disable').value = settings.auto_disable_enabled==='1' ? '1' : '0';
    $m('set-tg-report').value = settings.telegram_report_enabled==='1' ? '1' : '0';
    $m('set-tg-notify').value = settings.telegram_notify_enabled==='1' ? '1' : '0';
    setCard('card-keepalive', settings.keep_alive_enabled==='1');
    $m('set-keepalive-enabled').value = settings.keep_alive_enabled==='1' ? '1' : '0';
}

function updateSettingsStatusLabels(){
  document.querySelectorAll('#settings-status .status-glass-card').forEach(card => {
    const svg = card.querySelector('svg');
    const labelEl = card.querySelector('span');
    const label = card.getAttribute('data-'+lang) || labelEl?.textContent || '';
    const mark = card.classList.contains('active')
      ? '<svg class="ic" style="width:1rem;height:1rem"><use href="#ic-check"/></svg>'
      : '<svg class="ic" style="width:1rem;height:1rem"><use href="#ic-x"/></svg>';
    card.innerHTML = (svg ? svg.outerHTML : '') + ' ' + mark + ' <span>' + label + '</span>';
  });
}
function setLang(l){
  lang=l; document.querySelectorAll('.lang-en,.lang-fa').forEach(e=>e.classList.remove('active'));
  document.querySelectorAll(`.lang-${l}`).forEach(e=>e.classList.add('active'));
  document.body.dir=l==='fa'?'rtl':'ltr';
  document.querySelectorAll('[data-en]').forEach(el=>{const v=el.getAttribute('data-'+l);if(v)el.textContent=v;});
  document.querySelectorAll('[data-ph-en]').forEach(el=>{const v=el.getAttribute('data-ph-'+l);if(v)el.placeholder=v;});
  localStorage.setItem('ll',l);
  document.querySelectorAll('.mo-title[data-en]').forEach(el=>{const v=el.getAttribute('data-'+l);if(v)el.textContent=v;});
  updateSettingsStatusLabels();
  if (isAuthenticated) {
    loadLoginLogs();
  loadMtproxy();
    loadLogs();
    renderAddrs();
    filterLinks();
  }
  const footer = $m('footer-dedication');
  if (footer) footer.innerHTML = footerTexts[l] || footerTexts['en'];
  document.querySelectorAll('#lang-glass-group .glass-btn').forEach(b => b.classList.remove('active'));
  const activeLangBtn = document.getElementById(`btn-lang-${l}`);
  if (activeLangBtn) activeLangBtn.classList.add('active');
}
async function checkAuth(){try{const r=await fetch('/api/me');if((await r.json()).authenticated){await showDashboard();}else{showLogin();}}catch{showLogin();}}
function showLogin(){isAuthenticated=false;$m('login-page').style.display='';$m('dashboard-page').style.display='none';fetch('/api/public-settings').then(r=>r.json()).then(d=>{if(d.footer_text)$m('login-custom-message').textContent=d.footer_text;}).catch(()=>{});}
async function showDashboard(){
  isAuthenticated=true;
  $m('login-page').style.display='none';
  $m('dashboard-page').style.display='';
  await loadGeneralSettings();
  if (!localStorage.getItem('ll')) {
    const defLang = $m('set-default-lang')?.value || 'en';
    if (defLang) setLang(defLang);
  }
  initChart();
  initDoughnutChart();
  initSpeedChart();
  loadStats();
  loadLinks();
  loadAddrs();
  loadLogs();
  loadLoginLogs();
  loadTelegramSettings();
  setLang(lang);
  startPanelClock();
  syncGlassThemeButtons();
}
function startPanelClock() {
  setInterval(() => {
    const d = new Date();
    d.setMinutes(d.getMinutes() + d.getTimezoneOffset() + timezoneOffset * 60);
    $m('panel-clock').textContent = d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' });
  }, 1000);
}
async function doLogin(){const u=$m('login-user').value.trim();const pw=$m('login-pw').value;$m('login-err').style.display='none';try{const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:pw})});if(r.ok){$m('login-pw').value='';showDashboard();}else $m('login-err').style.display='block';}catch{console.error('Login error');$m('login-err').style.display='block';}}
async function doLogout(){await fetch('/api/logout',{method:'POST'});showLogin();}
document.querySelectorAll('.nav-link[data-page]').forEach(el=>el.addEventListener('click',()=>{switchPage(el.dataset.page);document.getElementById('mainNav').classList.remove('open');}));
function switchPage(id){document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));$m('page-'+id).classList.add('active');if(id==='mtproxy')loadMtproxy();if(id==='outbounds')loadOutbounds();if(id==='aether')startAether();else stopAetherPoll();document.querySelectorAll('.nav-link').forEach(n=>n.classList.toggle('active',n.dataset.page===id));document.querySelectorAll('.mobile-nav .nav-item').forEach(n=>n.classList.toggle('active',n.dataset.page===id));}
document.getElementById('hamburger-btn')?.addEventListener('click',function(e){e.stopPropagation();document.getElementById('mainNav').classList.toggle('open');});
function toast(msg,err=false){const t=$m('toast');t.textContent=msg;t.className='toast'+(err?' err':'')+' show';clearTimeout(t._hide);t._hide=setTimeout(()=>t.classList.remove('show'),3000);}
function fmtB(b){if(!b||b===0)return'0 B';return b>=1073741824?(b/1073741824).toFixed(2)+' GB':b>=1048576?(b/1048576).toFixed(2)+' MB':(b/1024).toFixed(1)+' KB';}
function fmtLim(b){if(!b||b===0)return'∞';const g=b/1073741824;return(g%1===0?g.toFixed(0):g.toFixed(1))+' GB';}
function fmtExp(ea){if(!ea||ea===0)return'∞';const d=new Date(ea)-new Date();if(d<=0)return'Expired';const days=Math.floor(d/86400000);if(days>0)return days+'d';const hours=Math.floor(d/3600000);if(hours>0)return hours+'h';return Math.floor(d/60000)+'m';}
function fmtConns(uuid){const list=liveConns[uuid]||[];if(!list.length)return '<span style="color:var(--text3)">—</span>';return list.map(c=>`<div style="font-size:0.76rem;line-height:1.5;">🌐 ${esc(c.ip)}</div>`).join('');}
function fillOutboundForm(cfg){if(!cfg)return;const set=(id,v)=>{const e=$m(id);if(e&&v!==undefined)e.value=v;};set('ob_dfp',cfg.ob_default_fp||'chrome');set('ob_dsni',cfg.ob_default_sni||'');set('ob_dhost',cfg.ob_default_host||'');set('ob_dalpn',cfg.ob_default_alpn||'http/1.1');set('ob_ws_path',cfg.ob_ws_path||'/ws/{uuid}');set('ob_xhttp_path',cfg.ob_xhttp_path||'/xhttp1/{uuid}');set('ob_http_path',cfg.ob_http_path||'/http/{uuid}');}
async function loadOutbounds(){try{const [t,r]=await Promise.all([fetch('/api/transports'),fetch('/api/outbound-config')]);if(!t.ok)return;const d=await t.json();const cfg=await r.json();const grid=$m('transport-grid');const icons={ws:'🌐',xhttp:'⚡',http:'📡',tcp:'🔌'};const paths={ws:cfg.ob_ws_path||'/ws/{uuid}',xhttp:cfg.ob_xhttp_path||'/xhttp1/{uuid}',http:cfg.ob_http_path||'/http/{uuid}'};let html='';for(const [key,tr] of Object.entries(d)){const status=tr.enabled?'<span style="color:var(--ok)">● Active</span>':'<span style="color:var(--text3)">● Off</span>';const port=tr.port?(':'+tr.port):'';const host=tr.host?(' → '+tr.host+port):'';const pathVal=paths[key]||tr.path_template||'-';html+=`<div class="card"><div style="display:flex;justify-content:space-between;align-items:center;"><div style="font-size:1.1rem;font-weight:700;">${icons[key]||'•'} ${tr.name}</div><div>${status}</div></div><div style="font-size:0.82rem;color:var(--text3);margin:8px 0;">${tr.description||''}</div><div style="font-size:0.85rem;margin-bottom:6px;"><div>Security: <code>${tr.security}</code></div><div>Path: <code>${pathVal}</code></div><div>Endpoint: <code>${tr.port?'port '+tr.port:''}${host}</code></div>${tr.mode?`<div>Mode: <code>${tr.mode}</code></div>`:''}</div></div>`;}grid.innerHTML=html;fillOutboundForm(cfg);}catch(e){console.error('loadOutbounds',e);}}
async function saveOutboundConfig(){const body={ob_default_fp:$m('ob_dfp').value,ob_default_sni:$m('ob_dsni').value.trim(),ob_default_host:$m('ob_dhost').value.trim(),ob_default_alpn:$m('ob_dalpn').value.trim(),ob_ws_path:$m('ob_ws_path').value.trim()||'/ws/{uuid}',ob_xhttp_path:$m('ob_xhttp_path').value.trim()||'/xhttp1/{uuid}',ob_http_path:$m('ob_http_path').value.trim()||'/http/{uuid}'};try{const r=await fetch('/api/outbound-config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(r.ok)toast('Outbound config saved');else toast('Error',true);}catch{toast('Error',true);}}
let aeTimer=null,aeFilled=false;
function aeEsc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
async function aeApi(path,body){try{const r=await fetch('/api/aether/'+path,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});if(r.status===401){showLogin();return null;}let d={};try{d=await r.json();}catch(e){}if(!r.ok||d.ok===false){toast(d.error||('Error '+r.status),true);return null;}return d;}catch(e){toast('Error',true);return null;}}
function aeFmtSec(s){if(s==null)return '—';s=Math.floor(s);const h=Math.floor(s/3600),m=Math.floor((s%3600)/60);return h>0?h+'h '+m+'m':m>0?m+'m '+(s%60)+'s':s+'s';}
function aeFillForm(s){const sch=s.options_schema||{};const fill=(id,list)=>{const el=$m(id);if(!el||el.options.length)return;(list||[]).forEach(v=>{const o=document.createElement('option');o.value=v;o.textContent=v;el.appendChild(o);});};fill('ae-protocol',sch.protocol);fill('ae-transport',sch.transport);fill('ae-scan',sch.scan);fill('ae-ip',sch.ip);fill('ae-noize',sch.noize);const o=s.saved_options||s.options||s.default_options||{};const set=(id,v)=>{const e=$m(id);if(e&&v!==undefined)e.value=v;};set('ae-protocol',o.protocol);set('ae-transport',o.transport);set('ae-scan',o.scan);set('ae-ip',o.ip);set('ae-noize',o.noize);set('ae-port',o.port);$m('ae-httpproxy').checked=!!o.http_proxy;$m('ae-quick').checked=o.quick_reconnect!==false;$m('ae-mode').value=s.outbound_mode||'direct';$m('ae-auto').checked=!!s.auto_start;aeFilled=true;}
function aeReadForm(){return{protocol:$m('ae-protocol').value,transport:$m('ae-transport').value,scan:$m('ae-scan').value,ip:$m('ae-ip').value,noize:$m('ae-noize').value,port:parseInt($m('ae-port').value,10),http_proxy:$m('ae-httpproxy').checked,quick_reconnect:$m('ae-quick').checked};}
function aeRender(s){if(!aeFilled)aeFillForm(s);const col={connected:'var(--green)',error:'var(--red)',stopped:'var(--text3)'}[s.phase]||'var(--yellow)';$m('ae-phase').innerHTML='<span style="color:'+col+'">● '+aeEsc(s.phase)+'</span>';const act=s.outbound_active;$m('ae-out').innerHTML='Outbound: <b>'+aeEsc(s.outbound_mode)+'</b> '+(act?'<span style="color:var(--green)">(users exit via Aether)</span>':'<span style="color:var(--text3)">(users exit directly)</span>');const ex=s.exit;let info=[];if(s.running&&s.options)info.push('SOCKS5 127.0.0.1:'+s.options.port+' · '+s.options.protocol+'/'+s.options.transport+' · scan '+s.options.scan);if(s.gateway)info.push('Gateway: '+aeEsc(s.gateway));if(ex)info.push('Exit: '+aeEsc(ex.ip)+' · '+aeEsc(ex.country)+' via '+aeEsc(ex.colo)+' · '+ex.latency_ms+' ms'+(ex.warp?' · warp '+aeEsc(ex.warp):''));if(s.uptime_sec!=null)info.push('Connected for '+aeFmtSec(s.uptime_sec));if(s.pid)info.push('PID '+s.pid);$m('ae-info').innerHTML=info.join('<br>');const er=$m('ae-err');er.style.display=s.last_error&&s.phase!=='connected'?'block':'none';er.textContent=s.last_error||'';$m('ae-nobin').style.display=s.binary?'none':'block';const note={direct:'Panel users connect from this server\'s own IP (default behaviour).',auto:'Users exit via Aether while it is connected; otherwise they connect directly (the server IP may be exposed during outages).',aether:'Fail-closed: if the tunnel is down, user connections are refused instead of leaking the server IP.'};$m('ae-mode-note').textContent=note[$m('ae-mode').value]||'';const w=s.watchdog||{};$m('ae-wd').innerHTML=(w.enabled?'enabled':'disabled')+' · restarts '+(w.restarts||0)+' · failed checks '+(w.consecutive_failures||0)+'/'+(w.max_failures||0)+(w.last_check_ok===true?' · last check OK':w.last_check_ok===false?' · last check FAILED':'')+(w.next_restart_in_sec!=null?' · restart in '+w.next_restart_in_sec+'s':'')+(w.last_reason?'<br>Last reason: '+aeEsc(w.last_reason):'')+(s.last_good?'<br>Known-good preset saved':'');const lg=$m('ae-logs');const atBottom=lg.scrollTop+lg.clientHeight>=lg.scrollHeight-24;const lc={error:'var(--red)',warn:'var(--yellow)'};lg.innerHTML=(s.logs||[]).map(l=>'<span style="color:'+(lc[l.level]||'var(--text2)')+'">'+aeEsc(l.text)+'</span>').join('\n');if(atBottom)lg.scrollTop=lg.scrollHeight;}
async function loadAether(){const s=await aeApi('status');if(s)aeRender(s);}
function startAether(){aeFilled=false;loadAether();stopAetherPoll();aeTimer=setInterval(loadAether,3000);}
function stopAetherPoll(){if(aeTimer){clearInterval(aeTimer);aeTimer=null;}}
async function aeStart(){const d=await aeApi('start',aeReadForm());if(d){toast('Starting…');loadAether();}}
async function aeRestart(){const d=await aeApi('restart',aeReadForm());if(d){toast('Restarting…');loadAether();}}
async function aeStop(){const d=await aeApi('stop',{});if(d){toast('Stopped');loadAether();}}
async function aeInstall(){toast('Downloading Aether…');const d=await aeApi('install',{});if(d){toast('Installed '+(d.version||''));loadAether();}}
async function aeSaveSettings(){const d=await aeApi('settings',{outbound_mode:$m('ae-mode').value,auto_start:$m('ae-auto').checked});if(d){toast('Saved');loadAether();}}
function setFilter(f,el){cf=f;document.querySelectorAll('.chip').forEach(c=>c.classList.remove('active'));el.classList.add('active');filterLinks();}
function filterLinks(){const q=($m('srch')?.value||'').toLowerCase();let r=allLinks;if(cf==='active')r=r.filter(l=>l.active);else if(cf==='off')r=r.filter(l=>!l.active);if(q)r=r.filter(l=>l.label.toLowerCase().includes(q)||l.uuid.toLowerCase().includes(q));renderLinks(r);}
function renderLinks(links){
  const tb=$m('ltb'),em=$m('lempty');
  if(!links||!links.length){tb.innerHTML='';em.style.display='block';return;}
  em.style.display='none';
  tb.innerHTML=links.map(l=>{
    const u=l.used_bytes||0,lim=l.limit_bytes||0,pct=lim>0?Math.min(100,(u/lim)*100):0,col=pct>90?'var(--red)':pct>70?'var(--yellow)':'var(--primary)',ex=fmtExp(l.expires_at),ec=ex==='Expired'?'var(--red)':ex==='∞'?'var(--text3)':'var(--text2)',cc=l.current_connections||0,mc2=l.max_connections||0,check=selectedUids.has(l.uuid)?'checked':'',flagEmoji=l.flag?codeToFlag(l.flag):'',labelDisplay=(flagEmoji?flagEmoji+' ':'')+esc(l.label);
    return`<tr>
      <td><input type="checkbox" value="${l.uuid}" ${check} onchange="toggleSelectUid('${l.uuid}')"></td>
      <td style="font-weight:600">${labelDisplay}</td>
      <td><span class="tag tag-vless">VLESS</span> <span class="tag" style="opacity:.75;font-size:.7em;">${(l.transport||'ws').toUpperCase()}</span> ${l.encryption&&l.encryption!=='none'?`<span class="tag" style="opacity:.6;font-size:.65em;">${l.encryption}</span>`:''}</td>
      <td style="white-space:nowrap"><div class="pill"><span class="pill-used">${fmtB(u)}</span><div class="pill-bar"><div class="pill-fill" style="width:${pct}%;background:${col}"></div></div><span>${fmtLim(lim)}</span></div></td>
      <td>${cc}/${mc2||'∞'}</td>
      <td style="max-width:180px;">${fmtConns(l.uuid)}</td>
      <td style="color:${ec}">${ex}</td>
      <td><span class="tag ${l.active?'tag-on':'tag-off'}">${l.active?t('on'):t('off')}</span></td>
      <td style="min-width:140px;">
        <div style="display:flex; flex-direction:column; gap:6px; align-items:center;">
          <button class="toggle ${l.active?'on':''}" data-uid="${l.uuid}" onclick="togLink(this)"></button>
          <div style="display:flex; flex-wrap:wrap; gap:4px; justify-content:center;">
            ${l.label === 'This Server is Free' ? `
              <button class="act-btn act-copy" title="${t('copy')}" onclick="cpLink('${esc(l.vless_link)}')"><svg class="ic"><use href="#ic-copy"/></svg></button>
              <button class="act-btn act-sub" title="${t('sub')}" onclick="cpSub('${l.uuid}')"><svg class="ic"><use href="#ic-link"/></svg></button>
              <button class="act-btn act-qr" title="${t('qr')}" onclick="showQR('${esc(l.vless_link)}')"><svg class="ic"><use href="#ic-qr"/></svg></button>
            ` : `
              <button class="act-btn act-edit" title="${t('edit')}" onclick="showEditMo('${l.uuid}')"><svg class="ic"><use href="#ic-edit"/></svg></button>
              <button class="act-btn act-copy" title="${t('copy')}" onclick="cpLink('${esc(l.vless_link)}')"><svg class="ic"><use href="#ic-copy"/></svg></button>
              <button class="act-btn act-sub" title="${t('sub')}" onclick="cpSub('${l.uuid}')"><svg class="ic"><use href="#ic-link"/></svg></button>
              <button class="act-btn act-qr" title="${t('qr')}" onclick="showQR('${esc(l.vless_link)}')"><svg class="ic"><use href="#ic-qr"/></svg></button>
              <button class="act-btn act-json" title="View JSON" onclick="viewJson('${l.uuid}')"><svg class="ic"><use href="#ic-json"/></svg></button>
              <button class="act-btn act-del" title="${t('del')}" onclick="delLink('${l.uuid}')"><svg class="ic"><use href="#ic-trash"/></svg></button>
              <button class="act-btn act-edit" title="Regenerate UUID" onclick="regenerateUUID('${l.uuid}')"><svg class="ic"><use href="#ic-refresh"/></svg></button>
              <button class="act-btn act-del" title="Disconnect" onclick="disconnectLink('${l.uuid}')"><svg class="ic"><use href="#ic-unplug"/></svg></button>
              <button class="act-btn act-sub" title="Copy Subscription Link" onclick="copySubLink('${l.uuid}')"><svg class="ic"><use href="#ic-paperclip"/></svg></button>
            `}
          </div>
        </div>
      </td>
    </tr>`;
  }).join('');
}
function copySubLink(uid) {
    const subUrl = 'https://'+location.host+'/sub/'+uid;
    navigator.clipboard.writeText(subUrl).then(()=>toast('Subscription link copied!')).catch(()=>toast('Failed',true));
}
function toggleSelectUid(uid){selectedUids.has(uid)?selectedUids.delete(uid):selectedUids.add(uid);}
function toggleSelectAll(){const all=$m('select-all');const boxes=document.querySelectorAll('#ltb input[type=checkbox]');if(all.checked){boxes.forEach(c=>{c.checked=true;selectedUids.add(c.value);});}else{boxes.forEach(c=>{c.checked=false;selectedUids.clear();});}}
function batchAction(action){
  if(selectedUids.size===0)return toast('No items selected',true);
  if(action==='delete'&&!confirm('Delete selected?'))return;
  fetch('/api/links/batch',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({uids:Array.from(selectedUids),action})})
    .then(async (r)=>{
      if(!r.ok){
        const d = await r.json();
        toast(d.detail || 'Error', true);
      } else {
        selectedUids.clear(); loadLinks(); loadStats();
      }
    });
}
async function regenerateUUID(uid){const r=await fetch('/api/links/'+uid+'/new-uuid',{method:'POST'});if(r.ok){loadLinks();toast('UUID regenerated');}}
async function disconnectLink(uid){await fetch('/api/links/'+uid+'/disconnect',{method:'POST'});toast('Disconnected');loadLinks();}
let sortCol='created_at',sortDir='desc';
function sortLinks(col){if(sortCol===col)sortDir=sortDir==='asc'?'desc':'asc';else{sortCol=col;sortDir='desc';}allLinks.sort((a,b)=>{let va=a[sortCol]??'',vb=b[sortCol]??'';if(sortCol==='used_bytes'){va=Number(va);vb=Number(vb);}else if(sortCol==='expires_at'){va=va||'';vb=vb||'';}if(va<vb)return sortDir==='asc'?-1:1;if(va>vb)return sortDir==='asc'?1:-1;return 0;});filterLinks();}
async function togLink(el){const uid=el.dataset.uid,l=allLinks.find(x=>x.uuid===uid);if(!l)return;const na=!l.active;try{await fetch('/api/links/'+uid,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({active:na})});l.active=na;filterLinks();loadStats();}catch{toast('Failed',true);}}
async function randomInbound(){const names=['User','Client','Node','Peer'];const n=names[Math.floor(Math.random()*names.length)]+'-'+Math.floor(Math.random()*1000);try{await fetch('/api/links',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({label:n,limit_value:0})});toast(`Created ${n}`);loadLinks();loadStats();}catch{toast('Error',true);}}
function showAddMo(){$m('mo-add').classList.add('show');}
async function createLink(){
  const label=$m('nl').value.trim()||'This Server is Free';
  const uuid=$m('auuid').value.trim();
  const v=parseFloat($m('nv').value)||0,mc=parseInt($m('nc').value)||0,days=parseInt($m('nd').value)||0;
  const flagCode = $m('flag-code-create').value || '';
  const fragment = $m('afrag')?.value?.trim() || '';
  const body={
    label,uuid,limit_value:v,limit_unit:'GB',max_connections:mc,days_valid:days,
    custom_path:$m('ap').value.trim(),custom_sni:$m('asni').value.trim(),
    custom_host:$m('ahost').value.trim(),custom_fp:$m('afp').value.trim(),
    color:$m('alink-color')?.value||'#39ff14', flag: flagCode, fragment: fragment,
    transport: $m('atransport')?.value || 'ws',
    encryption: $m('aenc')?.value || 'none'
  };
  try{
    await fetch('/api/links',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    toast('Created'); $m('mo-add').classList.remove('show'); loadLinks(); loadStats();
  }catch{toast('Error',true);}
}
function showEditMo(uid){
  const l=allLinks.find(x=>x.uuid===uid); if(!l)return;
  $m('eu').value=uid; $m('euuid').value=l.uuid; $m('en2').value=l.label;
  $m('el').value=l.limit_bytes>0?(l.limit_bytes/1073741824):''; $m('ec').value=l.max_connections||''; $m('ed').value='';
  $m('ep').value=l.custom_path||''; $m('esni').value=l.custom_sni||''; $m('ehost').value=l.custom_host||''; $m('efp').value=l.custom_fp||'chrome';
  $m('efrag').value=l.fragment||'';
  if($m('etransport')) $m('etransport').value = l.transport || 'ws';
  if($m('eenc')) $m('eenc').value = l.encryption || 'none';
  onTransportChange('e');
  $m('e-color').value=l.color||'#39ff14';
  const flag = l.flag || '';
  $m('flag-code-edit').value = flag;
  const sel = $m('flag-select-edit');
  if (flag && ['cn','nl','ru','us','ca','ir','de','gb','it','fr','tr','ae'].includes(flag)) {
    sel.value = flag;
    $m('flag-custom-edit').style.display = 'none';
  } else if (flag) {
    sel.value = 'custom';
    $m('flag-custom-edit').style.display = 'block';
    $m('flag-custom-edit').value = flag;
  } else {
    sel.value = '';
    $m('flag-custom-edit').style.display = 'none';
  }
  $m('et').textContent=(lang==='fa'?'ویرایش: ':'EDIT: ')+l.label; $m('mo-edit').classList.add('show');
}
async function saveEdit(){
  const uid=$m('eu').value,v=parseFloat($m('el').value)||0,mc=parseInt($m('ec').value)||0,days=parseInt($m('ed').value)||0;
  const flagCode = $m('flag-code-edit').value || '';
  const fragment = $m('efrag').value.trim() || '';
  const body={
    limit_value:v,limit_unit:'GB',max_connections:mc,label:$m('en2').value.trim(),
    custom_path:$m('ep').value.trim(),custom_sni:$m('esni').value.trim(),
    custom_host:$m('ehost').value.trim(),custom_fp:$m('efp').value.trim(),
    color:$m('e-color').value, flag: flagCode, fragment: fragment,
    transport: $m('etransport')?.value || 'ws',
    encryption: $m('eenc')?.value || 'none'
  };
  if(days)body.days_valid=days;
  try{
    await fetch('/api/links/'+uid,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    toast('Updated'); $m('mo-edit').classList.remove('show'); loadLinks();
  }catch{toast('Error',true);}
}
async function resetTraf(){const uid=$m('eu').value;if(!confirm('Reset?'))return;try{await fetch('/api/links/'+uid,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({reset_usage:true})});toast('Reset');loadLinks();}catch{toast('Error',true);}}
async function addTransportToUser(){const uid=$m('eu').value;if(!uid)return;const t=$m('etransport')?.value||'ws';const enc=$m('eenc')?.value||'none';try{const r=await fetch('/api/links/'+uid,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({transport:t,encryption:enc})});if(!r.ok)throw new Error();toast('Transport updated for user');loadLinks();loadStats();}catch(e){toast('Error',true);}}
function onTransportChange(prefix){const t=$m(prefix+'transport')?.value||'ws';const tcpBox=$m(prefix+'tcp-fields');if(tcpBox)tcpBox.style.display=(t==='tcp')?'block':'none';}
async function delLink(uid){
  if(!confirm('Delete?'))return;
  try{
    const r = await fetch('/api/links/'+uid,{method:'DELETE'});
    if(!r.ok){
      const d = await r.json();
      toast(d.detail || 'Error', true);
    } else {
      toast('Deleted'); loadLinks(); loadStats();
    }
  }catch{toast('Error',true);}
}
function cpLink(txt){navigator.clipboard.writeText(txt).then(()=>toast('Copied!')).catch(()=>toast('Failed',true));}
async function cpSub(uid){
  await navigator.clipboard.writeText('https://'+location.host+'/user/'+uid);
  toast('User Dashboard URL copied!');
}
function showQR(txt){if(txt.length>2000){toast('Link too long for QR',true);return;}const img=$m('qr-img');img.src='https://api.qrserver.com/v1/create-qr-code/?size=280x280&data='+encodeURIComponent(txt);$m('mo-qr').classList.add('show');}
async function viewJson(uid){try{const r=await fetch('/api/links/'+uid+'/json');if(!r.ok){toast('Failed',true);return;}const d=await r.json();$m('json-text').textContent=JSON.stringify(d,null,2);const fname=`${uid}.json`;$m('json-dl').onclick=()=>{const blob=new Blob([JSON.stringify(d,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=fname;a.click();URL.revokeObjectURL(a.href);};$m('mo-json').classList.add('show');}catch{toast('Failed',true);}}
function dlQR(){const a=document.createElement('a');a.href=$m('qr-img').src;a.download='se7osna-qr.png';a.click();}

function updateSpeedDisplaySafe(id, bps) {
  const el = $m(id);
  if (el) el.innerHTML = formatSpeed(bps);
}
async function loadStats(){
  try{const r=await fetch('/stats');if(r.status===401){showLogin();return;}if(!r.ok)return;sData=await r.json();
    // also load live connections for the Inbounds table
    try{const cr=await fetch('/connections');if(cr.ok)liveConns=await cr.json();}catch(e){}
    const now = Date.now();
    if (prevUploadBytes === null || prevDownloadBytes === null) {
      prevUploadBytes = sData.upload_bytes;
      prevDownloadBytes = sData.download_bytes;
      prevStatsTime = now;
      updateSpeedDisplaySafe('sv-down-speed', 0);
      updateSpeedDisplaySafe('sv-up-speed', 0);
    } else {
      const intervalSec = (now - prevStatsTime) / 1000;
      if (intervalSec > 0) {
        let rawUpload = (sData.upload_bytes - prevUploadBytes) / intervalSec;
        let rawDownload = (sData.download_bytes - prevDownloadBytes) / intervalSec;
        if (sData.active_connections === 0) {
          rawUpload = 0;
          rawDownload = 0;
          uploadSpeedAvg = 0;
          downloadSpeedAvg = 0;
        } else {
          uploadSpeedAvg = rawUpload * 0.3 + uploadSpeedAvg * 0.7;
          downloadSpeedAvg = rawDownload * 0.3 + downloadSpeedAvg * 0.7;
        }
        updateSpeedDisplaySafe('sv-down-speed', downloadSpeedAvg);
        updateSpeedDisplaySafe('sv-up-speed', uploadSpeedAvg);
        updSpeedChart(uploadSpeedAvg, downloadSpeedAvg);
      }
      prevUploadBytes = sData.upload_bytes;
      prevDownloadBytes = sData.download_bytes;
      prevStatsTime = now;
    }
    safeSetHTML('sv-traffic',(sData.total_traffic_mb||0)+'<span class="stat-unit"> MB</span>');
    safeSetText('sv-requests',sData.total_requests); safeSetText('sv-uptime',sData.uptime);
    safeSetHTML('sv-disk',(sData.disk_free_gb||0)+'<span class="stat-unit"> GB</span>');
    safeSetText('last-up',t('updatedAt',{time:getLocalTimeString()}));
    if(sData.cpu_percent!==undefined&&sData.cpu_percent!==null){
      const c=sData.cpu_percent;
      safeSetText('cpu-v',c.toFixed(1)+'%'); const bar=$m('cpu-b'); if(bar)bar.style.width=c+'%';
    } else { safeSetText('cpu-v','N/A'); const bar=$m('cpu-b'); if(bar)bar.style.width='0%'; }
    if(sData.memory_percent!==undefined){const m=sData.memory_percent;safeSetText('mem-v',m.toFixed(1)+'%');const bar=$m('mem-b');if(bar)bar.style.width=m+'%';}
    const monthlyUsageGB=sData.monthly_usage_bytes?sData.monthly_usage_bytes/1e9:0;
    const monthlyLimitGB=sData.monthly_limit_bytes?sData.monthly_limit_bytes/1e9:0;
    safeSetHTML('sv-monthly',monthlyUsageGB.toFixed(1)+' GB'+(monthlyLimitGB>0?' / '+monthlyLimitGB.toFixed(1)+' GB':''));
    updChart(); updDoughnutChart();
  }catch(err){console.error('loadStats error:',err);}
}
function formatSpeed(bps){if(bps<1024)return bps.toFixed(1)+' B/s';const kbps=bps/1024;if(kbps<1024)return kbps.toFixed(1)+' KB/s';const mbps=kbps/1024;return mbps.toFixed(2)+' MB/s';}
function updateSpeedDisplay(id,bps){const el=$m(id);if(el)el.innerHTML=formatSpeed(bps);}
function safeSetText(id,text){const el=$m(id);if(el)el.textContent=text;}
function safeSetHTML(id,html){const el=$m(id);if(el)el.innerHTML=html;}
async function loadLinks(){try{const r=await fetch('/api/links');if(r.status===401){showLogin();return;}if(!r.ok)return;const d=await r.json();allLinks=d.links||[];filterLinks();}catch(e){console.error('loadLinks error:',e);}}
let mtState=null;
async function loadMtproxy(){
  try{
    const r=await fetch('/api/mtproxy');
    if(!r.ok)return;
    const d=await r.json();mtState=d;
    $m('mt-running').textContent = d.running ? 'Running' : (d.enabled ? 'Stopped' : 'Disabled');
    $m('mt-running').style.color = d.running ? '#4ade80' : '#f87171';
    $m('mt-bind').textContent = d.bind_port;
    $m('mt-endpoint').textContent = d.public_host + ':' + d.public_port;
    $m('mt-front').textContent = d.fake_domain || '-';
    $m('mt-restarts').textContent = d.restarts;
    $m('mt-secret').value = d.secret || '';
    $m('mt-link').value = d.tg_link || '';
    $m('mt-bind-port').value = d.bind_port || '';
    $m('mt-pub-host').value = d.manual_host || '';
    $m('mt-pub-port').value = d.manual_port || '';
    $m('mt-warn').style.display = d.endpoint_confirmed ? 'none' : '';
    const er=$m('mt-err-row');
    if(d.error){er.style.display='';$m('mt-err').textContent=d.error;}else{er.style.display='none';}
  }catch(e){console.error('mtproxy load failed',e);}
}
function copyMt(id){const v=$m(id).value;if(!v){toast('Nothing to copy',true);return;}navigator.clipboard.writeText(v).then(()=>toast('Copied')).catch(()=>toast('Copy failed',true));}
function qrMt(){const v=$m('mt-link').value;if(!v){toast('No link yet',true);return;}showQR(v);}
async function regenMt(){
  if(!confirm('Generate a new secret? Existing users must re-import the link.'))return;
  const dom=$m('mt-newdomain').value.trim();
  try{
    const r=await fetch('/api/mtproxy/regenerate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(dom?{fake_domain:dom}:{})});
    const d=await r.json();
    if(!r.ok)throw new Error(d.detail||'Failed');
    $m('mt-newdomain').value='';
    await loadMtproxy();
    toast('New secret generated');
  }catch(e){toast(e.message||'Error',true);}
}
async function saveEndpoint(){
  const bp=$m('mt-bind-port').value.trim();
  const ph=$m('mt-pub-host').value.trim();
  const pp=$m('mt-pub-port').value.trim();
  const body={bind_port:bp?parseInt(bp,10):null,public_host:ph,public_port:pp?parseInt(pp,10):null};
  try{
    const r=await fetch('/api/mtproxy/set-endpoint',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const d=await r.json();
    if(!r.ok)throw new Error(d.detail||'Failed');
    await loadMtproxy();
    toast('Endpoint saved — proxy restarted');
  }catch(e){toast(e.message||'Error',true);}
}
async function restartMtproxy(){
  try{
    const r=await fetch('/api/mtproxy/restart',{method:'POST'});
    const d=await r.json();
    if(!r.ok)throw new Error(d.detail||'Failed');
    await loadMtproxy();
    toast('MTProxy restarted');
  }catch(e){toast(e.message||'Error',true);}
}
async function chgUser(){const nu=$m('nusr').value.trim(),cur=$m('usr-cpw').value;if(!nu||!cur){toast('Fill fields',true);return;}if(!/^[A-Za-z0-9._-]{3,32}$/.test(nu)){toast('Username must be 3-32 chars: letters, digits, . _ -',true);return;}try{const r=await fetch('/api/change-username',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({new_username:nu,current_password:cur})});const d=await r.json();if(!r.ok)throw new Error(d.detail);$m('nusr').value='';$m('usr-cpw').value='';$m('cur-username').value=d.username;toast('Username updated');}catch(e){toast(e.message||'Error',true);}}
async function chgPw(){const cur=$m('cpw').value,nw=$m('npw').value;if(!cur||!nw){toast('Fill fields',true);return;}if(nw.length<8){toast('Password must be at least 8 characters',true);return;}if(!/[A-Z]/.test(nw)||!/[a-z]/.test(nw)||!/[0-9]/.test(nw)){toast('Password must contain uppercase, lowercase, and digit',true);return;}try{const r=await fetch('/api/change-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({current_password:cur,new_password:nw})});if(!r.ok)throw new Error((await r.json()).detail||'Error');toast('Password updated');}catch(e){toast(e.message,true);}}
async function restartPanel(){if(!confirm('Restart panel? Active connections will drop for a few seconds.'))return;try{const r=await fetch('/api/panel/restart',{method:'POST'});if(r.ok){toast('Restarting...');}else{toast('Restart failed',true);}}catch{toast('Restarting...');}}
function initChart(){
  const ctx=$m('tc'); if(!ctx||tChart)return;
  tChart=new Chart(ctx,{
    type:'bar',
    data:{labels:[],datasets:[{label:'MB',data:[],backgroundColor:'rgba(57,255,20,0.6)',borderColor:'#39ff14',borderWidth:1,barPercentage:0.7,categoryPercentage:0.9}]},
    options:{
      responsive:true, maintainAspectRatio:false,
      plugins:{legend:{display:false}},
      scales:{x:{ticks:{color:'rgba(57,255,20,0.3)',maxRotation:45}},y:{ticks:{color:'rgba(57,255,20,0.3)',callback:v=>v+' MB'},beginAtZero:true}}
    }
  });
  updChartColors();
}
function updChartColors(){if(!tChart)return;const col=theme==='light'?'#000':'rgba(57,255,20,0.4)';tChart.options.scales.x.ticks.color=col;tChart.options.scales.y.ticks.color=col;tChart.update();}
function getPanelTime(isoString){const d=new Date(isoString);if(!isNaN(d)){d.setMinutes(d.getMinutes()+d.getTimezoneOffset()+timezoneOffset*60);}return d;}
function getLocalTimeString(){const d=new Date();d.setMinutes(d.getMinutes()+d.getTimezoneOffset()+timezoneOffset*60);return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`;}
function updChart(){
  if(!tChart||!sData.hourly_traffic)return;
  const labels = []; const data = [];
  for(let h=0;h<24;h++){
    const key = `${h.toString().padStart(2,'0')}:00`;
    labels.push(key);
    data.push(Math.round((sData.hourly_traffic[key]||0)/1048576));
  }
  tChart.data.labels = labels;
  tChart.data.datasets[0].data = data;
  tChart.update();
}
let doughnutChart=null;
function initDoughnutChart(){const ctx=$m('doughnut-chart');if(!ctx||doughnutChart)return;doughnutChart=new Chart(ctx,{type:'doughnut',data:{labels:[],datasets:[{data:[],backgroundColor:[]}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:'bottom'},tooltip:{callbacks:{label:ctx=>`${ctx.label}: ${ctx.raw>=1e9?(ctx.raw/1e9).toFixed(1)+' GB':(ctx.raw/1e6).toFixed(1)+' MB'}`}}}}});}
function updDoughnutChart(){if(!doughnutChart)return;const labels=[],data=[],colors=[];allLinks.filter(l=>l.used_bytes>0).forEach(l=>{labels.push(l.label);data.push(l.used_bytes);colors.push(l.color||'#39ff14');});doughnutChart.data.labels=labels;doughnutChart.data.datasets[0].data=data;doughnutChart.data.datasets[0].backgroundColor=colors;doughnutChart.update();}
let speedChart=null,speedHistory=[];
function initSpeedChart(){
  const ctx=$m('speed-chart');if(!ctx||speedChart)return;
  speedChart=new Chart(ctx,{type:'line',data:{labels:[],datasets:[{label:'DL',borderColor:'#4ade80',data:[],tension:0.2},{label:'UL',borderColor:'#f87171',data:[],tension:0.2}]},options:{responsive:true,maintainAspectRatio:false,plugins:{tooltip:{callbacks:{label:ctx=>ctx.dataset.label+': '+formatSpeed(ctx.raw)}}},scales:{y:{max:undefined,beginAtZero:true,ticks:{callback:v=>formatSpeed(v)}}}}});
}
function updSpeedChart(up,down){
  if(!speedChart)return;
  const t=getLocalTimeString();
  speedHistory.push({t,up,down});
  if(speedHistory.length>60)speedHistory.shift();
  const maxVal = Math.max(...speedHistory.map(s=>Math.max(s.up,s.down)), 1);
  speedChart.options.scales.y.max = maxVal * 1.2;
  speedChart.data.labels=speedHistory.map(s=>s.t);
  speedChart.data.datasets[0].data=speedHistory.map(s=>s.down);
  speedChart.data.datasets[1].data=speedHistory.map(s=>s.up);
  speedChart.update();
}
async function loadAddrs(){try{const r=await fetch('/api/addresses');if(r.status===401){showLogin();return;}if(!r.ok)return;allAddrs=(await r.json()).addresses||[];renderAddrs();}catch(e){console.error('loadAddrs error:',e);}}
function renderAddrs(){const el=$m('addr-list');if(!el)return;if(!allAddrs.length){el.innerHTML='<div style="color:var(--text3);font-size:0.9rem">No addresses added</div>';return;}el.innerHTML=allAddrs.map((a,i)=>`<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:var(--surface3);border:1px solid var(--border);border-radius:10px;margin-bottom:6px"><div style="display:flex;align-items:center;gap:8px"><input type="checkbox" class="addr-checkbox" data-index="${i}" ${selectedAddrIndices.has(i)?'checked':''} onchange="toggleSelectAddr(${i})"><span style="font-size:0.9rem;font-weight:600">${esc(a)}</span></div><div style="display:flex;gap:4px;"><button class="act-btn act-edit" onclick="showEditAddr(${i})">${svgic('edit')}</button><button class="act-btn act-del" onclick="delAddr(${i})">${svgic('trash')}</button></div></div>`).join('');}
function toggleSelectAddr(i){selectedAddrIndices.has(i)?selectedAddrIndices.delete(i):selectedAddrIndices.add(i);}
async function bulkDeleteAddrs(){if(selectedAddrIndices.size===0)return toast('No addresses selected',true);if(!confirm('Delete selected addresses?'))return;const indices = Array.from(selectedAddrIndices);try{const r=await fetch('/api/addresses/bulk-delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({indices})});if(r.ok){selectedAddrIndices.clear();await loadAddrs();toast('Deleted selected');}}catch(e){toast('Error',true);}}
function showEditAddr(i){editingAddrIndex=i;$m('edit-addr-input').value=allAddrs[i];$m('mo-addr-edit').classList.add('show');}
async function saveAddrEdit(){const newAddr=$m('edit-addr-input').value.trim();if(!newAddr)return toast('Invalid address',true);try{const r=await fetch('/api/addresses/'+editingAddrIndex,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({address:newAddr})});if(r.ok){toast('Address updated');$m('mo-addr-edit').classList.remove('show');await loadAddrs();}else{const d=await r.json();toast(d.detail||'Error updating',true);}}catch(e){toast('Error',true);}}
async function addBatchAddrs(){const raw=$m('batch-addrs').value;const lines=raw.split('\n').map(l=>l.trim()).filter(l=>l);if(!lines.length)return;try{const r=await fetch('/api/addresses/batch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({addresses:lines})});if(r.status===401){showLogin();return;}const d=await r.json();toast(`Added ${d.added} addresses`+(d.errors?` (${d.errors} errors)`:''));$m('batch-addrs').value='';await loadAddrs();}catch(e){toast('Batch add failed',true);}}
async function deleteAllAddrs(){if(!confirm('Delete all addresses?'))return;try{await fetch('/api/addresses',{method:'DELETE'});toast('All deleted');await loadAddrs();}catch{toast('Error',true);}}
async function delAddr(i){if(!confirm('Delete?'))return;try{await fetch('/api/addresses/'+i,{method:'DELETE'});toast('Deleted');await loadAddrs();}catch{toast('Error',true);}}
async function exportLinks(){try{const r=await fetch('/api/export-links');const data=await r.json();const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='se7osna-links.json';a.click();}catch{toast('Export failed',true);}}
async function importLinks(input){const file=input.files[0];if(!file)return;try{const text=await file.text();const data=JSON.parse(text);const r=await fetch('/api/import-links',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const res=await r.json();toast(`Imported ${res.imported} links`);loadLinks();loadStats();}catch{toast('Import failed',true);}input.value='';}

async function loadLogs(){try{const r=await fetch('/api/logs');if(r.status===401){showLogin();return;}const d=await r.json();const logs=d.logs||[];const tbody=$m('logs-tbody'),empty=$m('logs-empty');if(!tbody)return;if(!logs.length){tbody.innerHTML='';empty.style.display='block';return;}empty.style.display='none';tbody.innerHTML=logs.map((l,i)=>{const local=getPanelTime(l.time);return`<tr><td>${i+1}</td><td>${local.toISOString().replace('T',' ').split('.')[0]}</td><td>${esc(l.type||'Event')}</td><td>${esc(l.error||'')}</td></tr>`}).join('');}catch(err){console.error('loadLogs error:',err);}}
async function loadLoginLogs(){try{const r=await fetch('/api/login-logs');if(!r.ok)return;const d=await r.json();const tbody=$m('login-logs-tbody');if(!tbody)return;tbody.innerHTML=d.logs.map(l=>`<tr><td>${timeAgo(l.timestamp)}</td><td><div style="font-weight:600">${esc(l.ip)}</div><div style="font-size:0.7rem;color:var(--text3);max-width:160px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${esc(l.user_agent)}">${esc(l.user_agent)}</div></td><td style="color:${l.success?'var(--green)':'var(--red)'}">${l.success?svgic('check')+' '+t('success'):svgic('x')+' '+t('failed')}</td></tr>`).join('');}catch(e){}}
function timeAgo(ts){const then=new Date(ts),now=new Date(),diff=Math.floor((now-then)/1000);if(lang==='fa'){if(diff<60)return t('justNow');if(diff<3600)return t('minsAgo',{n:Math.floor(diff/60)});if(diff<86400)return t('hoursAgo',{n:Math.floor(diff/3600)});return new Date(ts).toLocaleDateString('fa-IR');}else{if(diff<60)return t('justNow');if(diff<3600)return t('minsAgo',{n:Math.floor(diff/60)});if(diff<86400)return t('hoursAgo',{n:Math.floor(diff/3600)});return new Date(ts).toLocaleDateString();}}
async function loadTelegramSettings(){try{const r=await fetch('/api/settings');if(r.status===401){showLogin();return;}const d=await r.json();$m('tg-token').value=d.tg_bot_token||'';$m('tg-chat-id').value=d.tg_chat_id||'';$m('tg-interval').value=d.telegram_interval||'1';const events=(d.telegram_events||'').split(',');document.querySelectorAll('.tg-event').forEach(cb=>cb.checked=events.includes(cb.value));$m('tg-templates-en').value=d.telegram_templates_en||'{"quota_90":"⚠️ {label} ({uid}) used 90% of quota","login":"🔐 SE7O-SNA Panel login\\n🌐 IP: {ip}\\n🤖 UA: {ua}\\n📅 {time}","expiry":"⏰ {label} expired","error":"❌ Error on {label}: check logs"}';$m('tg-templates-fa').value=d.telegram_templates_fa||'{"quota_90":"⚠️ {label} ({uid}) ۹۰٪ کوتا","login":"🔐 ورود SE7O-SNA\\n🌐 IP: {ip}\\n🤖 UA: {ua}\\n📅 {time}","expiry":"⏰ {label} منقضی شد","error":"❌ خطا در {label}: بررسی شود"}';
const tgLang = d.telegram_lang || 'en';
const toggle = $m('tg-lang-toggle');
if (tgLang === 'fa') {
    toggle.classList.remove('on');
    $m('tg-lang-label').textContent = 'فارسی';
    $m('tg-lang-hidden').value = 'fa';
} else {
    toggle.classList.add('on');
    $m('tg-lang-label').textContent = 'English';
    $m('tg-lang-hidden').value = 'en';
}}catch(err){console.error('loadTelegram error:',err);}}
async function saveTelegramSettings(){const token=$m('tg-token').value.trim(),chat=$m('tg-chat-id').value.trim();const interval=$m('tg-interval').value.trim();const events=Array.from(document.querySelectorAll('.tg-event:checked')).map(cb=>cb.value).join(',');const templates_en=$m('tg-templates-en').value.trim();const templates_fa=$m('tg-templates-fa').value.trim();const tglang=$m('tg-lang-hidden').value;try{await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tg_bot_token:token,tg_chat_id:chat,telegram_interval:interval,telegram_events:events,telegram_templates_en:templates_en,telegram_templates_fa:templates_fa,telegram_lang:tglang})});toast('Saved');}catch{toast('Error',true);}}
async function testTelegram(){const token=$m('tg-token').value.trim(),chat=$m('tg-chat-id').value.trim();if(!token||!chat){toast('Fill token and chat ID',true);return;}const tglang=$m('tg-lang-hidden').value;try{const res=await fetch('/api/telegram/test',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tg_bot_token:token,tg_chat_id:chat,lang:tglang})});if(res.ok){toast('Test message sent!');}else{const d=await res.json().catch(()=>({}));toast(d.detail||'Failed to send',true);}}catch{toast('Network error contacting panel',true);}}
function toggleTgLang() {
    const toggle = $m('tg-lang-toggle');
    toggle.classList.toggle('on');
    const isEn = toggle.classList.contains('on');
    $m('tg-lang-label').textContent = isEn ? 'English' : 'فارسی';
    $m('tg-lang-hidden').value = isEn ? 'en' : 'fa';
}
function previewTemplate() {
    const isEn = document.getElementById('tg-lang-toggle').classList.contains('on');
    const targetId = isEn ? 'tg-templates-en' : 'tg-templates-fa';
    const textarea = document.getElementById(targetId);
    const previewDiv = document.getElementById('tg-preview');
    if (!textarea || !previewDiv) return;
    try {
        const sanitizedValue = textarea.value.replace(/[\u0000-\u001f]/g, function(ch) {
            if (ch === '\n') return '\\n';
            if (ch === '\r') return '\\r';
            if (ch === '\t') return '\\t';
            return '';
        });
        const templates = JSON.parse(sanitizedValue);
        const mockData = {
            label: "SE7O_User", uid: "se7o-7b8c-49ed-b45a",
            ip: "85.201.32.44", ua: "Mozilla/5.0 (iPhone; iOS 18)",
            time: new Date().toISOString().replace('T', ' ').substring(0, 19)
        };
        let previewHTML = "";
        for (const [key, templateText] of Object.entries(templates)) {
            let text = templateText;
            text = text.replace(/{label}/g, mockData.label).replace(/{uid}/g, mockData.uid)
                       .replace(/{ip}/g, mockData.ip).replace(/{ua}/g, mockData.ua).replace(/{time}/g, mockData.time);
            previewHTML += `<div style="margin-bottom: 10px; border-bottom: 1px solid var(--border); padding-bottom: 6px;">`;
            previewHTML += `<span style="color: var(--primary); font-weight: bold; font-size: 0.8rem;">[${key}]:</span><br>`;
            previewHTML += `<span>${text}</span></div>`;
        }
        const mockDomain = window.location.host || "your-domain.com";
        previewHTML += `<div style="margin-top: 6px; padding-top: 4px; color: #4caf50;">`;
        previewHTML += `⚠️ <i>Auto Appended:</i><br>Open SE7O-SNA Panel (Link: https://${mockDomain}/panel)`;
        previewHTML += `</div>`;
        previewDiv.innerHTML = previewHTML;
        previewDiv.style.border = "1px solid var(--primary)";
    } catch (e) {
        previewDiv.innerHTML = `<span style="color: #ff4d4f; font-weight: 600;">❌ EN/FA Invalid JSON:</span><br><small style="color: #ff7875;">${e.message}</small>`;
        previewDiv.style.border = "1px solid #ff4d4f";
    }
}
async function loadGeneralSettings(){try{const r=await fetch('/api/settings');if(!r.ok)return;const d=await r.json();$m('set-footer').value=d.footer_text||'';$m('set-default-path').value=d.default_path||'';timezoneOffset=parseFloat(d.timezone_offset)||0;$m('set-default-limit').value=d.default_limit_bytes?(parseInt(d.default_limit_bytes)/1073741824).toFixed(1):'';$m('set-default-expiry').value=d.default_expiry_days||'';$m('set-default-maxconn').value=d.default_max_connections||'';$m('set-monthly-limit').value=d.monthly_limit_gb||'';$m('set-keep-alive-interval').value=d.keep_alive_interval||'300';
updateSettingsStatus(d);
updateDashboardStatusCards(d);
if (d.keep_alive_mode) {
    setKeepAliveMode(d.keep_alive_mode);
    $m('set-keepalive-enabled').value = d.keep_alive_enabled === '1' ? '1' : '0';
    const card = $m('card-keepalive');
    if (d.keep_alive_enabled === '1') { card.classList.add('active'); card.classList.remove('inactive'); }
    else { card.classList.add('inactive'); card.classList.remove('active'); }
}
if(timezoneOffset===3.5)setPanelTZ(3.5,'Tehran');else if(timezoneOffset===0)setPanelTZ(0,'UTC');else{toggleCustomTZInput(true);$m('custom-tz-value').value=timezoneOffset;}
const savedTheme = d.theme_color || 'dark'; setPanelTheme(savedTheme);}catch(e){}}
async function saveGeneralSettings(){const footer=$m('set-footer').value.trim();const defPath=$m('set-default-path').value.trim();let tz;const preset=$m('set-tz-preset')?.value;if(preset==='custom')tz=$m('set-tz-custom').value.trim();else tz=preset;const logEnabled=$m('set-log-toggle').value;const themeColor=$m('set-theme-color')?.value||theme;const defLang=$m('set-default-lang')?.value||lang;const defLimit=parseFloat($m('set-default-limit').value)*1073741824;const defExpiry=$m('set-default-expiry').value.trim();const defMaxConn=$m('set-default-maxconn').value.trim();const monthlyLimit=$m('set-monthly-limit').value.trim();const keepAliveInterval=$m('set-keep-alive-interval').value.trim();const keepAliveEnabled=$m('set-keepalive-enabled').value;var keepAliveModeEl = $m('set-keepalive-mode'); var keepAliveMode = keepAliveModeEl ? keepAliveModeEl.value : 'simple';const autoDisable=$m('set-auto-disable').value;const tgReport=$m('set-tg-report').value;const tgNotify=$m('set-tg-notify').value;try{await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({footer_text:footer,default_path:defPath,timezone_offset:tz,log_enabled:logEnabled,theme_color:themeColor,default_lang:defLang,default_limit_bytes:isNaN(defLimit)?'':String(Math.round(defLimit)),default_expiry_days:defExpiry,default_max_connections:defMaxConn,monthly_limit_gb:monthlyLimit,keep_alive_interval:keepAliveInterval,keep_alive_enabled:keepAliveEnabled,keep_alive_mode:keepAliveMode,auto_disable_enabled:autoDisable,telegram_report_enabled:tgReport,telegram_notify_enabled:tgNotify})});timezoneOffset=parseFloat(tz)||0;toast('Saved');loadGeneralSettings();}catch{toast('Error',true);}}
function generateUUID(id){const uuid=crypto.randomUUID?crypto.randomUUID():'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g,c=>{const r=Math.random()*16|0;return(c=='x'?r:(r&0x3|0x8)).toString(16);});$m(id).value=uuid;}
function toggleAdv(id){const el=$m(id);el.style.display=el.style.display==='none'?'block':'none';}
function filterLogs(){const q=($m('log-search').value||'').toLowerCase();document.querySelectorAll('#logs-tbody tr').forEach(row=>{if(!q){row.style.display='';return;}row.style.display=row.innerText.toLowerCase().includes(q)?'':'none';});}
function clearLogSearch(){$m('log-search').value='';filterLogs();}
async function clearLogs(){if(!confirm('Clear all logs?'))return;await fetch('/api/logs/clear',{method:'DELETE'});loadLogs();}
async function fetchLogSize(){const r=await fetch('/api/logs/size');const d=await r.json();toast(`Log entries: ${d.count}, Size: ${d.size_kb} KB`);}
async function resetAllSettings() {
    const msg = lang === 'fa' ? 'آیا مطمئن هستید؟ تمام تنظیمات (به جز رمز عبور) بازنشانی می‌شوند.' : 'Are you sure? All settings (except password) will return to defaults.';
    if (!confirm(msg)) return;
    try {
        const r = await fetch('/api/settings/reset', { method: 'POST' });
        if (!r.ok) throw new Error((await r.json()).detail);
        toast(lang === 'fa' ? 'تنظیمات بازنشانی شد. در حال بارگذاری مجدد...' : 'Settings reset. Reloading...');
        setTimeout(() => location.reload(), 1500);
    } catch (e) {
        toast(e.message, true);
    }
}
document.addEventListener('keydown',e=>{if(e.ctrlKey||e.metaKey){const pages=['dashboard','inbounds','addresses','logs','telegram','settings'];const num=parseInt(e.key);if(num>=1&&num<=pages.length)switchPage(pages[num-1]);}});
if(window.matchMedia('(prefers-color-scheme: dark)').matches && !localStorage.getItem('theme'))setTheme('dark');
setTheme(theme);setLang(lang);checkAuth();
setInterval(()=>{if(isAuthenticated){loadStats();loadLinks();}},12000);
</script>
</body>
</html>"""
