# -*- coding: utf-8 -*-
"""
Jarvis - sistem araclari.

AI'nin cagirabildigi yerel yetenekler: uygulama/web ac, ses kontrolu,
ekran goruntusu, kilit ekrani, sistem bilgisi, dosya oku/yaz, zaman.
Windows odaklidir; diger sistemlerde guvenli sekilde zarar vermez.
"""

import os
import sys
import time
import shutil
import platform
import subprocess
import webbrowser
import json
import urllib.request
import urllib.parse

IS_WINDOWS = os.name == "nt"

WORK_DIR = os.path.join(os.path.expanduser("~"), "Documents", "Jarvis")


def _ensure_work_dir():
    try:
        os.makedirs(WORK_DIR, exist_ok=True)
    except Exception:  # noqa: BLE001
        pass


APP_ALIASES = {
    "not defteri": "notepad", "notepad": "notepad", "not defterini": "notepad",
    "hesap makinesi": "calc", "hesap makinesini": "calc", "calculator": "calc",
    "kalkulator": "calc", "calc": "calc",
    "boyama": "mspaint", "paint": "mspaint", "paint'i": "mspaint",
    "resim": "mspaint",
    "dosya gezgini": "explorer", "gezgin": "explorer", "explorer": "explorer",
    "klasor": "explorer", "bilgisayarim": "explorer",
    "chrome": "chrome", "google chrome": "chrome",
    "edge": "msedge", "microsoft edge": "msedge",
    "firefox": "firefox",
    "spotify": "spotify",
    "vs code": "code", "vscode": "code", "visual studio code": "code",
    "terminal": "wt", "komut istemi": "cmd", "cmd": "cmd", "powershell": "powershell",
    "ayarlar": "ms-settings:", "settings": "ms-settings:",
    "gorev yoneticisi": "taskmgr", "task manager": "taskmgr",
    "muzik": "spotify", "takvim": "outlookcal:",
    "postaci": "outlook", "mail": "outlook",
    "youtube": "https://www.youtube.com", "you tube": "https://www.youtube.com",
}

URL_HINTS = (".com", ".net", ".org", ".tr", ".dev", ".io", ".gov", ".edu",
             "http://", "https://", "www.")

APP_WEB = {
    "youtube": "https://www.youtube.com", "you tube": "https://www.youtube.com",
    "spotify": "https://open.spotify.com",
    "whatsapp": "https://web.whatsapp.com",
    "instagram": "https://www.instagram.com",
    "twitter": "https://twitter.com", "x": "https://x.com",
    "facebook": "https://www.facebook.com",
    "gmail": "https://mail.google.com", "mail": "https://mail.google.com",
    "google": "https://www.google.com",
    "harita": "https://maps.google.com", "maps": "https://maps.google.com",
    "github": "https://github.com",
    "chatgpt": "https://chat.openai.com",
    "gemini": "https://gemini.google.com",
    "netflix": "https://www.netflix.com",
    "trendyol": "https://www.trendyol.com",
    "google translate": "https://translate.google.com", "ceviri": "https://translate.google.com",
}


def app_web_url(name):
    return APP_WEB.get((name or "").strip().lower())


def get_datetime():
    now = time.localtime()
    gunler = ["Pazartesi", "Sali", "Carsamba", "Persembe", "Cuma", "Cumartesi", "Pazar"]
    return {
        "saat": time.strftime("%H:%M", now),
        "tarih": time.strftime("%d.%m.%Y", now),
        "gun": gunler[now.tm_wday],
        "metin": time.strftime("%d.%m.%Y %H:%M", now),
    }


def open_app(name):
    name = (name or "").strip()
    if not name:
        return {"ok": False, "hata": "Uygulama adi bos"}
    low = name.lower()

    # Web sitesi/adres ise tarayicida ac
    if any(h in low for h in URL_HINTS) or low.startswith("http"):
        url = name if low.startswith("http") else "https://" + name
        try:
            webbrowser.open(url)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "hata": str(exc)}
        return {"ok": True, "acilan": url, "url": url}

    target = APP_ALIASES.get(low, APP_ALIASES.get(low.strip(), name))
    try:
        if IS_WINDOWS:
            if target.endswith(":"):
                os.startfile(target)  # ms-settings: / outlookcal: gibi URI'ler
            else:
                subprocess.Popen(["cmd", "/c", "start", "", target], shell=False)
        else:
            subprocess.Popen([target])
        return {"ok": True, "acilan": target}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "hata": str(exc)}


def open_url(url):
    url = (url or "").strip()
    if not url:
        return {"ok": False, "hata": "Adres bos"}
    if not url.startswith("http"):
        url = "https://" + url
    try:
        webbrowser.open(url)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "hata": str(exc)}
    return {"ok": True, "acilan": url, "url": url}


