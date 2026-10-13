# -*- coding: utf-8 -*-
"""
Jarvis - ajan dongusu (Gemini function-calling / ReAct).

Internetteki gelismis Jarvis projelerindeki gibi, model gerekirse araclari
(uygulama ac, ses, ekran goruntusu, hafiza, web arama...) kendisi secer ve
cagirir; sonucu kullanarak dogal dilde yanit uretir.

Model araclari desteklemezse veya hata verirse cagiran taraf (server.py) duz
sohbete duser; boylece sistem her kosulda calisir.
"""

import json
import re
import urllib.request
import urllib.error

import jarvis_tools as tools

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
FAST_MODEL = "gemini-3.5-flash-lite"
FALLBACK_MODELS = [
    "gemini-3.5-flash-lite",   # 500 istek/gun (ucretsiz)
    "gemini-3.1-flash-lite",   # 500 istek/gun
    "gemini-3.6-flash",        # daha yetenekli (20/gun) - lite tukenirse
    "gemini-flash-lite-latest",
    "gemini-3.8-flash",
]

MAX_STEPS = 6

FUNCTION_DECLARATIONS = [
    {
        "name": "open_app",
        "description": "Windows'ta bir uygulamayi veya web sitesini acar.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "name": {"type": "STRING", "description": "Uygulama adi (orn. 'not defteri', 'chrome') veya web sitesi (orn. 'youtube.com')"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "open_url",
        "description": "Verilen web adresini varsayilan tarayicida acar.",
        "parameters": {"type": "OBJECT", "properties": {"url": {"type": "STRING"}}, "required": ["url"]},
    },
    {
        "name": "set_volume",
        "description": "Sistem sesini ayarlar veya degistirir.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "'yukselt', 'dusur', 'sessiz' veya 'ayarla'"},
                "level": {"type": "INTEGER", "description": "action 'ayarla' ise 0-100 arasi ses seviyesi"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "take_screenshot",
        "description": "Bilgisayar ekraninin goruntusunu alip kaydeder.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "lock_screen",
        "description": "Bilgisayar ekranini kilitler.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "get_system_info",
        "description": "Bilgisayarin isletim sistemi, RAM, disk ve CPU bilgilerini dondurur.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "get_datetime",
        "description": "Su anki tarih ve saati dondurur.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "remember",
        "description": "Kullanici hakkinda kalici bir bilgiyi uzun sureli hafizaya kaydeder.",
        "parameters": {"type": "OBJECT", "properties": {"text": {"type": "STRING"}}, "required": ["text"]},
    },
    {
        "name": "recall",
        "description": "Uzun sureli hafizadan ilgili bilgileri arar.",
        "parameters": {"type": "OBJECT", "properties": {"query": {"type": "STRING"}}, "required": ["query"]},
    },
    {
        "name": "write_file",
        "description": "Documents/Jarvis klasorune bir metin dosyasi yazar.",
        "parameters": {
            "type": "OBJECT",
            "properties": {"filename": {"type": "STRING"}, "content": {"type": "STRING"}},
            "required": ["filename", "content"],
        },
    },
    {
        "name": "read_file",
        "description": "Documents/Jarvis klasorunden bir dosyayi okur.",
        "parameters": {"type": "OBJECT", "properties": {"filename": {"type": "STRING"}}, "required": ["filename"]},
    },
    {
        "name": "list_files",
        "description": "Documents/Jarvis klasorundeki dosyalari listeler.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "web_search",
        "description": "Guncel bilgi, haber, hava durumu, mac sonucu, fiyat gibi internete bakilmasi gereken sorular icin web'de arar.",
        "parameters": {"type": "OBJECT", "properties": {"query": {"type": "STRING"}}, "required": ["query"]},
    },
    {
        "name": "get_weather",
        "description": "Bir sehir icin guncel hava durumunu ve 3 gunluk tahmini verir.",
        "parameters": {"type": "OBJECT", "properties": {"city": {"type": "STRING", "description": "Sehir adi, orn. 'Istanbul'"}}, "required": ["city"]},
    },
    {
        "name": "play_youtube",
        "description": "YouTube'da bir sarki/muzik/video acar. Kullanici sarki, muzik veya video dinlemek/acmak istediginde kullan.",
        "parameters": {"type": "OBJECT", "properties": {"query": {"type": "STRING", "description": "Aranacak sarki, sanatci veya video adi. Bos birakilirsa YouTube ana sayfasi acilir."}}, "required": ["query"]},
    },
    {
        "name": "get_exchange_rate",
        "description": "Doviz kuru verir (dolar, euro, sterlin vb. karsiligi TL). Kullanici kur/fiyat sordugunda kullan.",
        "parameters": {"type": "OBJECT", "properties": {
            "base": {"type": "STRING", "description": "Kaynak doviz kodu, orn. 'USD', 'EUR'"},
            "to": {"type": "STRING", "description": "Hedef doviz kodu, varsayilan 'TRY'"}},
            "required": ["base"]},
    },
]


def _generate(cfg, body):
    key = cfg.get("api_key") or ""
    if not key:
        raise RuntimeError("API anahtari yok")
    preferred = cfg.get("model") or FAST_MODEL
    models = []
    for m in [preferred] + FALLBACK_MODELS:
        if m and m not in models:
            models.append(m)
    last = None
    for model in models:
        url = GEMINI_URL.format(model=model) + "?key=" + key

        def _do(payload):
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read().decode("utf-8"))

        fast = dict(body)
        gen = dict(fast.get("generationConfig") or {})
        gen.setdefault("thinkingConfig", {"thinkingBudget": 0})
        fast["generationConfig"] = gen
        try:
            try:
                return _do(fast)
            except urllib.error.HTTPError as exc400:
                if exc400.code == 400:
                    return _do(body)
                raise
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code in (404, 429, 500, 503):
                print("[i] %s mesgul (%s), sonraki model" % (model, exc.code))
                continue
            raise
    raise last


