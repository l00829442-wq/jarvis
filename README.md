# Jarvis - Yapay Zeka Asistanı (Windows Uygulaması + Android APK)

Sesle konuşan, soruları yanıtlayan ve hatırlatan ücretsiz bir Jarvis asistanı.
Üç şekilde çalışır: **Windows masaüstü uygulaması (.exe)**, **Android uygulaması
(APK)** ve istenirse tarayıcı/PWA.

## Hangi sürümü kullanacaksın?
| Sürüm | Nasıl açılır | Not |
|-------|--------------|-----|
| 💻 **Windows uygulaması** | Masaüstündeki **Jarvis** kısayolu, ya da `dist\Jarvis\Jarvis.exe` | Tarayıcı yok, kendi penceresi |
| 📱 **Android uygulaması** | Telefona kurulu APK | Kurulum: [APK.md](APK.md) |
| 🌐 Tarayıcı/PWA | `baslat.cmd` → tarayıcı | Yedek yöntem |

> ⚠️ **Windows "Smart App Control" notu:** İmzasız `.exe` dosyalarını engelleyen bu
> Windows güvenlik özelliği açıksa `Jarvis.exe` çalışmayabilir. Sorun olmaması için
> masaüstündeki **Jarvis** kısayolu, imzalı Python ile çalışan native pencereyi açar
> (`pythonw jarvis_app.py`) — bu her zaman çalışır. `.exe`'yi başka bilgisayarlarda
> paylaşmak için kullan. Kendi bilgisayarında `.exe`'yi de çalıştırmak istersen
> **Ayarlar → Gizlilik ve güvenlik → Windows Güvenliği → Uygulama ve tarayıcı
> denetimi → Smart App Control**'ü kapatabilirsin (kapatınca Windows sıfırlanmadan
> yeniden açılamaz).

## Özellikler
- 🎤 **Sesle dinleme** ve 🔊 **sesli cevaplama**; 👂 **"Hey Jarvis"** ile eller serbest
- 🧠 **Kalıcı hafıza**: "Hatırla: ..." ile bilgi kaydeder, sonra hatırlar (hafıza penceresi)
- 🛠️ **Araç kullanımı (ajan)**: uygulama/site açma, sistem bilgisi, ekran görüntüsü,
  kilit, ses denetimi, dosya yaz/oku/listele, web arama (ReAct/function-calling)
- 🖼️ **Görsel anlama (vision)**: görsel yükle / sürükle-bırak / Ctrl+V → Jarvis inceler
- 🔎 **Güncel bilgi (kota dostu)**: **anahtarsız** web arama (DuckDuckGo + Wikipedia),
  🌤️ **hava durumu** (Open-Meteo), 💱 **döviz kuru** (frankfurter) — ekstra ücret yok
- 🎵 **Müzik/video**: "YouTube'dan ... çal" dediğinde sonuç bağlantısı sayfada açılır
  (bulut/telefonda bile çalışır, çünkü bağlantı tarayıcıda açılır)
- 🌐 **Çok sağlayıcı**: Gemini, ChatGPT (OpenAI), **DeepSeek**, Groq, OpenRouter —
  Ayarlar'dan seçilir; araç çağırma açık uyumlu modellerde çalışır
