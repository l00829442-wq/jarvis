# Android APK (telefona kurulan gerçek uygulama)

Jarvis'i telefona **uygulama olarak** kurmanın ücretsiz yolu: PWA'yı **PWABuilder**
ile APK'ya çevirmek. Bu yöntem, hazırladığımız `.exe` gibi tam ekran, tarayıcı
arayüzü olmayan bir uygulama üretir.

> Önemli: APK, internette yayınlanmış **HTTPS adresine** bağlanır. Bu yüzden önce
> [DEPLOY.md](DEPLOY.md) ile Jarvis'i ücretsiz yayınlaman gerekir (Render).

---

## 1) Jarvis'i internete yayınla
DEPLOY.md'deki **Yol A – Render** adımlarını uygula. Sonunda elinde şöyle bir adres
olacak: `https://jarvis-xxxx.onrender.com`

Ayrıca Render panelinde şu ortam değişkenini ekle (API anahtarın):
- `JARVIS_API_KEY` = Gemini anahtarın
- `JARVIS_MODEL` = `gemini-3-flash-preview`
- `JARVIS_PROVIDER` = `gemini` (istersen `deepseek`, `openai`, `groq`, `openrouter`)

> Not: Uygulama içindeki **⚙️ Ayarlar → Yapay zeka sağlayıcı** bölümünden
> sağlayıcı/model/anahtarı sonradan da değiştirebilirsin (DeepSeek, ChatGPT,
> Gemini, Groq, OpenRouter). Anahtarlar cihazın `config.json`'unda saklanır.

## 2) PWABuilder ile APK üret
1. Tarayıcıda **https://www.pwabuilder.com** aç
2. Kutuya Render adresini yaz: `https://jarvis-xxxx.onrender.com` → **Start**
3. PWABuilder uygulamayı inceler:
   - **Manifest** ✔ (ikonlar 192/512 hazır)
   - **Service Worker** ✔
   - Skorlar yeşil olmalı
4. **"Package for Stores"** → **Android** seç
5. Ayarlar:
   - **Package ID:** `com.senin.jarvis` (kendine göre)
   - **App name:** `Jarvis`
   - **Signing key:** **"Create new"** seç (PWABuilder senin için imza anahtarı
     üretir). **Bu anahtarı mutlaka indir ve sakla** (güncelleme için gerekir).
6. **Download** → sana bir klasör verir:
   - `*.apk` → telefona kurulacak dosya
   - `*.aab` → Play Store için (istersen)
   - `signing.keystore` + şifreler → **sakla!**

## 3) Telefona kur
1. APK dosyasını telefona aktar (USB, WhatsApp, Drive — ne olursa)
2. Dosyaya dokun → "Bilinmeyen kaynaklara izin ver" derse onayla
3. **Kur** → ana ekranda Jarvis ikonu görünür
4. İlk açılışta **mikrofon** ve **bildirim** izinlerini ver

## 4) Güncelleme (kodu değiştirince)
- Kodu değiştirip GitHub'a gönder → Render otomatik yayınlar.
- Telefondaki uygulama aynı adresi yüklediği için **otomatik güncellenir**.
  (Yeni APK üretmene gerek yok, sadece arayüz yenilenir.)

---

## Sık sorulanlar

**Ses/mikrofon çalışsın istiyorum.** APK, yayınlanan **HTTPS** adresini kullandığı
için mikrofon çalışır (yerel `http://` çalışmazdı).

**"Uygulama açılmıyor / beyaz ekran."** Render ücretsiz planı uykuda olabilir; ilk
açılış 30-50 sn sürebilir. Bekle ve tekrar dene.

**Play Store'a koymak istiyorum.** PWABuilder'ın verdiği `.aab` dosyasını Play
Console'a yükleyebilirsin (tek seferlik 25$ hesap ücreti).

**Tamamen kendi WebView APK'mı yapmak istiyorum (internet gerekmesin).** Bu, Android
Studio + JDK + Gradle gerektirir (ağır kurulum); istersen o yolu da anlatabilirim.
