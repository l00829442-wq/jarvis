# Jarvis'i İnternete Yayınlama (ücretsiz)

Böylece telefondan **her yerden** (Wi-Fi'ye bağlı olmadan) erişebilirsin.
Ayrıca **HTTPS** sayesinde telefonda **mikrofon/sesle dinleme de çalışır**
(birçok tarayıcı mikrofonu sadece HTTPS veya localhost'ta açar).

> ⚠️ **Önemli:** API anahtarını `config.json` ile repoya **koymayın**. Sunucu,
> anahtarı ortam değişkeni (`JARVIS_API_KEY`) üzerinden de okur. Repoda
> `config.json` `.gitignore` ile gizlidir.

---

## Yol A - Render (en kolay, ücretsiz)

### 1) Kodu GitHub'a koy
Git kurulu değilse: https://git-scm.com/download/win adresinden kur.
Sonra bu klasörde:

```powershell
git init
git add .
git commit -m "Jarvis"
```

GitHub'da yeni bir **boş** repo aç (örnek: `jarvis`), sonra:

```powershell
git branch -M main
git remote add origin https://github.com/KULLANICI_ADIN/jarvis.git
git push -u origin main
```

> Git kullanmak istemezsen **GitHub Desktop** uygulaması ile de bu klasörü
> repoya yükleyebilirsin.

### 2) Render'da yayınla
1. https://render.com → ücretsiz kaydol (GitHub ile giriş yap)
2. **New → Web Service** → GitHub reponu seç
3. Ayarlar:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python server.py`
   - **Instance Type:** Free
4. **Environment** sekmesinde değişken ekle:
   - `JARVIS_PROVIDER` = `gemini`   (ayrıca: `deepseek`, `openai`, `groq`, `openrouter`)
   - `JARVIS_MODEL` = `gemini-3-flash-preview`  (DeepSeek: `deepseek-chat`, OpenAI: `gpt-4o-mini`)
   - `JARVIS_API_KEY` = senin anahtarın (aktif sağlayıcının anahtarı)
5. **Create Web Service** → birkaç dakika sonra sana şöyle bir adres verir:
   `https://jarvis-xxxx.onrender.com`

### 3) Telefonda kullan
1. Telefon tarayıcısında (Chrome) o `https://...` adresini aç
2. Menü → **Ana ekrana ekle** → uygulama gibi açılır
3. Mikrofon ve bildirim izinlerini ver. Artık sesle de çalışır. 🎉

> Not: Render ücretsiz planı 15 dk hareketsizlikte uyur; ilk açılış ~30-50 sn
> sürebilir. Kullanınca hemen uyanır.

---

## Yol B - Docker (VPS veya kendi sunucun)

`Dockerfile` hazır. Sunucuda:

```bash
docker build -t jarvis .
docker run -d -p 8000:8000 \
  -e JARVIS_PROVIDER=gemini \
  -e JARVIS_API_KEY=SENIN_ANAHTARIN \
  --name jarvis jarvis
```

Ardından bir reverse proxy (Caddy/Nginx) ile HTTPS bağla (ör. Caddy tek satır).

---

## Yol C - Sadece aynı Wi-Fi (kurulum yok)

Yayınlamadan denemek istersen: `python server.py` çalıştır, telefondan
`http://192.168.x.x:8000` aç. **Ama mikrofon burada çalışmayabilir** (HTTPS yok).
Ses önemliyse Yol A'yı kullan.

---

## Ortam değişkenleri (özet)

| Değişken | Açıklama | Örnek |
|----------|----------|-------|
| `JARVIS_API_KEY` | Yapay zeka anahtarı | `AIza...` |
| `JARVIS_PROVIDER` | `gemini` / `deepseek` / `openai` / `groq` / `openrouter` | `gemini` |
| `JARVIS_MODEL` | Model adı | `gemini-3-flash-preview` |
| `PORT` | (Bulut otomatik verir) | `10000` |
| `JARVIS_PORT` | Yerel port | `8000` |
