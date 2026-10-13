# -*- coding: utf-8 -*-
"""
Jarvis - uctan uca otomatik test.

Calistirmadan once sunucuyu baslatin:
    set PORT=8011 && python server.py
Sonra:
    python tools/selftest.py
"""

import base64
import io
import json
import sys
import time
import urllib.request
import urllib.error

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8011"
PASS, FAIL = 0, 0


def req(path, data=None, method=None, timeout=120):
    url = BASE + path
    if data is not None:
        raw = json.dumps(data).encode("utf-8")
        r = urllib.request.Request(url, data=raw, method=method or "POST",
                                   headers={"Content-Type": "application/json"})
    else:
        r = urllib.request.Request(url, method=method or "GET")
    t0 = time.time()
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    return resp.status, body, time.time() - t0


def check(name, ok, info=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  [OK]   %s %s" % (name, info))
    else:
        FAIL += 1
        print("  [HATA] %s %s" % (name, info))


def chat(text, image=None, timeout=120):
    payload = {"messages": [{"role": "user", "content": text}]}
    if image:
        payload["image"] = image
    status, body, dt = req("/api/chat", payload, timeout=timeout)
    d = json.loads(body)
    tools = [t.get("arac") for t in (d.get("tools") or [])]
    return d, tools, dt


def make_test_image():
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return None
    img = Image.new("RGB", (420, 160), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([10, 10, 410, 150], outline="black", width=3)
    d.text((30, 60), "MERHABA JARVIS 42", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def main():
    print("Jarvis selftest -> %s" % BASE)
    print("-" * 60)

    # 1) health
    try:
        s, b, dt = req("/api/health")
        d = json.loads(b)
        check("health", d.get("status") == "ok", json.dumps(d, ensure_ascii=False))
        check("health.memories alani", "memories" in d)
    except Exception as e:
        check("health", False, str(e))

    # 2) statik arayuz
    try:
        s, b, dt = req("/")
        check("index.html servis", s == 200 and "<html" in b.lower(), "%d bayt" % len(b))
    except Exception as e:
        check("index.html servis", False, str(e))

    # 3) basit sohbet
    try:
        d, tools, dt = chat("Merhaba, kendini tek cumleyle tanit.")
        check("sohbet (duz)", bool(d.get("reply")) and dt < 30, "%.1fs" % dt)
    except Exception as e:
        check("sohbet (duz)", False, str(e))

    # 4) hizli komutlar (deterministik)
    for name, q, want in [
        ("saat", "Saat kaç?", "get_datetime"),
        ("gun", "Bugün hangi gündeyiz?", "get_datetime"),
        ("sistem", "Sistem bilgilerimi özetle.", "get_system_info"),
    ]:
        try:
            d, tools, dt = chat(q)
            check("fast-path %s" % name, want in tools and dt < 10,
                  "tools=%s %.1fs" % (tools, dt))
        except Exception as e:
            check("fast-path %s" % name, False, str(e))

    # 5) hafiza
    try:
        d, tools, dt = chat("Hatırla: favori rengim mavi")
        check("hafiza kaydet", "remember" in tools, "tools=%s" % tools)
        d, tools, dt = chat("Ne hatırlıyorsun?")
        check("hafiza listele", "recall" in tools and "mavi" in (d.get("reply") or "").lower())
    except Exception as e:
        check("hafiza", False, str(e))

    # 6) memory API
    try:
        s, b, dt = req("/api/memory")
        before = len(json.loads(b).get("memories", []))
        s, b, dt = req("/api/memory", {"action": "add", "text": "selftest kaydi"})
        s, b, dt = req("/api/memory")
        after = len(json.loads(b).get("memories", []))
        check("memory API ekle/listele", after == before + 1, "%d -> %d" % (before, after))
    except Exception as e:
        check("memory API", False, str(e))

    # 7) ses -> yazi (test WAV)
    wav = None
    for p in [r"C:\Users\Bthn\AppData\Local\Temp\opencode\test.wav"]:
        try:
            with open(p, "rb") as f:
                wav = base64.b64encode(f.read()).decode()
            break
        except Exception:
            pass
    if wav:
        try:
            s, b, dt = req("/api/transcribe", {"audio": wav, "mime": "audio/wav"}, timeout=120)
            d = json.loads(b)
            check("ses->yazi", bool(d.get("text")), "%.1fs: %s" % (dt, d.get("text")))
        except Exception as e:
            check("ses->yazi", False, str(e))
    else:
        print("  [atla] ses->yazi (test.wav yok)")

    # 8) gorsel (vision)
    img = make_test_image()
    if img:
        try:
            d, tools, dt = chat("Bu gorselde ne yaziyor? Sadece yaziyi söyle.", image=img, timeout=120)
            txt = (d.get("reply") or "").upper()
            check("gorsel/vision", ("MERHABA" in txt or "42" in txt), "%.1fs: %s" % (dt, d.get("reply")))
        except Exception as e:
            check("gorsel/vision", False, str(e))
    else:
        print("  [atla] gorsel (Pillow yok)")

    print("-" * 60)
    print("SONUC: %d basarili, %d hatali" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