_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _ddg_search(query, limit=5, timeout=20):
    """DuckDuckGo (lite, anahtarsiz) ile web arama sonuclari."""
    import html as _html
    import urllib.parse as _up
    url = "https://lite.duckduckgo.com/lite/?q=" + _up.quote(query or "")
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        page = resp.read().decode("utf-8", "ignore")
    items = []
    for m in re.finditer(r"<a[^>]*class=['\"]result-link['\"][^>]*>(.*?)</a>", page, re.S):
        text = _html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
        href = ""
        hm = re.search(r"href=['\"]([^'\"]+)['\"]", m.group(0))
        if hm:
            href = hm.group(1)
        if "uddg=" in href:
            href = _up.unquote(href.split("uddg=", 1)[1].split("&", 1)[0])
        if href.startswith("//"):
            href = "https:" + href
        if text:
            items.append({"title": text, "url": href, "snippet": ""})
    snips = [_html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
             for m in re.finditer(r"<td[^>]*class=['\"]result-snippet['\"][^>]*>(.*?)</td>", page, re.S)]
    for i, s in enumerate(snips):
        if i < len(items):
            items[i]["snippet"] = s
    return items[:limit]


def _wiki_search(query, limit=3, timeout=20):
    """Wikipedia (anahtarsiz) ozet arama."""
    import urllib.parse as _up
    url = ("https://tr.wikipedia.org/w/api.php?action=query&list=search&format=json&srprop=snippet&srlimit=%d&srsearch=" % limit
           + _up.quote(query or ""))
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    out = []
    for s in (data.get("query", {}).get("search") or []):
        snip = re.sub(r"<[^>]+>", "", s.get("snippet", ""))
        out.append({"title": s.get("title", ""), "snippet": snip.strip()})
    return out


def _web_search(cfg, query):
    """Guncel bilgi icin web'de arar: anahtarsiz DDG + Wikipedia; son care model
    'grounding'. Sonucu araci cagiran modele metin olarak dondurur."""
    query = (query or "").strip()
    if not query:
        return {"ok": False, "hata": "Sorgu bos"}
    # 1) Anahtarsiz arama (kota harcamaz)
    try:
        items = _ddg_search(query)
        if items:
            lines = ["Web sonuclari (%s):" % query]
            for it in items:
                line = "- " + it["title"]
                if it.get("snippet"):
                    line += ": " + it["snippet"]
                if it.get("url"):
                    line += " [%s]" % it["url"]
                lines.append(line)
            return {"ok": True, "kaynak": "duckduckgo", "sonuc": "\n".join(lines)}
    except Exception:  # noqa: BLE001
        pass
    # 2) Wikipedia
    try:
        wikis = _wiki_search(query)
        if wikis:
            lines = ["Wikipedia sonuclari (%s):" % query]
            for w in wikis:
                lines.append("- %s: %s" % (w["title"], w["snippet"]))
            return {"ok": True, "kaynak": "wikipedia", "sonuc": "\n".join(lines)}
    except Exception:  # noqa: BLE001
        pass
    # 3) Model grounding (varsa)
    return _web_search_grounding(cfg, query)


