# -*- coding: utf-8 -*-
"""
Jarvis - otomatik guncelleme (exe).

Mantik:
1. config.json icindeki 'update_url' adresinden bir JSON cekilir:
       { "version": "1.2.0", "exe_url": "https://.../Jarvis.exe", "notes": "..." }
2. Surum yeniyse yeni exe indirilir.
3. Windows calisan exe'yi uzerine yazamadigi icin kucuk bir .bat yardimcisi
   ile: mevcut kapanana kadar bekler, degistirir ve yeniden baslatir.

'update_url' bos ise hicbir sey yapilmaz (yerel/yayinsiz kullanim guvenli).
"""

import json
import os
import subprocess
import sys
import tempfile
import urllib.request


def _parse_version(v):
    parts = []
    for p in str(v or "").strip().split("."):
        num = ""
        for ch in p:
            if ch.isdigit():
                num += ch
            else:
                break
        parts.append(int(num) if num else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def is_newer(remote, local):
    return _parse_version(remote) > _parse_version(local)


def fetch_manifest(update_url, timeout=15):
    req = urllib.request.Request(update_url, headers={"User-Agent": "Jarvis-Updater"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download(url, timeout=120):
    tmp = os.path.join(tempfile.gettempdir(), "jarvis_update_new.exe")
    req = urllib.request.Request(url, headers={"User-Agent": "Jarvis-Updater"})
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(tmp, "wb") as f:
        f.write(resp.read())
    return tmp


def apply_update(new_exe, target_exe):
    """Bir .bat yardimcisi ile exe'yi degistirip yeniden baslatir."""
    bat = os.path.join(tempfile.gettempdir(), "jarvis_apply_update.bat")
    lines = [
        "@echo off",
        "timeout /t 2 /nobreak >nul",
        ':wait',
        'tasklist /fi "PID eq %1" 2>nul | find "%1" >nul',
        "if not errorlevel 1 ( timeout /t 1 /nobreak >nul & goto wait )",
        'copy /y "%s" "%s" >nul' % (new_exe, target_exe),
        'del "%s" >nul' % new_exe,
        'start "" "%s"' % target_exe,
        'del "%%~f0" >nul',
    ]
    with open(bat, "w", encoding="utf-8") as f:
        f.write("\r\n".join(lines) + "\r\n")
    subprocess.Popen([bat, str(os.getpid())], shell=True)


def check_and_update(cfg, exe_path=None):
    """Yeni surum varsa indirir ve guncellemeyi uygular. True donerse uygulama
    kapanmalidir (guncelleme icin)."""
    if not cfg.get("autoupdate", True):
        return False
    if not getattr(sys, "frozen", False):
        return False  # sadece derlenmis exe kendini guncelleyebilir
    url = cfg.get("update_url")
    if not url:
        return False
    if exe_path is None:
        exe_path = sys.executable
    try:
        man = fetch_manifest(url)
        remote = man.get("version")
        local = cfg.get("_version") or ""
        if not remote or not is_newer(remote, local):
            return False
        exe_url = man.get("exe_url")
        if not exe_url:
            return False
        print("[i] Yeni surum bulundu: %s -> %s" % (local, remote))
        new_exe = download(exe_url)
        apply_update(new_exe, exe_path)
        return True
    except Exception as exc:  # noqa: BLE001
        print("[!] Guncelleme denetimi basarisiz:", exc)
        return False
