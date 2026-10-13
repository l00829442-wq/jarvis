#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jarvis - yerel sunucu ve yapay zeka koprusu (proxy).

Hicbir ek paket gerekmez; sadece Python'un standart kutuphanesi kullanilir.
- public/ klasorundeki web arayuzunu sunar (telefon ve PC icin).
- /api/chat adresine gelen istekleri ucretsiz bir AI saglayicisina iletir.
- API anahtari sadece bu sunucuda durur, tarayiciya sizmaz.

Calistirmak icin:  python server.py
"""

import json
import os
import sys
import mimetypes
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import jarvis_agent
from jarvis_memory import MemoryStore

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
MEMORY_PATH = os.path.join(BASE_DIR, "jarvis_memory.db")
PORT = int(os.environ.get("JARVIS_PORT") or os.environ.get("PORT") or "8000")

_MEMORY = None


def get_memory():
    global _MEMORY
    if _MEMORY is None:
        _MEMORY = MemoryStore(MEMORY_PATH)
    return _MEMORY

APP_VERSION = "1.1.0"

DEFAULT_CONFIG = {
    "provider": "gemini",          # gemini | groq | deepseek | openai | openrouter | offline
    "api_key": "",
    "model": "gemini-3-flash-preview",
    "keys": {},                    # her saglayici icin ayri anahtar (opsiyonel)
    "models": {},                  # her saglayici icin ayri model (opsiyonel)
    "assistant_name": "Jarvis",
    "system_prompt": "",           # bos ise jarvis_agent varsayilani kullanilir
    # Otomatik guncelleme (exe): uzak JSON {version, exe_url, notes}
    "update_url": "",
    "autoupdate": True,
    # Akilli ev kisayollari: sesli komut -> webhook/URL
    # Ornek: "isigi ac" dediginizde IFTTT webhook'unuzu tetikler.
    "shortcuts": {},
}

# Saglayicilar. kind: "gemini" (ozel), "openai" (OpenAI uyumlu), "offline".
PROVIDERS = {
    "gemini": {
        "label": "Google Gemini",
        "kind": "gemini",
        "url": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        "default_model": "gemini-3-flash-preview",
        "key_url": "https://aistudio.google.com/app/apikey",
        "free": True,
        "vision": True,
    },
    "groq": {
        "label": "Groq (Llama)",
        "kind": "openai",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "default_model": "llama-3.3-70b-versatile",
        "key_url": "https://console.groq.com/keys",
        "free": True,
        "vision": False,
    },
    "deepseek": {
        "label": "DeepSeek",
        "kind": "openai",
        "url": "https://api.deepseek.com/chat/completions",
        "default_model": "deepseek-chat",
        "key_url": "https://platform.deepseek.com/api_keys",
        "free": False,
        "vision": False,
    },
    "openai": {
        "label": "OpenAI (ChatGPT)",
        "kind": "openai",
        "url": "https://api.openai.com/v1/chat/completions",
        "default_model": "gpt-4o-mini",
        "key_url": "https://platform.openai.com/api-keys",
        "free": False,
        "vision": True,
    },
    "openrouter": {
        "label": "OpenRouter",
        "kind": "openai",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "default_model": "meta-llama/llama-3.3-70b-instruct:free",
        "key_url": "https://openrouter.ai/keys",
        "free": True,
        "vision": False,
    },
    "offline": {
        "label": "Cevrimdisi (anahtarsiz)",
        "kind": "offline",
        "default_model": "",
        "free": True,
    },
}


def resolve_key(cfg, provider):
    keys = cfg.get("keys") or {}
    if keys.get(provider):
        return keys[provider]
    if cfg.get("provider") == provider and cfg.get("api_key"):
        return cfg["api_key"]
    return ""


def resolve_model(cfg, provider):
    models = cfg.get("models") or {}
    if models.get(provider):
        return models[provider]
    if cfg.get("provider") == provider and cfg.get("model"):
        return cfg["model"]
    return (PROVIDERS.get(provider) or {}).get("default_model", "")


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception as exc:  # noqa: BLE001
            print("[!] config.json okunamadi:", exc)
    # Ortam degiskenleri (bulut yayinlari icin - anahtari repoya koymayin)
    if os.environ.get("JARVIS_API_KEY"):
        cfg["api_key"] = os.environ["JARVIS_API_KEY"]
    if os.environ.get("JARVIS_PROVIDER"):
        cfg["provider"] = os.environ["JARVIS_PROVIDER"]
    if os.environ.get("JARVIS_MODEL"):
        cfg["model"] = os.environ["JARVIS_MODEL"]
    return cfg


def save_config(updates):
    """config.json'u verilen alanlarla gunceller (digerlerini korur)."""
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as exc:  # noqa: BLE001
            print("[!] config.json okunamadi (yazma):", exc)
            cfg = {}
    if not isinstance(cfg, dict):
        cfg = {}
    cfg.update(updates or {})
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as exc:  # noqa: BLE001
        print("[!] config.json yazilamadi:", exc)
    return cfg