def _web_search_grounding(cfg, query):
    body = {
        "contents": [{"role": "user", "parts": [{"text":
            "Su konuda internette guncel bilgi ara ve Turkce, kisa ve net bir "
            "cevap ver: " + (query or "")}]}],
        "tools": [{"google_search": {}}],
    }
    try:
        payload = _generate(cfg, body)
        parts = payload["candidates"][0]["content"].get("parts", [])
        return {"ok": True, "sonuc": "".join(p.get("text", "") for p in parts).strip()}
    except urllib.error.HTTPError as exc:
        if exc.code in (400,):
            try:
                body["tools"] = [{"google_search_retrieval": {}}]
                payload = _generate(cfg, body)
                parts = payload["candidates"][0]["content"].get("parts", [])
                return {"ok": True, "sonuc": "".join(p.get("text", "") for p in parts).strip()}
            except Exception as exc2:  # noqa: BLE001
                return {"ok": False, "hata": str(exc2)}
        return {"ok": False, "hata": "web arama hatasi (%s)" % exc.code}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "hata": str(exc)}


def execute_tool(name, args, memory, cfg):
    args = args or {}
    try:
        if name == "open_app":
            return tools.open_app(args.get("name"))
        if name == "open_url":
            return tools.open_url(args.get("url"))
        if name == "set_volume":
            return tools.volume(args.get("action"), args.get("level"))
        if name == "take_screenshot":
            return tools.take_screenshot()
        if name == "lock_screen":
            return tools.lock_screen()
        if name == "get_system_info":
            return tools.system_info()
        if name == "get_datetime":
            return tools.get_datetime()
        if name == "write_file":
            return tools.write_file(args.get("filename"), args.get("content"))
        if name == "read_file":
            return tools.read_file(args.get("filename"))
        if name == "list_files":
            return tools.list_files()
        if name == "web_search":
            return _web_search(cfg, args.get("query"))
        if name == "get_weather":
            reply, w = tools.weather_reply(args.get("city") or "Istanbul")
            if w.get("ok"):
                w["ozet"] = reply
            return w
        if name == "play_youtube":
            url = tools.youtube_url(args.get("query"))
            return {"ok": True, "acilan": url, "url": url}
        if name == "get_exchange_rate":
            reply, r = tools.exchange_reply(args.get("base") or "USD", args.get("to") or "TRY")
            if r.get("ok"):
                r["ozet"] = reply
            return r
        if name == "remember":
            text = (args.get("text") or "").strip()
            if memory and text:
                mid = memory.add(text, tags="auto")
                return {"ok": True, "kaydedildi": text, "id": mid}
            return {"ok": False, "hata": "Bos bilgi"}
        if name == "recall":
            hits = memory.search(args.get("query")) if memory else []
            return {"ok": True, "sonuclar": [h[1] for h in hits]}
        return {"ok": False, "hata": "Bilinmeyen arac: " + str(name)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "hata": str(exc)}


def _build_contents(messages):
    contents = []
    for m in messages:
        role = m.get("role")
        text = m.get("content") or ""
        if role == "system":
            continue
        parts = [{"text": text}] if text else []
        img = m.get("image")
        if img and isinstance(img, str) and "," in img:
            head, b64 = img.split(",", 1)
            mime = "image/png"
            if head.startswith("data:") and ";" in head:
                mime = head[5:].split(";", 1)[0] or mime
            if b64:
                parts.append({"inline_data": {"mime_type": mime, "data": b64}})
        if not parts:
            parts = [{"text": ""}]
        if role == "assistant":
            contents.append({"role": "model", "parts": parts})
        else:
            contents.append({"role": "user", "parts": parts})
    return contents