# ---------------- Web yardimcilari (YouTube / Hava durumu) ----------------
def youtube_url(query=None):
    """YouTube arama adresi (sorgu bossa ana sayfa)."""
    q = (query or "").strip()
    if not q:
        return "https://www.youtube.com"
    return "https://www.youtube.com/results?search_query=" + urllib.parse.quote(q)


WMO_TR = {
    0: "acik", 1: "az bulutlu", 2: "parcali bulutlu", 3: "kapali",
    45: "sisli", 48: "kirci firtinasi (sis)",
    51: "hafif cisenti", 53: "cisenti", 55: "yogun cisenti",
    56: "dondurucu cisenti", 57: "yogun dondurucu cisenti",
    61: "hafif yagmurlu", 63: "yagmurlu", 65: "siddetli yagmurlu",
    66: "dondurucu yagmur", 67: "siddetli dondurucu yagmur",
    71: "hafif kar", 73: "kar", 75: "yogun kar", 77: "kar taneleri",
    80: "hafif saganak", 81: "saganak", 82: "siddetli saganak",
    85: "kar saganagi", 86: "yogun kar saganagi",
    95: "gok gurultulu firtina", 96: "dolulu firtina", 99: "siddetli dolulu firtina",
}


def _http_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def weather(city="Istanbul"):
    """Open-Meteo (anahtarsiz) ile anlik + 3 gunluk hava durumu."""
    city = (city or "Istanbul").strip()
    try:
        geo = _http_json("https://geocoding-api.open-meteo.com/v1/search?"
                         + urllib.parse.urlencode({"name": city, "count": 1, "language": "tr", "format": "json"}))
        results = geo.get("results") or []
        if not results:
            return {"ok": False, "hata": "Sehir bulunamadi: " + city}
        loc = results[0]
        fc = _http_json("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
            "latitude": loc["latitude"], "longitude": loc["longitude"],
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min",
            "timezone": "auto", "forecast_days": 3,
        }))
        cur = fc.get("current", {})
        daily = fc.get("daily", {})
        days = []
        for i, d in enumerate(daily.get("time", [])):
            days.append({
                "tarih": d,
                "min": daily.get("temperature_2m_min", [None])[i],
                "max": daily.get("temperature_2m_max", [None])[i],
                "durum": WMO_TR.get(daily.get("weather_code", [None])[i], "?"),
            })
        return {
            "ok": True,
            "sehir": loc.get("name"),
            "ulke": loc.get("country"),
            "sicaklik": cur.get("temperature_2m"),
            "hissedilen": cur.get("apparent_temperature"),
            "nem": cur.get("relative_humidity_2m"),
            "ruzgar": cur.get("wind_speed_10m"),
            "durum": WMO_TR.get(cur.get("weather_code"), "?"),
            "gunler": days,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "hata": str(exc)}


def weather_reply(city="Istanbul"):
    """Hava durumunu insan dilinde Turkce metne cevirir."""
    w = weather(city)
    if not w.get("ok"):
        return None, w
    lines = ["%s hava durumu efendim: %s, sicaklik %s°C (hissedilen %s°C), nem %%%.0f, ruzgar %s km/s." % (
        w.get("sehir") or city, w.get("durum"), w.get("sicaklik"), w.get("hissedilen"),
        w.get("nem") or 0, w.get("ruzgar"),
    )]
    for d in w.get("gunler", [])[:3]:
        lines.append("- %s: %s, %s-%s°C" % (d["tarih"], d["durum"], d["min"], d["max"]))
    return "\n".join(lines), w


CURRENCY_ALIASES = {
    "dolar": "USD", "usd": "USD", "amerikan dolari": "USD", "abd dolari": "USD",
    "euro": "EUR", "eur": "EUR", "avro": "EUR",
    "sterlin": "GBP", "gbp": "GBP", "pound": "GBP", "ingiliz sterlini": "GBP",
    "frank": "CHF", "chf": "CHF", "isvicre frangi": "CHF",
    "yen": "JPY", "jpy": "JPY", "japon yeni": "JPY",
    "yuan": "CNY", "cny": "CNY", "ruble": "RUB", "rub": "RUB",
    "altin": "XAU", "gram altin": "XAU",
}


def exchange_rate(base="USD", to="TRY"):
    """Frankfurter (anahtarsiz, ECB) ile doviz kuru. Basarisizsa er-api denenir."""
    base = (base or "USD").upper()
    to = (to or "TRY").upper()
    try:
        data = _http_json("https://api.frankfurter.app/latest?from=%s&to=%s" % (base, to))
        rate = (data.get("rates") or {}).get(to)
        if rate:
            return {"ok": True, "base": base, "hedef": to, "kur": rate,
                    "tarih": data.get("date"), "kaynak": "frankfurter"}
    except Exception:  # noqa: BLE001
        pass
    try:
        data = _http_json("https://open.er-api.com/v6/latest/%s" % base)
        rate = (data.get("rates") or {}).get(to)
        if rate:
            return {"ok": True, "base": base, "hedef": to, "kur": rate,
                    "tarih": (data.get("time_last_update_utc") or "")[:16], "kaynak": "er-api"}
        return {"ok": False, "hata": "Kur bulunamadi: %s->%s" % (base, to)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "hata": str(exc)}