- ⚡ **Akıllı komutlar** ve **hızlı yol** (hava/döviz/YouTube/saat gibi net komutlar
  ~0.1 sn'de, LLM ve kota harcamadan)
- ⏰ Sesli hatırlatıcılar, 🔔 bildirimler, 🏠 IFTTT/webhook akıllı ev kısayolları
- 🔄 **Kendini güncelleme**: arayüz otomatik yenilenir; `.exe` (opsiyonel `update_url` ile)
- 📴 API anahtarı olmasa bile **çevrimdışı modda** çalışır

## Windows uygulamasını çalıştırma
Hazır uygulama: **`dist\Jarvis\Jarvis.exe`** — çift tıkla, biter. Masaüstündeki
**Jarvis** kısayolu (`pythonw` ile native pencere) her koşulda çalışır.
`config.json` dosyası exe'nin yanında (`dist\Jarvis\config.json`) durur; anahtarını
oradan da düzenleyebilirsin (ya da uygulama içi ⚙️ Ayarlar'dan).

> Neden **onedir** (klasör)? `pywebview`/`pythonnet` tek-dosya (`onefile`) derlemede
> ~15 sn sonra çöküyordu; onedir kararlı çalışıyor. Bu yüzden `dist\Jarvis\` klasörünü
> bir bütün olarak taşı/paylaş (içinde `Jarvis.exe` + `_internal`).

Yeniden derlemek istersen (kod değişince):
```powershell
python -m PyInstaller Jarvis.spec --noconfirm --distpath dist --workpath build
# sonra config'i yanına kopyala:
copy config.json dist\Jarvis\config.json
```

## Android APK
Telefona kurulan gerçek uygulama için: **[APK.md](APK.md)**

## Gereken tek şey
Bilgisayarınızda **Python 3** kurulu olması yeterli. Başka kurulum yok.


## 1) Ücretsiz yapay zeka anahtarı al (isteğe bağlı)
Anahtar olmadan da çalışır ama gerçek yapay zeka için bir tane alın:

**Seçenek A - Google Gemini (kredi kartı istemez):**
1. https://aistudio.google.com/app/apikey adresine gir
2. "Create API key" ile anahtar oluştur, kopyala

**Seçenek B - Groq (çok hızlı, ücretsiz):**
1. https://console.groq.com/keys adresine gir
2. Anahtar oluştur, kopyala

## 2) Anahtarı programa tanıt
`config.json` dosyasını aç ve anahtarını yaz:

```json
{
  "provider": "gemini",
  "api_key": "BURAYA_ANAHTARINI_YAPISTIR",
  "model": "gemini-3.5-flash-lite"
}
```

> **Önemli (ücretsiz kota):** Google'ın ücretsiz katmanında `gemini-3-flash-preview`
> ve benzeri **3.x Flash** modelleri **günde yalnızca 20 istek** verir ve çabucak
> tükenir ("429 / quota" hatası). Bu yüzden varsayılan model **`gemini-3.5-flash-lite`
> (günde ~500 istek)** yapıldı. Kod, sırayla birden çok modele düşerek (fallback)
> kotayı ve kesintiyi en aza indirir. Ayrıca hava durumu, döviz, saat gibi komutlar
> **modeli hiç çağırmadan** (anahtarsız servislerle) yanıt verir.

> En kolayı: uygulamayı aç, **⚙️ Ayarlar → Yapay zeka sağlayıcı** seç (Gemini /
> ChatGPT / DeepSeek / Groq / OpenRouter), model ve anahtarı yaz → **kaydet**.
> Her sağlayıcı için anahtar `config.json`'daki `keys` alanında saklanır.

## 3) Çalıştır
**En kolay yol:** Bu klasördeki **`baslat.cmd`** dosyasına çift tıkla. Sunucu açılır
ve PC tarayıcısı otomatik başlar. Açılan siyah pencereyi kapatma.

**Komutla:** Bu klasörde bir terminal aç ve şunu çalıştır:

```powershell
python server.py
```

Ekranda iki adres görünecek:
- **PC'de:** `http://localhost:8000`
- **Telefonda:** `http://192.168.x.x:8000`  (telefon aynı Wi-Fi'de olmalı)

## 4) Telefonda kullan
1. Telefon tarayıcısını (Chrome önerilir) aç, yukarıdaki `192.168...` adresini yaz
2. Menüden **"Ana ekrana ekle"** de → artık uygulama gibi açılır
3. Mikrofon ve bildirim izinlerini ver
4. `🎤` butonuna bas ve konuş: *"Merhaba Jarvis"*, *"2 dakika sonra çayı hatırlat"*

> Not: Sesle dinleme Chrome/Edge'de çalışır. iPhone Safari'de kısıtlı olabilir.
> Mikrofon birçok tarayıcıda sadece **HTTPS** veya `localhost`'ta açılır; bu yüzden
> telefonda sesle kullanmak için internete yayınlamak en iyisidir (bkz. DEPLOY.md).

## 5) Eller serbest: "Hey Jarvis" modu
Üst taraftaki `👂` butonuna bas (veya Ayarlar → "Uyandırma modu") ve mikrofona izin
ver. Artık sadece **"Jarvis"** dediğinde uyanır. Uyandırma kelimesini Ayarlar'dan
değiştirebilirsin. Örnek: *"Jarvis, YouTube'da tarkan çal"*, *"Jarvis not al: süt al"*.

## 6) Akıllı ev / webhook (isteğe bağlı)
`config.json` içindeki `shortcuts` bölümüne "komut": "webhook-adresi" ekle.
Örneğin IFTTT ile ışığı açmak için:

```json
"shortcuts": {
  "ışığı aç":  "https://maker.ifttt.com/trigger/light_on/with/key/ANAHTARIN",
  "ışığı kapat": "https://maker.ifttt.com/trigger/light_off/with/key/ANAHTARIN"
}
```

Söylediğinde adres sessizce çağrılır (webhook tetiklenir).

## İnternete yayınlama
Telefondan her yerden (ve mikrofonla) kullanmak için ücretsiz yayın adımları:
**[DEPLOY.md](DEPLOY.md)**

## Dosyalar
| Dosya | Görev |
|-------|-------|
| `dist\Jarvis\Jarvis.exe` | **Windows uygulaması** (tarayıcısız, onedir klasör) |
| `jarvis_app.py` | Masaüstü uygulama kaynağı (native WebView2 penceresi) |
| `Jarvis.spec` | PyInstaller derleme tanımı (onedir) |
| `jarvis_agent.py` | Ajan döngüsü: araç çağırma (Gemini + OpenAI uyumlu) |
| `jarvis_tools.py` | Sistem araçları (uygulama/ses/ekran/dosya/…) |
| `jarvis_memory.py` | Kalıcı hafıza (SQLite) |
| `jarvis_updater.py` | `.exe` otomatik güncelleme |
| `tools/selftest.py` | Uçtan uca otomatik test |
| `baslat.cmd` | Tarayıcı sürümünü tek tıkla başlatır |
| `server.py` | Web sunucusu + yapay zeka köprüsü (çok sağlayıcı) |
| `config.json` | API anahtarı, sağlayıcı/model, ayarlar, kısayollar |
| `public/index.html` | Arayüz |
| `public/app.js` | Ses, sohbet, akıllı komutlar, hatırlatıcı mantığı |
| `public/style.css` | Jarvis görünümü |
| `public/icons/` | Uygulama ikonları (PNG + ICO) |
| `public/manifest.json`, `public/sw.js` | PWA (APK ve tarayıcı için) |
| `tools/make_icons.py` | İkonları yeniden üretir |
| `APK.md` | Android APK yapım rehberi |
| `DEPLOY.md` | Ücretsiz internete yayınlama rehberi |
| `Dockerfile`, `render.yaml`, `Procfile` | Bulut yayın dosyaları |

## Sorun giderme
- **"Sunucuya ulaşılamıyor"**: `python server.py` çalışıyor mu? Portu değiştirmek
  için: `$env:JARVIS_PORT=8080; python server.py`
- **Telefondan açılmıyor**: Windows Güvenlik Duvarı Python'a izin vermeli. "Ağ"
  iznini ver. Telefon ve PC aynı Wi-Fi'de olmalı.
- **Mikrofon/ses çalışmıyor**: Tarayıcılar mikrofonu genelde sadece **HTTPS** veya
  `localhost`'ta açar. Yerel `http://192.168...` açılmazsa, internete yayınla
  ([DEPLOY.md](DEPLOY.md)) ve çıkan `https://...` adresiyle kullan.
- **`.exe` açılmıyor / "Uygulama Denetimi ilkesi engelledi"**: Windows **Smart App
  Control** imzasız uygulamayı engelliyor demektir. Çözüm: masaüstündeki **Jarvis**
  kısayolunu kullan (Python ile çalışır, engellenmez) **veya** Smart App Control'ü
  kapat (Ayarlar → Gizlilik ve güvenlik → Windows Güvenliği).
- **"429 / kota doldu" hatası**: Gemini ücretsiz katmanı çok dardır (3.x Flash =
  günde 20). Varsayılan `gemini-3.5-flash-lite` (günde ~500) kullanın; kod zaten
  otomatik olarak yedek modellere geçer. Hava/döviz/saat gibi komutlar modeli hiç
  çağırmaz.
- **Hava durumu/döviz çalışmıyor**: Bu araçlar internet erişimi ister (anahtarsız
  servisler: Open-Meteo, frankfurter). Ağ yoksa veya geçici kesinti olursa tekrar
  deneyin.
- **Test**: `python tools/selftest.py` (sunucu açıkken) tüm özellikleri sınar.