def _last_user(messages):
    for m in reversed(messages):
        if m.get("role") == "user":
            return m.get("content") or ""
    return ""


def _now():
    return tools.get_datetime()


def fast_path(text, memory):
    """Yaygin, net komutlari LLM'e gitmeden aninda calistirir.
    (cevap, araclar) dondurur; eslesme yoksa None."""
    t = _tr_lower((text or "").strip())
    if not t:
        return None
    used = []

    def done(tool, result, reply):
        used.append({"arac": tool, "sonuc": result})
        return reply, used

    # --- Zaman / tarih ---
    if ("saat" in t and ("kaç" in t or t == "saat")) or t in ("saat kaç", "saat"):
        d = _now()
        return done("get_datetime", d, "Saat su anda %s efendim." % d["saat"])
    if any(k in t for k in ("hangi gündeyiz", "hangi gun", "bugün gün", "tarih ne", "bugünün tarihi")):
        d = _now()
        return done("get_datetime", d, "Bugun %s %s efendim." % (d["tarih"], d["gun"]))

    # --- Sistem bilgisi ---
    if (any(k in t for k in ("sistem bilgi", "sistem durum", "donanım", "donanim",
                             "bellek", "işlemci", "islemci"))
            or __import__("re").search(r"\b(ram|disk|cpu)\b", t)):
        return done("get_system_info", {"ok": True}, system_info_reply())

    # --- Ekran görüntüsü ---
    if any(k in t for k in ("ekran görünt", "ekran gorunt", "screenshot", "ekran resmi", "ekran fotoğraf", "ekran fotograf")):
        res = tools.take_screenshot()
        if res.get("ok"):
            return done("take_screenshot", res, "Ekran goruntusu alindi efendim: %s" % res["dosya"])
        return done("take_screenshot", res, "Ekran goruntusu alinamadi: %s" % res.get("hata"))

    # --- Kilit ---
    if "kilit" in t and any(k in t for k in ("ekran", "bilgisayar", "pencere", "pc", "sistemi")):
        res = tools.lock_screen()
        return done("lock_screen", res, "Ekran kilitleniyor efendim." if res.get("ok")
                    else "Kilitlenemedi: %s" % res.get("hata"))

    # --- Ses ---
    if "ses" in t or "sessiz" in t:
        if any(k in t for k in ("aç", "ac", "arttır", "arttir", "yükselt", "yukselt", "yüksel")):
            return done("set_volume", tools.volume("yukselt"), "Sesi yukseltiyorum efendim.")
        if any(k in t for k in ("kıs", "kis", "azalt", "düşür", "dusur", "düş")):
            return done("set_volume", tools.volume("dusur"), "Sesi kisiyorum efendim.")
        if any(k in t for k in ("sessiz", "mute", "sus", "kapa")):
            return done("set_volume", tools.volume("sessiz"), "Sesi kapattim/açtım efendim.")
        import re as _re
        m = _re.search(r"(?:ses\w*\s*)?(%\s*)?(\d{1,3})", t)
        if m and any(k in t for k in ("ayarla", "yap", "seviye", "%")):
            lvl = int(m.group(2))
            return done("set_volume", tools.volume("ayarla", lvl), "Ses seviyesini ~%%%d yaptim efendim." % lvl)

    # --- Hava durumu (anahtarsiz, LLM'e gitmeden) ---
    if any(k in t for k in ("hava durum", "hava nasil", "hava nasıl", "hava kac",
                            "hava kaç", "hava sicaklik", "hava sıcaklık", "hava tahmin",
                            "yagmur var", "yağmur var", "kar var mı", "kar var mi")):
        city = _city_from_text(text)
        reply, w = tools.weather_reply(city)
        if reply:
            return done("get_weather", w, reply)
        return done("get_weather", w, "Hava durumu alinamadi efendim: %s" % w.get("hata"))

    # --- Doviz kuru (anahtarsiz, LLM'e gitmeden) ---
    _cur_kw = ("dolar", "usd", "euro", "eur", "avro", "sterlin", "gbp", "frank",
               "chf", "yen", "jpy", "yuan", "cny", "ruble", "doviz", "döviz")
    if (any(k in t for k in _cur_kw)
            and any(k in t for k in ("kur", "ne kadar", "kaç", "kac", "kaç tl", "kac tl", "fiyat", "tl"))):
        cur = _currency_from_text(text)
        reply, r = tools.exchange_reply(cur, "TRY")
        if reply:
            return done("get_exchange_rate", r, reply)
        return done("get_exchange_rate", r, "Kur alinamadi efendim: %s" % r.get("hata"))


    # --- YouTube / muzik acma ---
    if "youtube" in t or re.search(r"(^|[\s,.;:!?])çal([\s,.;:!?]|$)", t):
        q = _youtube_query(text)
        url = tools.youtube_url(q)
        reply = ("YouTube'da '%s' ariyorum efendim." % q) if q else "YouTube aciliyor efendim."
        return done("play_youtube", {"ok": True, "url": url}, reply)

    # --- Uygulama / site açma ---
    if any(k in t for k in ("aç", "ac ", "açar mısın", "acar misin", "başlat", "baslat", "açsana")):
        alias = _match_app(t)
        if alias:
            if not tools.IS_WINDOWS:
                web = tools.app_web_url(alias) or (alias if alias.startswith("http") else None)
                if web:
                    return done("open_app", {"ok": True, "url": web}, "%s web'de aciliyor efendim." % alias)
            res = tools.open_app(alias)
            if res.get("ok"):
                return done("open_app", res, "%s aciliyor efendim." % alias)
            return done("open_app", res, "Acilamadi: %s" % res.get("hata"))

    # --- Hafıza: kaydet ---
    low = text.lower()
    for kw in ("hatırla", "hatirla", "unutma", "kaydet", "aklında tut", "aklinda tut"):
        idx = low.find(kw)
        if idx != -1:
            info = text[idx + len(kw):].strip(" :.-,")
            if info:
                mid = memory.add(info, tags="kullanici") if memory else None
                return done("remember", {"ok": bool(mid)}, "Tamam efendim, not ettim: %s" % info)

    # --- Hafıza: hatırla ---
    if any(k in t for k in ("ne hatırlıyor", "ne hatirliyor", "hafızanda ne", "hafizanda ne",
                            "neler biliyorsun", "benimle ilgili ne", "hatırladıkların")):
        if memory and memory.count():
            items = [r[1] for r in memory.all(15)]
            return done("recall", {"ok": True}, "Hatirladiklarim efendim:\n- " + "\n- ".join(items))
        return done("recall", {"ok": True}, "Henuz benimle ilgili kayitli bir sey yok efendim. 'Hatırla: ...' diyerek ekleyebilirsiniz.")

    return None


