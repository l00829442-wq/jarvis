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
}

URL_HINTS = (".com", ".net", ".org", ".tr", ".dev", ".io", ".gov", ".edu",
             "http://", "https://", "www.")


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
            return {"ok": True, "acilan": url}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "hata": str(exc)}

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
        return {"ok": True, "acilan": url}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "hata": str(exc)}


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
