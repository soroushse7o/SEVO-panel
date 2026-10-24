# ادغام ASiRi ↔ SE7O-SNA — راهنما / Merge notes

## چه چیزی عوض شد
SE7O-SNA پایه است. هر اتصال کاربران پنل (WS، XHTTP، HTTP، Raw-TCP) حالا به‌جای اتصال مستقیم،
از تابع `open_upstream()` در `app/services/upstream.py` رد می‌شود. این تابع سه حالت دارد:

| حالت | رفتار |
| --- | --- |
| `direct` (پیش‌فرض) | مثل قبل، اتصال مستقیم از IP سرور |
| `auto` | تا وقتی Aether وصل است از آن؛ وگرنه مستقیم |
| `aether` | همیشه از Aether. اگر تونل قطع باشد اتصال **رد می‌شود** (fail-closed) و IP سرور لو نمی‌رود |

مدیریت خود Aether (از ASiRi به پایتون پورت شد) در `app/services/aether.py`:
اجرای باینری، پارس لاگ و فاز اتصال، watchdog با backoff نمایی، بازگشت به آخرین پریست سالم،
نصب با چک‌سام، و ذخیره‌ی تنظیمات در جدول `settings` (پس روی Volume ماندگار است).

- API: `/api/aether/{status,start,stop,restart,install,settings}` (با همان نشست JWT پنل)
- UI: تب جدید **Aether** (دسکتاپ و موبایل)
- اعلان تلگرام: رویداد جدید `tunnel_down` (در تب Telegram تیکش را بزنید)
- Dockerfile: مرحله‌ی دانلود Aether با نسخه‌ی پین‌شده و بررسی sha256

## متغیرهای محیطی (همه اختیاری)
`AETHER_OUTBOUND` (direct|auto|aether، روی تنظیم پنل اولویت دارد)، `AETHER_AUTO_START=1`،
`AETHER_BIN`، `AETHER_DIR`، `AETHER_VERSION`، و `WATCHDOG_*` مثل ASiRi.

## استفاده
1. دیپلوی؛ در تب Aether اگر باینری نبود «Install» را بزنید (در Docker از قبل هست).
2. Start. صبر کنید فاز `connected` شود.
3. «Exit mode» را روی `auto` یا `aether` بگذارید و Save.

## پورت نشده / محدودیت‌ها
- بخش‌های ASiRi که پورت **نشدند**: «بهترین کانفیگ» (sweep)، gateway‌های SOCKS5/HTTP/Shadowsocks،
  ورودی Trojan، رله‌ی TCP برای Railway، و watchdog مبتنی بر probe خارجی (فقط probe داخلی از SOCKS5).
- Aether فقط TCP است؛ UDP از مسیر Aether کار نمی‌کند.
- با `aether` حالت fail-closed، هنگام scan/connect اولیه اتصال کاربران رد می‌شود.

## مجوز (مهم)
منطق مدیریت Aether از ASiRi-web-panel (**AGPL-3.0**) پورت شده و SE7O-SNA زیر **MIT** است.
اگر ASiRi از خودتان نیست، پروژه‌ی ترکیبی باید AGPL-3.0 شود (و سورس برای کاربران شبکه‌ای در دسترس باشد).
فایل LICENSE را دست نزده‌ام؛ تصمیم با شماست.

## تست
`python test_upstream.py` — بدون وب‌استک و اینترنت: SOCKS5 جعلی (دامنه/IPv4/IPv6/رد)، سه حالت خروج،
پارس لاگ و آرگومان‌ها، و چرخه‌ی کامل با باینری جعلی (start → connected → kill → ری‌استارت watchdog → stop).
`test_endpoints_defined.py` حالا مسیرهای `/api/aether/*` را هم چک می‌کند (نیاز به نصب requirements).

## اصلاح جانبی
تابع `esc()` در `panel_html.py` عملاً هیچ‌چیز escape نمی‌کرد (`&`→`&`، `<`→`<`)؛ برچسب‌های لینک بدون
escape در HTML می‌نشستند (XSS). اصلاح شد.