def _match_app(t):
    for alias in sorted(tools.APP_ALIASES, key=len, reverse=True):
        if alias in t:
            return alias
    return None


_FILLER = {"da", "de", "dan", "den", "için", "icin", "bana", "bir", "acaba", "lütfen",
           "lutfen", "nasil", "nasıl", "kaç", "kac", "derece", "bugün", "bugun", "yarın",
           "yarin", "şu", "su", "bu", "var", "mı", "mi", "mu", "mü", "the", "and"}


def _tr_lower(s):
    """Turkce'ye uygun kucuk harf: İ->i, I->ı (birlesik nokta sorununu onler)."""
    return (s or "").replace("İ", "i").replace("I", "ı").lower()

_YT_TRIGGERS = ["youtube", "you tube", "müzik", "muzik", "şarkı", "sarki", "dinle",
                "video", "parça", "parca", "playlist", "listesi", "açsana", "çalsana",
                "açar mısın", "acar misin", "aç", "ac", "çal", "cal", "başlat", "baslat",
                "üzerinden", "uzerinden", "tane"]


def _clean_query(text):
    low = " " + _tr_lower(text) + " "
    for w in _YT_TRIGGERS + list(_FILLER):
        low = re.sub(r"(^|[\s,.;:!?'\"])" + re.escape(w) + r"([\s,.;:!?'\"]|$)", " ", low)
    low = re.sub(r"[^\wçğıöşüÇĞİÖŞÜ ]+", " ", low)
    return re.sub(r"\s+", " ", low).strip(" -.,")


def _youtube_query(text):
    return _clean_query(text)