def offline_brain(messages):
    """Anahtar yoksa calisan basit kural tabanli yedek beyin."""
    user = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user = (m.get("content") or "").lower()
            break
    if any(w in user for w in ("merhaba", "selam", "hello", "hey")):
        return "Merhaba efendim, sizi dinliyorum."
    if "saat" in user:
        import datetime
        return "Saat su anda " + datetime.datetime.now().strftime("%H:%M") + "."
    if "tarih" in user or "gun" in user:
        import datetime
        return "Bugun " + datetime.datetime.now().strftime("%d.%m.%Y") + "."
    if "adin" in user or "kimsin" in user:
        return "Ben Jarvis, sizin yapay zeka asistaninizim."
    return (
        "Su anda cevrimdisi modda calisiyorum. Gercek yapay zeka icin "
        "config.json dosyasina ucretsiz bir API anahtari ekleyin "
        "(README'ye bakin efendim)."
    )


FAST_MODEL = "gemini-3-flash-preview"
GEMINI_FALLBACK_MODELS = [
    "gemini-3-flash-preview",
    "gemini-flash-latest",
    "gemini-3.8-flash",
    "gemini-flash-lite-latest",
]


def _gemini_models(preferred):
    ordered = []
    for m in [preferred] + GEMINI_FALLBACK_MODELS:
        if m and m not in ordered:
            ordered.append(m)
    return ordered


def _gemini_generate(key, model, body, timeout=60):
    url = PROVIDERS["gemini"]["url"].format(model=model) + "?key=" + key

    def _do(payload):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    fast = dict(body)
    gen = dict(fast.get("generationConfig") or {})
    gen.setdefault("thinkingConfig", {"thinkingBudget": 0})
    fast["generationConfig"] = gen
    try:
        return _do(fast)
    except urllib.error.HTTPError as exc:
        if exc.code == 400:
            return _do(body)
        raise


def parse_image(dataurl):
    """'data:image/png;base64,XXXX' -> (mime, base64) veya None."""
    if not dataurl or not isinstance(dataurl, str):
        return None
    if "," not in dataurl:
        return None
    head, b64 = dataurl.split(",", 1)
    mime = "image/png"
    if head.startswith("data:") and ";" in head:
        mime = head[5:].split(";", 1)[0] or mime
    if not b64:
        return None
    return mime, b64


