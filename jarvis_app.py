#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jarvis Masaustu Uygulamasi
==========================
Tarayici OLMADAN, kendi penceresinde acilan gercek bir uygulama.
- Arka planda yerel sunucuyu (server.py) baslatir.
- Arayuzu native bir pencerede (Edge WebView2) gosterir.
- config.json'u .exe'nin yanindan okur.

Calistirma:  python jarvis_app.py
Derleme:     pyinstaller --noconsole --onefile --name Jarvis --icon public/icons/jarvis.ico --add-data "public;public" --add-data "config.example.json;." jarvis_app.py
"""

import os
import sys
import socket
import shutil
import threading
import time
from http.server import ThreadingHTTPServer

APP_NAME = "Jarvis"


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def bundle_dir():
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def ensure_config():
    """config.json yoksa ornegi kopyala; yolunu dondur."""
    cfg = os.path.join(app_dir(), "config.json")
    if not os.path.exists(cfg):
        example = os.path.join(bundle_dir(), "config.example.json")
        try:
            if os.path.exists(example):
                shutil.copyfile(example, cfg)
            else:
                with open(cfg, "w", encoding="utf-8") as f:
                    f.write('{\n  "provider": "gemini",\n  "api_key": "",\n'
                            '  "model": "gemini-flash-latest"\n}\n')
        except Exception:
            pass
    return cfg


def free_port(start=8000):
    for port in range(start, start + 60):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start


def start_server(port):
    import server
    server.PUBLIC_DIR = os.path.join(bundle_dir(), "public")
    server.CONFIG_PATH = ensure_config()
    server.MEMORY_PATH = os.path.join(app_dir(), "jarvis_memory.db")
    httpd = ThreadingHTTPServer(("127.0.0.1", port), server.JarvisHandler)
    httpd.serve_forever()


def patch_webview2_mic():
    """WebView2'de mikrofon erisimini otomatik onayla. Boylece tarayici
    konusma servisi olmasa bile kayit+Gemini yontemiyle sesli komut calisir."""
    try:
        from webview.platforms import edgechromium as ec
    except Exception as exc:  # noqa: BLE001
        print("[!] WebView2 yamasi atlandi:", exc)
        return
    base = ec.CoreWebView2CreationProperties
    extra = " --use-fake-ui-for-media-stream --autoplay-policy=no-user-gesture-required"

    class _Props(base):
        def __setattr__(self, name, value):
            if (name == "AdditionalBrowserArguments" and isinstance(value, str)
                    and "--use-fake-ui-for-media-stream" not in value):
                value = value + extra
            super().__setattr__(name, value)

    ec.CoreWebView2CreationProperties = _Props
    print("[i] WebView2 mikrofon izni otomatik onay icin hazir")


def _setup_logging():
    """Derlenmis (penceresiz) exe'de hatalari gorebilmek icin dosyaya logla."""
    if not getattr(sys, "frozen", False):
        return
    try:
        log = open(os.path.join(app_dir(), "jarvis.log"), "a", encoding="utf-8", buffering=1)
        sys.stdout = log
        sys.stderr = log
    except Exception:
        pass
    try:
        import faulthandler
        faulthandler.enable()
    except Exception:
        pass
    try:
        import threading as _th

        def _hook(args):
            import traceback
            traceback.print_exception(args.exc_type, args.exc_value, args.exc_traceback)
        _th.excepthook = _hook
    except Exception:
        pass


def _maybe_self_update():
    """Arka planda guncelleme denetler; yeni surum varsa exe'yi degistirip cikar."""
    try:
        import server
        import jarvis_updater
    except Exception:
        return
    try:
        cfg = server.load_config()
        cfg["_version"] = getattr(server, "APP_VERSION", "")
        if jarvis_updater.check_and_update(cfg, sys.executable):
            print("[i] Guncelleme uygulandi, yeniden baslatiliyor...")
            time.sleep(1.0)
            os._exit(0)
    except Exception as exc:  # noqa: BLE001
        print("[!] Guncelleme kontrolu atlandi:", exc)


def main():
    _setup_logging()
    # WebView2 mikrofon izin istemini otomatik onayla (sesle dinleme icin sart)
    os.environ.setdefault(
        "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
        "--use-fake-ui-for-media-stream --autoplay-policy=no-user-gesture-required",
    )
    patch_webview2_mic()

    port = free_port(8000)
    url = "http://127.0.0.1:%d" % port

    threading.Thread(target=start_server, args=(port,), daemon=True).start()
    threading.Thread(target=_maybe_self_update, daemon=True).start()

    # Sunucunun ayaga kalkmasini bekle
    for _ in range(50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                break
        time.sleep(0.1)

    try:
        import webview
    except Exception:
        webview = None

    if webview is not None:
        try:
            webview.create_window(
                APP_NAME, url,
                width=470, height=900,
                min_size=(360, 620),
                background_color="#04121a",
            )
            webview.start()
            return
        except Exception as exc:  # WebView2 yoksa yedek
            print("Native pencere acilamadi:", exc)

    # Yedek: sistemin varsayilan tarayicisinda app penceresi
    print("Tarayici penceresinde aciliyor:", url)
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:
        os.startfile(url)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