def _city_from_text(text):
    low = _tr_lower(text)
    for phrase in ("hava durumu", "hava durumunu", "hava nasıl", "hava nasil",
                   "hava kaç derece", "hava kac derece", "hava sıcaklığı", "hava sicakligi",
                   "hava kaç", "hava kac", "hava tahmini", "hava tahmin", "hava"):
        low = low.replace(phrase, " ")
    low = re.sub(r"[^\wçğıöşüÇĞİÖŞÜ ]+", " ", low)
    words = [w for w in low.split() if w not in _FILLER]
    return " ".join(words) or "Istanbul"


def _currency_from_text(text):
    low = _tr_lower(text)
    for alias, code in tools.CURRENCY_ALIASES.items():
        if alias in low:
            return code
    return "USD"


def system_info_reply():
    info = tools.system_info()
    lines = ["Sistem bilgileri efendim:"]
    lines.append("- Isletim sistemi: %s" % info.get("isletim_sistemi", "?"))
    if info.get("ram_toplam_gb"):
        lines.append("- RAM: %s GB (bos: %s GB)" % (info.get("ram_toplam_gb"), info.get("ram_bos_gb")))
    if info.get("disk_toplam_gb"):
        lines.append("- Disk: %s GB (bos: %s GB)" % (info.get("disk_toplam_gb"), info.get("disk_bos_gb")))
    lines.append("- Islemci cekirdegi: %s" % info.get("cpu_cekirdek", "?"))
    return "\n".join(lines)


DEFAULT_SYSTEM_PROMPT = (
    "Sen Jarvis'sin: Iron Man'deki Jarvis'ten ilham alan, Turkce konusan, son "
    "derece yetenekli ve zarif bir yapay zeka asistanisin. Kullaniciya saygiyla "
    "'efendim' diye hitap edersin. Davranisin:\n"
    "- Net, dogru ve oz cevap ver; gereksiz uzatma. Gerektiginde madde madde acikla.\n"
    "- Kullanici komut verdiginde once niyeti anla; gerekiyorsa dogru araci cagir.\n"
    "- Emin olmadigin bilgide uydurma; guncel bilgi gerekiyorsa web arasini kullan.\n"
    "- Kod, matematik, analiz ve yaratici yazimda ust duzey ol; ornek ver.\n"
    "- Kisa sorulara kisa, karmasik sorulara yeterince ayrintili yanit ver.\n"
    "- Konusma dilini kullaniciya uyarla (Turkce sorarsa Turkce)."
)


def _system_prompt(cfg, messages, memory=None):
    system = cfg.get("system_prompt") or DEFAULT_SYSTEM_PROMPT
    mem_ctx = memory.context_for(_last_user(messages)) if memory else ""
    if mem_ctx:
        system += "\n\n" + mem_ctx
    system += (
        "\n\nElinde araclar var (uygulama/site acma, ses, ekran goruntusu, sistem "
        "bilgisi, hafiza, dosya, web arama). Bir gorevi yerine getirmek icin "
        "gerekiyorsa aciklama yapmadan ilgili araci cagir; sonuc gelince kisa bir "
        "Turkce cevap ver. Gereksiz arac cagirma."
    )
    if not tools.IS_WINDOWS:
        system += (
            "\n\nONEMLI: Su an WEB/tarayici ortamindasin (kullanicinin telefonu veya "
            "tabletinde). Bilgisayara ozel araclar (open_app ile program acma, ses "
            "kontrolu, ekran goruntusu, ekran kilitleme, dosya islemleri) BU ORTAMDA "
            "CALISMAZ; bunlari denemek yerine kullaniciya bunun yalnizca bilgisayar "
            "uygulamasinda oldugunu kibarca soyle. Muzik/video icin play_youtube "
            "(YouTube arama acar), guncel bilgi icin get_weather veya web_search, "
            "doviz kuru icin get_exchange_rate araclarini kullan."
        )
    return system


def _should_fast_path(messages):
    return len(messages) == 1 or (messages and messages[-1].get("role") == "user")


def _openai_tools():
    def conv(schema):
        t = dict(schema)
        if isinstance(t.get("type"), str):
            t["type"] = t["type"].lower()
        if "properties" in t:
            t["properties"] = {k: conv(v) for k, v in t["properties"].items()}
        if "items" in t:
            t["items"] = conv(t["items"])
        return t

    out = []
    for fn in FUNCTION_DECLARATIONS:
        out.append({"type": "function", "function": {
            "name": fn["name"],
            "description": fn["description"],
            "parameters": conv(fn["parameters"]),
        }})
    return out