def call_gemini(cfg, messages):
    key = cfg.get("api_key") or ""
    if not key:
        raise RuntimeError("API anahtari yok")
    preferred = cfg.get("model") or PROVIDERS["gemini"]["default_model"]
    system = ""
    contents = []
    for m in messages:
        role = m.get("role")
        text = m.get("content") or ""
        img = parse_image(m.get("image"))
        if role == "system":
            system = text
            continue
        parts = [{"text": text}] if text else []
        if img:
            parts.append({"inline_data": {"mime_type": img[0], "data": img[1]}})
        if not parts:
            parts = [{"text": ""}]
        if role == "assistant":
            contents.append({"role": "model", "parts": parts})
        else:
            contents.append({"role": "user", "parts": parts})

    body = {"contents": contents}
    if system:
        body["system_instruction"] = {"parts": [{"text": system}]}

    last = None
    for model in _gemini_models(preferred):
        try:
            payload = _gemini_generate(key, model, body)
            return payload["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code in (404, 429, 500, 503):
                print("[i] %s mesgul/erisilemez (%s), sonraki model deneniyor" % (model, exc.code))
                continue
            raise
    raise last


def call_gemini_transcribe(cfg, audio_b64, mime):
    """Ses kaydini Gemini ile Turkce metne cevirir (tarayici konusma servisi
    desteklenmeyen ortamlar icin - orn. masaustu WebView2 uygulamasi)."""
    key = cfg.get("api_key") or ""
    if not key:
        raise RuntimeError("API anahtari yok")
    preferred = cfg.get("transcribe_model") or "gemini-3-flash-preview"
    body = {
        "contents": [{
            "parts": [
                {"text": "Bu ses kaydindaki konusmayi Turkce olarak metne cevir. "
                         "Sadece konusulan metni yaz; aciklama, etiket veya tirnak ekleme."},
                {"inline_data": {"mime_type": mime, "data": audio_b64}},
            ]
        }]
    }
    last = None
    for model in _gemini_models(preferred):
        try:
            payload = _gemini_generate(key, model, body, timeout=90)
            parts = payload["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts).strip()
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code in (404, 429, 500, 503):
                print("[i] %s mesgul/erisilemez (%s), sonraki model deneniyor" % (model, exc.code))
                continue
            raise
    raise last


def provider_cfg(cfg, provider):
    """Belirli saglayici icin api_key ve model'i cozup cfg kopyasi dondurur."""
    out = dict(cfg)
    out["provider"] = provider
    out["api_key"] = resolve_key(cfg, provider)
    out["model"] = resolve_model(cfg, provider)
    return out


def call_openai_compatible(cfg, messages, spec):
    """OpenAI uyumlu saglayicida (arac destekli) sohbet."""
    key = cfg.get("api_key") or ""
    if not key:
        raise RuntimeError("API anahtari yok")
    model = cfg.get("model") or spec.get("default_model")
    return jarvis_agent.ask_openai(cfg, messages, get_memory(), spec["url"], model, key)


def ask_ai(cfg, messages):
    """(cevap, kullanilan_araclar) dondurur. Aktif saglayiciya gore yonlendirir;
    her durumda cokmek yerine guvenli bir yedege duser."""
    provider = (cfg.get("provider") or "offline").lower()
    spec = PROVIDERS.get(provider) or PROVIDERS["offline"]
    kind = spec.get("kind")
    pcfg = provider_cfg(cfg, provider)

    if kind == "gemini" and pcfg.get("api_key"):
        try:
            return jarvis_agent.ask(pcfg, messages, get_memory())
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 404):
                print("[i] Ajan modu yok (%s), duz sohbet" % exc.code)
                return call_gemini(pcfg, messages), []
            raise
        except Exception as exc:  # noqa: BLE001
            print("[!] Ajan hatasi, duz sohbet:", exc)
            return call_gemini(pcfg, messages), []

    if kind == "openai" and pcfg.get("api_key"):
        return call_openai_compatible(pcfg, messages, spec), []

    return offline_brain(messages), []


class JarvisHandler(BaseHTTPRequestHandler):
    server_version = "Jarvis/1.0"

    def log_message(self, fmt, *args):  # daha temiz konsol
        sys.stdout.write("  - " + (fmt % args) + "\n")

    def _send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.end_headers()

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/api/health"):
            cfg = load_config()
            provider = (cfg.get("provider") or "offline").lower()
            self._send_json({
                "status": "ok",
                "version": APP_VERSION,
                "provider": provider,
                "has_key": bool(resolve_key(cfg, provider)),
                "model": resolve_model(cfg, provider),
                "tools": True,
                "memories": get_memory().count(),
            })
            return
        if self.path.startswith("/api/version"):
            self._send_json({
                "version": APP_VERSION,
                "name": "Jarvis",
                "update_url": load_config().get("update_url") or "",
            })
            return
        if self.path.startswith("/api/providers"):
            cfg = load_config()
            current = (cfg.get("provider") or "offline").lower()
            items = []
            for pid, spec in PROVIDERS.items():
                if pid == "offline":
                    continue
                items.append({
                    "id": pid,
                    "label": spec.get("label"),
                    "kind": spec.get("kind"),
                    "default_model": spec.get("default_model"),
                    "key_url": spec.get("key_url"),
                    "free": bool(spec.get("free")),
                    "vision": bool(spec.get("vision")),
                    "has_key": bool(resolve_key(cfg, pid)),
                    "model": resolve_model(cfg, pid),
                })
            self._send_json({
                "providers": items,
                "current": current,
                "current_model": resolve_model(cfg, current),
            })
            return
        if self.path.startswith("/api/shortcuts"):
            cfg = load_config()
            self._send_json({"shortcuts": cfg.get("shortcuts") or {}})
            return
        if self.path.startswith("/api/memory"):
            mem = get_memory()
            self._send_json({
                "memories": [
                    {"id": r[0], "content": r[1], "tags": r[2], "created": r[3]}
                    for r in mem.all()
                ]
            })
            return
        self._serve_static()

    def do_POST(self):  # noqa: N802
        if self.path.startswith("/api/chat"):
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                req = json.loads(raw.decode("utf-8"))
            except Exception:  # noqa: BLE001
                self._send_json({"error": "Gecersiz istek"}, 400)
                return
            messages = req.get("messages") or []
            if not messages:
                self._send_json({"error": "Mesaj yok"}, 400)
                return
            # En son kullanici mesajina gorsel eklenmisse ona bagla
            img = req.get("image")
            if img:
                for m in reversed(messages):
                    if m.get("role") == "user":
                        m["image"] = img
                        break
            cfg = load_config()
            try:
                reply, tools_used = ask_ai(cfg, messages)
                self._send_json({
                    "reply": reply,
                    "provider": cfg.get("provider"),
                    "tools": tools_used,
                })
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "ignore")
                print("[!] AI hatasi:", exc.code, detail[:300])
                self._send_json({
                    "error": "AI saglayici hatasi (%s). Anahtar/kota kontrol edin." % exc.code,
                    "detail": detail[:500],
                }, 502)
            except Exception as exc:  # noqa: BLE001
                print("[!] Hata:", exc)
                self._send_json({"error": str(exc)}, 500)
            return
        if self.path.startswith("/api/transcribe"):
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                req = json.loads(raw.decode("utf-8"))
            except Exception:  # noqa: BLE001
                self._send_json({"error": "Gecersiz istek"}, 400)
                return
            audio = req.get("audio")
            if not audio:
                self._send_json({"error": "Ses verisi yok"}, 400)
                return
            cfg = provider_cfg(load_config(), "gemini")
            try:
                text = call_gemini_transcribe(cfg, audio, req.get("mime") or "audio/wav")
                self._send_json({"text": text})
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "ignore")
                print("[!] Ceviri hatasi:", exc.code, detail[:300])
                self._send_json({"error": "Ses ceviri hatasi (%s)" % exc.code}, 502)
            except Exception as exc:  # noqa: BLE001
                print("[!] Ceviri hatasi:", exc)
                self._send_json({"error": str(exc)}, 500)
            return
        if self.path.startswith("/api/config"):
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                req = json.loads(raw.decode("utf-8"))
            except Exception:  # noqa: BLE001
                self._send_json({"error": "Gecersiz istek"}, 400)
                return
            cur = load_config()
            upd = {}
            for k in ("provider", "model", "assistant_name", "system_prompt",
                      "update_url", "autoupdate"):
                if k in req:
                    upd[k] = req[k]
            prov = (req.get("provider") or cur.get("provider") or "").lower()
            if "api_key" in req and prov:
                keys = dict(cur.get("keys") or {})
                keys[prov] = req["api_key"]
                upd["keys"] = keys
                if prov == (cur.get("provider") or "").lower():
                    upd["api_key"] = req["api_key"]
            if isinstance(req.get("keys"), dict):
                keys = dict(cur.get("keys") or {})
                keys.update(req["keys"])
                upd["keys"] = keys
            if isinstance(req.get("models"), dict):
                models = dict(cur.get("models") or {})
                models.update(req["models"])
                upd["models"] = models
            save_config(upd)
            newp = (req.get("provider") or cur.get("provider") or "offline").lower()
            self._send_json({
                "ok": True,
                "provider": newp,
                "model": resolve_model(load_config(), newp),
                "has_key": bool(resolve_key(load_config(), newp)),
            })
            return
        if self.path.startswith("/api/memory"):
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                req = json.loads(raw.decode("utf-8"))
            except Exception:  # noqa: BLE001
                self._send_json({"error": "Gecersiz istek"}, 400)
                return
            mem = get_memory()
            action = (req.get("action") or "").lower()
            if action == "add":
                mid = mem.add(req.get("text", ""), req.get("tags", ""))
                self._send_json({"ok": True, "id": mid})
            elif action == "forget":
                try:
                    mem.forget(int(req.get("id")))
                    self._send_json({"ok": True})
                except Exception:  # noqa: BLE001
                    self._send_json({"error": "Gecersiz id"}, 400)
            elif action == "clear":
                mem.clear()
                self._send_json({"ok": True})
            else:
                self._send_json({"error": "Bilinmeyen islem"}, 400)
            return
        self._send_json({"error": "Bulunamadi"}, 404)

    def _serve_static(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            path = "/index.html"
        rel = path.lstrip("/").replace("/", os.sep)
        full = os.path.normpath(os.path.join(PUBLIC_DIR, rel))
        if not full.startswith(PUBLIC_DIR) or not os.path.isfile(full):
            self.send_error(404, "Bulunamadi")
            return
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        with open(full, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)


def get_lan_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:  # noqa: BLE001
        return "127.0.0.1"


def main():
    cfg = load_config()
    print("=" * 56)
    print("  JARVIS sunucusu baslatiliyor")
    print("=" * 56)
    print("  AI saglayici : %s" % cfg.get("provider"))
    print("  Model        : %s" % cfg.get("model"))
    print("  API anahtari : %s" % ("VAR" if cfg.get("api_key") else "YOK (cevrimdisi mod)"))
    print("-" * 56)
    print("  PC'de ac    : http://localhost:%d" % PORT)
    print("  Telefonda   : http://%s:%d  (ayni Wi-Fi'de)" % (get_lan_ip(), PORT))
    print("=" * 56)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), JarvisHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[+] Kapatiliyor...")
        server.shutdown()


if __name__ == "__main__":
    main()
