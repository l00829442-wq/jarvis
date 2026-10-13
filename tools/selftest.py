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

    # 4b) yeni anahtarsiz araclar (hava, doviz, youtube, web arama)
    try:
        d, tools, dt = chat("Ankara hava durumu nasıl?")
        check("hava durumu", "get_weather" in tools and "hava durumu" in (d.get("reply") or "").lower(),
              "%.1fs" % dt)
    except Exception as e:
        check("hava durumu", False, str(e))

    try:
        d, tools, dt = chat("youtube'dan sezen aksu çal")
        acts = [a.get("url") for a in (d.get("actions") or [])]
        check("youtube/actions", "play_youtube" in tools and any("youtube.com" in (u or "") for u in acts),
              "actions=%s" % acts)
    except Exception as e:
        check("youtube/actions", False, str(e))

    try:
        d, tools, dt = chat("dolar kaç tl?")
        check("doviz kuru", "get_exchange_rate" in tools and "tl" in (d.get("reply") or "").lower(),
              "%.1fs" % dt)
    except Exception as e:
        check("doviz kuru", False, str(e))

    try:
        sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
        import jarvis_tools
        import jarvis_agent

        def _retry(fn, tries=2):
            last = None
            for _ in range(tries):
                try:
                    r = fn()
                    if isinstance(r, dict) and r.get("ok"):
                        return r
                    last = r
                except Exception as exc:  # noqa: BLE001
                    last = exc
                time.sleep(1)
            return last if isinstance(last, dict) else {"ok": False, "hata": str(last)}

        check("arac: hava (yerel)", _retry(lambda: jarvis_tools.weather("Ankara")).get("ok"))
        check("arac: doviz (yerel)", _retry(lambda: jarvis_tools.exchange_rate("USD")).get("ok"))
        ws = _retry(lambda: jarvis_agent._web_search({}, "python programlama dili"))
        check("arac: web_search (yerel)", ws.get("ok") and len(ws.get("sonuc") or "") > 20,
              "kaynak=%s" % ws.get("kaynak"))
        dr = _retry(lambda: jarvis_agent._deep_research({}, "Ankara hakkinda bilgi"))
        check("arac: deep_research (yerel)", dr.get("ok") and len(dr.get("sonuc") or "") > 200,
              "kaynak=%s len=%d" % (dr.get("kaynak"), len(dr.get("sonuc") or "")))
    except Exception as e:
        check("arac: yerel testler", False, str(e))

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

    # 6b) rehber / ara / mesaj
    try:
        d, tools, dt = chat("Rehberime Test Kişi ekle 0555 111 22 33")
        check("rehber kaydet", "save_contact" in tools, "tools=%s" % tools)

        d, tools, dt = chat("Test Kişi'yi ara")
        acts = [(a.get("type"), a.get("url")) for a in (d.get("actions") or [])]
        check("rehber ara", "call_contact" in tools and any(t == "call" and (u or "").startswith("tel:") for t, u in acts),
              "actions=%s" % acts)

        d, tools, dt = chat("Test Kişi'ye mesaj at merhaba jarvis")
        acts = [(a.get("type"), a.get("url")) for a in (d.get("actions") or [])]
        check("rehber mesaj", "send_sms" in tools and any(t == "sms" and (u or "").startswith("sms:") for t, u in acts),
              "actions=%s" % acts)
    except Exception as e:
        check("rehber", False, str(e))

    # 6c) uygulama acma (deep-link/web) eylemi
    try:
        d, tools, dt = chat("instagram aç")
        acts = [(a.get("type"), a.get("scheme")) for a in (d.get("actions") or [])]
        check("uygulama acma", "open_app" in tools, "actions=%s" % acts)
    except Exception as e:
        check("uygulama acma", False, str(e))

    # 6d) saat dilimi (istemci tz_offset kabul edilmeli)
    try:
        s, b, dt = req("/api/chat", {"messages": [{"role": "user", "content": "Saat kaç?"}], "tz_offset": 0})
        d = json.loads(b)
        check("tz_offset kabul", bool(d.get("reply")) and "get_datetime" in [t.get("arac") for t in (d.get("tools") or [])],
              "reply=%s" % (d.get("reply") or "")[:40])
    except Exception as e:
        check("tz_offset kabul", False, str(e))

    # 6e) contacts API
    try:
        s, b, dt = req("/api/contacts")
        before = len(json.loads(b).get("contacts", []))
        uniq = "Api Kisi %d" % int(time.time())
        s, b, dt = req("/api/contacts", {"action": "add", "name": uniq, "phone": "0555 999 88 77"})
        s, b, dt = req("/api/contacts")
        d = json.loads(b)
        names = [c.get("name") for c in d.get("contacts", [])]
        check("contacts API ekle/listele", len(names) == before + 1 and uniq in names,
              "%d -> %d" % (before, len(names)))
    except Exception as e:
        check("contacts API", False, str(e))

    # 6f) kendini test et
    try:
        s, b, dt = req("/api/selfcheck", timeout=120)
        d = json.loads(b)
        check("selfcheck", "checks" in d and len(d["checks"]) >= 6 and dt < 60,
              "ok=%s %d kontrol %.1fs" % (d.get("ok"), len(d.get("checks", [])), dt))
    except Exception as e:
        check("selfcheck", False, str(e))

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