def _openai_messages(system, messages):
    out = [{"role": "system", "content": system}]
    for m in messages:
        role = m.get("role")
        if role == "system":
            continue
        text = m.get("content") or ""
        img = m.get("image")
        if img and isinstance(img, str) and img.startswith("data:"):
            out.append({"role": "user", "content": [
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {"url": img}},
            ]})
        else:
            out.append({"role": role if role in ("user", "assistant") else "user",
                        "content": text})
    return out


def ask_openai(cfg, messages, memory, url, model, key, timeout=90):
    """OpenAI uyumlu saglayicilar (OpenAI, DeepSeek, Groq, OpenRouter...) icin
    arac cagirabilen sohbet dongusu. Araclar desteklenmezse duz sohbete duser."""
    if not key:
        raise RuntimeError("API anahtari yok")
    system = _system_prompt(cfg, messages, memory)

    if _should_fast_path(messages):
        fp = fast_path(_last_user(messages), memory)
        if fp:
            return fp

    payload = {
        "model": model,
        "messages": _openai_messages(system, messages),
        "tools": _openai_tools(),
        "tool_choice": "auto",
    }
    notes = []

    def post(p):
        data = json.dumps(p).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", "Bearer " + key)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    tools_supported = True
    for _ in range(MAX_STEPS):
        try:
            resp = post(payload)
        except urllib.error.HTTPError as exc:
            if tools_supported and exc.code in (400, 422):
                print("[i] Arac cagirma desteklenmiyor (%s), duz sohbet" % exc.code)
                tools_supported = False
                payload.pop("tools", None)
                payload.pop("tool_choice", None)
                resp = post(payload)
            else:
                raise
        msg = resp["choices"][0]["message"]
        tcs = msg.get("tool_calls")
        if tcs:
            payload["messages"].append(msg)
            for tc in tcs:
                name = tc.get("function", {}).get("name")
                try:
                    args = json.loads(tc.get("function", {}).get("arguments") or "{}")
                except Exception:  # noqa: BLE001
                    args = {}
                result = execute_tool(name, args, memory, cfg)
                notes.append({"arac": name, "sonuc": result})
                payload["messages"].append({
                    "role": "tool",
                    "tool_call_id": tc.get("id"),
                    "content": json.dumps(result, ensure_ascii=False),
                })
            continue
        return (msg.get("content") or "").strip() or "Tamam efendim.", notes

    return "Uzgunum efendim, bu istegi tamamlayamadim.", notes


def ask(cfg, messages, memory=None):
    """Ajan dongusu: model araclari cagirabilir, sonra dogal cevap uretir."""
    system = _system_prompt(cfg, messages, memory)

    contents = _build_contents(messages)
    tool_result_notes = []

    # Hizli yol: net sistem/hafiza komutlarini LLM'e gitmeden calistir (stabilite)
    if _should_fast_path(messages):
        fp = fast_path(_last_user(messages), memory)
        if fp:
            return fp

    for _ in range(MAX_STEPS):
        body = {
            "contents": contents,
            "system_instruction": {"parts": [{"text": system}]},
            "tools": [{"functionDeclarations": FUNCTION_DECLARATIONS}],
        }
        payload = _generate(cfg, body)
        cand = payload.get("candidates", [{}])[0]
        parts = cand.get("content", {}).get("parts", [])
        fcalls = [p["functionCall"] for p in parts if "functionCall" in p]
        texts = [p.get("text", "") for p in parts if p.get("text")]

        if fcalls:
            contents.append({"role": "model", "parts": parts})
            fparts = []
            for fc in fcalls:
                name = fc.get("name")
                result = execute_tool(name, fc.get("args"), memory, cfg)
                tool_result_notes.append({"arac": name, "sonuc": result})
                fparts.append({
                    "functionResponse": {"name": name, "response": {"sonuc": result}},
                })
            contents.append({"role": "user", "parts": fparts})
            continue

        answer = "".join(texts).strip()
        if not answer:
            answer = "Tamam efendim."
        return answer, tool_result_notes

    return "Uzgunum efendim, bu istegi tamamlayamadim.", tool_result_notes