def exchange_reply(base="USD", to="TRY"):
    """Doviz kurunu insan dilinde Turkce metne cevirir."""
    r = exchange_rate(base, to)
    if not r.get("ok"):
        return None, r
    symbol = {"USD": "$", "EUR": "€", "GBP": "£"}.get(r["base"], "")
    hedef = "TL" if r["hedef"] == "TRY" else r["hedef"]
    text = "1 %s%s = %.4f %s efendim (%s)." % (
        symbol, r["base"], r["kur"], hedef, r.get("tarih") or "")
    return text, r


# ---------------- Ses kontrolu (Windows: sanal tuslar) ----------------
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF


def _press_vk(vk, times=1):
    if not IS_WINDOWS:
        return False
    import ctypes
    for _ in range(max(1, times)):
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
        time.sleep(0.02)
    return True


def volume(action, level=None):
    action = (action or "").lower()
    if action in ("yukselt", "up", "arttir", "increase"):
        _press_vk(VK_VOLUME_UP, 5)
        return {"ok": True, "yapilan": "ses +5"}
    if action in ("dusur", "down", "azalt", "decrease"):
        _press_vk(VK_VOLUME_DOWN, 5)
        return {"ok": True, "yapilan": "ses -5"}
    if action in ("sessiz", "kapat", "mute", "sus"):
        _press_vk(VK_VOLUME_MUTE, 1)
        return {"ok": True, "yapilan": "sessize alma degistirildi"}
    if action in ("ayarla", "set") and level is not None:
        try:
            level = max(0, min(100, int(level)))
        except Exception:  # noqa: BLE001
            return {"ok": False, "hata": "Gecersiz seviye"}
        _press_vk(VK_VOLUME_UP, 55)          # önce sonuna kadar aç
        _press_vk(VK_VOLUME_DOWN, max(0, 100 - level))
        return {"ok": True, "yapilan": "ses ~%d" % level}
    return {"ok": False, "hata": "Bilinmeyen ses komutu"}


def lock_screen():
    if not IS_WINDOWS:
        return {"ok": False, "hata": "Yalnizca Windows"}
    try:
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        return {"ok": True, "yapilan": "ekran kilitlendi"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "hata": str(exc)}


def take_screenshot():
    try:
        from PIL import ImageGrab
    except Exception:  # noqa: BLE001
        return {"ok": False, "hata": "Pillow kurulu degil"}
    _ensure_work_dir()
    path = os.path.join(WORK_DIR, "ekran_%s.png" % time.strftime("%Y%m%d_%H%M%S"))
    try:
        img = ImageGrab.grab()
        img.save(path)
        return {"ok": True, "dosya": path}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "hata": str(exc)}


def system_info():
    info = {
        "isletim_sistemi": platform.system() + " " + platform.release(),
        "surum": platform.version(),
        "makine": platform.machine(),
        "python": platform.python_version(),
        "cpu_cikarim": platform.processor() or "bilinmiyor",
        "cpu_cekirdek": os.cpu_count(),
    }
    try:
        total, used, free = shutil.disk_usage(os.path.expanduser("~"))
        gb = 1024 ** 3
        info["disk_toplam_gb"] = round(total / gb, 1)
        info["disk_bos_gb"] = round(free / gb, 1)
    except Exception:  # noqa: BLE001
        pass
    ram = _ram_gb()
    if ram:
        info["ram_toplam_gb"] = ram[0]
        info["ram_bos_gb"] = ram[1]
    return info


def _ram_gb():
    if not IS_WINDOWS:
        return None
    try:
        import ctypes
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        gb = 1024 ** 3
        return (round(stat.ullTotalPhys / gb, 1), round(stat.ullAvailPhys / gb, 1))
    except Exception:  # noqa: BLE001
        return None


def _safe_name(name):
    name = os.path.basename((name or "").strip())
    return "".join(ch for ch in name if ch.isalnum() or ch in "._- ()")[:80]


def write_file(filename, content):
    _ensure_work_dir()
    safe = _safe_name(filename)
    if not safe:
        return {"ok": False, "hata": "Gecersiz dosya adi"}
    path = os.path.join(WORK_DIR, safe)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content or "")
        return {"ok": True, "dosya": path}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "hata": str(exc)}


def read_file(filename):
    safe = _safe_name(filename)
    path = os.path.join(WORK_DIR, safe)
    if not os.path.isfile(path):
        return {"ok": False, "hata": "Dosya bulunamadi: " + safe}
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return {"ok": True, "icerik": f.read()[:4000]}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "hata": str(exc)}


def list_files():
    _ensure_work_dir()
    try:
        files = sorted(os.listdir(WORK_DIR))
        return {"ok": True, "dosyalar": files[:100], "klasor": WORK_DIR}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "hata": str(exc)}
