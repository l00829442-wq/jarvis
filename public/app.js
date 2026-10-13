/* Jarvis - istemci mantığı: ses, sohbet, hatırlatıcı, bildirim */

const $ = (id) => document.getElementById(id);

const state = {
  messages: [],            // {role, content}
  settings: {
    speak: true,
    wake: false,           // sürekli dinleme (uyandırma kelimesi)
    wakeWord: "jarvis",
    name: "Jarvis",
  },
  listening: false,
  busy: false,
  recognition: null,
  voices: [],
  reminders: [],
  notes: [],               // sesli notlar
  shortcuts: {},           // akıllı ev kısayolları (sunucudan)
  awaitingCommand: false,  // "Hey Jarvis" sonrası komut bekleniyor
  speaking: false,
  recorderMode: false,     // Web Speech yoksa: kayıt + Gemini ile yazıya çevir
  recorder: null,          // aktif kayıt durumu
  pendingImage: null,      // gönderilecek görsel (data URL)
};

/* ---------------- Kalıcı ayarlar ---------------- */
const LS = {
  load() {
    try {
      const s = JSON.parse(localStorage.getItem("jarvis.settings") || "{}");
      Object.assign(state.settings, s);
      state.messages = JSON.parse(localStorage.getItem("jarvis.messages") || "[]");
      state.reminders = JSON.parse(localStorage.getItem("jarvis.reminders") || "[]");
      state.notes = JSON.parse(localStorage.getItem("jarvis.notes") || "[]");
    } catch (e) { /* yoksay */ }
  },
  save() {
    localStorage.setItem("jarvis.settings", JSON.stringify(state.settings));
    localStorage.setItem("jarvis.messages", JSON.stringify(state.messages.slice(-40)));
    localStorage.setItem("jarvis.reminders", JSON.stringify(state.reminders));
    localStorage.setItem("jarvis.notes", JSON.stringify(state.notes));
  },
};

/* ---------------- Yardımcılar ---------------- */
function toast(text) {
  const t = $("toast");
  t.textContent = text;
  t.classList.add("show");
  clearTimeout(t._id);
  t._id = setTimeout(() => t.classList.remove("show"), 2600);
}

function setState(text, cls) {
  $("stateText").textContent = text;
  const orb = $("orb");
  orb.classList.remove("listening", "speaking", "thinking");
  if (cls) orb.classList.add(cls);
}

function addMessage(role, content, image) {
  const div = document.createElement("div");
  div.className = "msg " + (role === "user" ? "user" : "ai");
  if (image) {
    const img = document.createElement("img");
    img.src = image;
    img.className = "msg-img";
    div.appendChild(img);
  }
  if (content) {
    const span = document.createElement("span");
    span.textContent = content;
    div.appendChild(span);
  }
  $("chat").appendChild(div);
  $("chat").scrollTop = $("chat").scrollHeight;
  return div;
}

const TOOL_LABELS = {
  get_datetime: "Saat", get_system_info: "Sistem", open_app: "Uygulama aç",
  set_volume: "Ses", take_screenshot: "Ekran görüntüsü", lock_screen: "Kilit",
  remember: "Hafıza", recall: "Hafıza", write_file: "Dosya yaz", read_file: "Dosya oku",
  list_files: "Dosya listesi", web_search: "Web arama", open_url: "Web aç",
  get_weather: "Hava durumu", play_youtube: "YouTube",
};

function addToolBadges(tools) {
  const names = tools.map((t) => TOOL_LABELS[t.arac] || t.arac);
  const div = document.createElement("div");
  div.className = "tool-note";
  div.textContent = "🔧 " + names.join(" · ");
  $("chat").appendChild(div);
  $("chat").scrollTop = $("chat").scrollHeight;
}

/* Gelen eylemleri (açılacak linkler) kullanıcının cihazında gerçekleştir */
function addActionLink(url, label) {
  const div = document.createElement("div");
  div.className = "msg ai";
  const a = document.createElement("a");
  a.href = url;
  a.target = "_blank";
  a.rel = "noopener";
  a.className = "action-link";
  a.textContent = "▶ " + (label || "Aç: " + url);
  div.appendChild(a);
  $("chat").appendChild(div);
  $("chat").scrollTop = $("chat").scrollHeight;
}

function runActions(actions) {
  if (!actions || !actions.length) return;
  const local = ["localhost", "127.0.0.1", "::1"].includes(location.hostname);
  actions.forEach((a) => {
    if (!a || a.type !== "open_url" || !a.url) return;
    if (local) {
      fetch("/api/open", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: a.url }),
      }).catch(() => {});
      return;
    }
    let ok = false;
    try { ok = !!window.open(a.url, "_blank"); } catch (e) { ok = false; }
    if (!ok) addActionLink(a.url);
  });
}

function addTyping() {
  const div = document.createElement("div");
  div.className = "msg ai typing";
  div.innerHTML = "<span></span><span></span><span></span>";
  $("chat").appendChild(div);
  $("chat").scrollTop = $("chat").scrollHeight;
  return div;
}

function renderHistory() {
  $("chat").innerHTML = "";
  state.messages.forEach((m) => addMessage(m.role, m.content));
}

/* ---------------- Bağlantı durumu ---------------- */
async function checkHealth() {
  try {
    const r = await fetch("/api/health");
    const d = await r.json();
    const info = `Sağlayıcı: ${d.provider} | Model: ${d.model} | Anahtar: ${d.has_key ? "var" : "yok"}`;
    $("connInfo").textContent = info;
    if (d.has_key) {
      $("statusDot").className = "dot online";
      if (!state.messages.length) setState("Hazırım efendim.");
    } else {
      $("statusDot").className = "dot offline";
      if (!state.messages.length) setState("Çevrimdışı mod • API anahtarı ekleyin");
    }
  } catch (e) {
    $("statusDot").className = "dot error";
    setState("Sunucuya ulaşılamıyor");
  }
}

/* ---------------- Ses: dinleme ---------------- */
function micSupported() {
  return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
}

function initRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return null;
  const rec = new SR();
  rec.lang = "tr-TR";
  rec.interimResults = false;
  rec.continuous = false;
  rec.maxAlternatives = 1;

  rec.onstart = () => {
    state.listening = true;
    $("micBtn").classList.add("listening");
    if (!state.awaitingCommand) setState("Dinliyorum...", "listening");
  };
  rec.onresult = (e) => {
    for (let i = e.resultIndex; i < e.results.length; i++) {
      if (!e.results[i].isFinal) continue;
      handleTranscript(e.results[i][0].transcript.trim());
    }
  };
  rec.onerror = (e) => {
    const err = e.error || "bilinmeyen";
    if (err === "aborted" || err === "no-speech") return;
    if (err === "network" || err === "service-not-allowed" || err === "language-not-supported") {
      enableRecorderMode("tarayıcı konuşma servisi yok: " + err);
      addMessage("assistant", "Tarayıcının konuşma servisi çalışmıyor. Artık 🎤 ile bas-konuş yapabilirsin (kayıt sunucuda yazıya çevrilir).");
      return;
    }
    if (err === "not-allowed") {
      state.settings.wake = false;
      LS.save();
      syncSettingsUI();
      addMessage("assistant", "Mikrofon izni verilmedi (not-allowed). Cihazın/uygulamanın mikrofon iznini aç ve tekrar dene.");
      toast("Mikrofon izni gerekli");
    } else {
      addMessage("assistant", "Sesle dinleme hatası: " + err);
      toast("Dinleme hatası: " + err);
    }
  };
  rec.onend = () => {
    state.listening = false;
    $("micBtn").classList.remove("listening");
    // Uyandırma modu açıksa mikrofonu sürekli açık tut
    if (state.settings.wake && !state.speaking && !state.busy && !state.awaitingCommand) {
      setTimeout(safeStart, 350);
    } else if (!state.busy && !state.speaking) {
      setState("Hazırım efendim.");
    }
  };
  return rec;
}

function safeStart() {
  if (!state.recognition || state.listening || state.speaking) return;
  try {
    state.recognition.continuous = state.settings.wake;
    state.recognition.start();
  } catch (e) { /* zaten çalışıyor */ }
}

/* Gelen metni işle: uyandırma kelimesi mi, yoksa komut mu? */
function handleTranscript(transcript) {
  const ww = (state.settings.wakeWord || "jarvis").toLowerCase();
  const lower = transcript.toLowerCase();

  if (!state.settings.wake) {
    handleUserInput(transcript);
    return;
  }
  if (state.awaitingCommand) {
    state.awaitingCommand = false;
    setState("Hazırım efendim.");
    if (transcript.length > 1) handleUserInput(transcript);
    return;
  }
  if (lower.includes(ww)) {
    const rest = transcript
      .replace(new RegExp(ww, "i"), "")
      .replace(/^[\s,.!?]+/, "")
      .trim();
    if (rest.length > 2) {
      handleUserInput(rest);
    } else {
      state.awaitingCommand = true;
      setState("Dinliyorum efendim...", "listening");
      beep();
    }
  }
}

function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.frequency.value = 880;
    g.gain.value = 0.06;
    o.connect(g); g.connect(ctx.destination);
    o.start();
    setTimeout(() => { o.stop(); ctx.close(); }, 120);
  } catch (e) { /* yoksay */ }
}

function toggleListen() {
  if (state.recorderMode) { toggleRecord(); return; }
  if (!state.recognition) {
    toast("Tarayıcınız sesle dinlemeyi desteklemiyor");
    return;
  }
  if (state.listening) {
    state.recognition.stop();
  } else {
    safeStart();
  }
}

function toggleWake() {
  if (state.recorderMode) { toast("Bu uygulamada 🎤 ile bas-konuş yap"); return; }
  if (!micSupported()) { toast("Bu tarayıcı sesle dinlemeyi desteklemiyor"); return; }
  state.settings.wake = !state.settings.wake;
  state.awaitingCommand = false;
  LS.save();
  syncSettingsUI();
  if (state.settings.wake) {
    toast("Uyandırma modu açık: \"" + state.settings.wakeWord + "\" de");
    safeStart();
  } else {
    if (state.recognition) state.recognition.stop();
    toast("Uyandırma modu kapalı");
  }
}

/* ---------------- Ses: kayıt + Gemini ile yazıya çevirme ----------------
   Tarayıcı konuşma servisi olmayan ortamlarda (ör. masaüstü WebView2
   uygulaması) mikrofonu kaydedip sunucudaki /api/transcribe ile metne çevirir. */
function isDesktopApp() {
  return !!window.pywebview;
}

function enableRecorderMode(reason) {
  if (state.recorderMode) return;
  state.recorderMode = true;
  state.settings.wake = false;
  state.awaitingCommand = false;
  LS.save();
  syncSettingsUI();
  const wb = $("wakeBtn");
  if (wb) { wb.style.opacity = "0.35"; wb.title = "Uyandırma modu yalnızca tarayıcıda çalışır"; }
  const mb = $("micBtn");
  if (mb) mb.title = "Bas-konuş: bas, konuş, bitirmek için tekrar bas";
  console.log("[Jarvis] Kayıt modu aktif:", reason);
}

function toggleRecord() {
  if (state.recorder && state.recorder.active) stopRecord();
  else startRecord();
}

async function startRecord() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    addMessage("assistant", "Bu cihazda mikrofon kaydı desteklenmiyor.");
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const Ctx = window.AudioContext || window.webkitAudioContext;
    const ctx = new Ctx();
    const src = ctx.createMediaStreamSource(stream);
    const proc = ctx.createScriptProcessor(4096, 1, 1);
    const mute = ctx.createGain();
    mute.gain.value = 0;
    const chunks = [];
    proc.onaudioprocess = (e) => chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
    src.connect(proc);
    proc.connect(mute);
    mute.connect(ctx.destination);
    state.recorder = { active: true, stream, ctx, proc, src, chunks, rate: ctx.sampleRate };
    state.listening = true;
    $("micBtn").classList.add("listening");
    setState("Kaydediyorum... bitirmek için tekrar bas", "listening");
    beep();
  } catch (e) {
    const msg = (e && e.name) ? e.name : "hata";
    addMessage("assistant", "Mikrofona erişilemedi (" + msg + "). İzin verildiğinden emin ol.");
    toast("Mikrofon hatası: " + msg);
  }
}

function stopRecord() {
  const r = state.recorder;
  if (!r || !r.active) return;
  r.active = false;
  state.listening = false;
  $("micBtn").classList.remove("listening");
  try { r.stream.getTracks().forEach((t) => t.stop()); } catch (e) { /* yoksay */ }
  try { r.proc.disconnect(); r.src.disconnect(); } catch (e) { /* yoksay */ }
  try { r.ctx.close(); } catch (e) { /* yoksay */ }

  const samples = mergeChunks(r.chunks);
  r.chunks = [];
  if (!samples.length) { setState("Ses algılanamadı."); return; }
  const wav = encodeWav(downsampleTo16k(samples, r.rate), 16000);
  setState("Düşünüyorum...", "thinking");
  transcribeWav(wav);
}

function mergeChunks(chunks) {
  let len = 0;
  for (const c of chunks) len += c.length;
  const out = new Float32Array(len);
  let off = 0;
  for (const c of chunks) { out.set(c, off); off += c.length; }
  return out;
}

function downsampleTo16k(samples, inRate) {
  if (inRate === 16000) return samples;
  const ratio = inRate / 16000;
  const outLen = Math.floor(samples.length / ratio);
  const out = new Float32Array(outLen);
  for (let i = 0; i < outLen; i++) {
    const start = Math.floor(i * ratio);
    const end = Math.min(Math.floor((i + 1) * ratio), samples.length);
    let sum = 0, n = 0;
    for (let j = start; j < end; j++) { sum += samples[j]; n++; }
    out[i] = n ? sum / n : samples[start] || 0;
  }
  return out;
}

function encodeWav(samples, rate) {
  const buf = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buf);
  const writeStr = (off, s) => { for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i)); };
  writeStr(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeStr(36, "data");
  view.setUint32(40, samples.length * 2, true);
  let off = 44;
  for (let i = 0; i < samples.length; i++, off += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return buf;
}

function bufferToBase64(buf) {
  const bytes = new Uint8Array(buf);
  let bin = "";
  const step = 0x8000;
  for (let i = 0; i < bytes.length; i += step) {
    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + step));
  }
  return btoa(bin);
}

async function transcribeWav(wavBuffer) {
  try {
    const resp = await fetch("/api/transcribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ audio: bufferToBase64(wavBuffer), mime: "audio/wav" }),
    });
    const data = await resp.json();
    if (!resp.ok || data.error) {
      addMessage("assistant", "Sesi yazıya çeviremedim: " + (data.error || resp.status));
      setState("Hazırım efendim.");
      return;
    }
    const text = (data.text || "").trim();
    if (!text) { setState("Anlayamadım efendim."); return; }
    handleUserInput(text);
  } catch (e) {
    addMessage("assistant", "Ses gönderilemedi: " + e.message);
    setState("Hazırım efendim.");
  }
}

/* ---------------- Ses: konuşma ---------------- */
function initVoices() {
  if (!window.speechSynthesis) return;
  const load = () => { state.voices = speechSynthesis.getVoices(); };
  load();
  speechSynthesis.onvoiceschanged = load;
}

function speak(text) {
  if (!state.settings.speak || !window.speechSynthesis) return;
  // Kendi sesimizi duymamak için uyandırma modunda mikrofonu geçici kapat
  if (state.settings.wake && state.recognition) {
    try { state.recognition.stop(); } catch (e) { /* yoksay */ }
  }
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "tr-TR";
  const tr = state.voices.find((v) => v.lang && v.lang.startsWith("tr"));
  if (tr) u.voice = tr;
  state.speaking = true;
  u.onstart = () => setState("Konuşuyorum...", "speaking");
  u.onend = () => {
    state.speaking = false;
    setState("Hazırım efendim.");
    if (state.settings.wake) setTimeout(safeStart, 400);
  };
  u.onerror = () => { state.speaking = false; };
  speechSynthesis.speak(u);
}

/* ---------------- Hatırlatıcılar ---------------- */
function trySetReminder(text) {
  // "5 dakika sonra ... hatırlat" veya "30 saniye sonra ..."
  const m = text.match(/(\d+)\s*(saniye|dakika|dak|saat)\s*sonra\s*(.+?)(?:hatırlat|hatir[lt]at)?$/i);
  if (!m) return false;
  const n = parseInt(m[1], 10);
  const unit = m[2].toLowerCase();
  const what = m[3].replace(/hatırlat.*$/i, "").trim() || "bir şey";
  let ms = n * 1000;
  if (unit.startsWith("dak")) ms = n * 60 * 1000;
  if (unit.startsWith("saat")) ms = n * 60 * 60 * 1000;
  const at = Date.now() + ms;
  state.reminders.push({ at, what });
  LS.save();
  const when = new Date(at).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
  const reply = `Tamam efendim, ${when} saatinde "${what}" için hatırlatacağım.`;
  state.messages.push({ role: "assistant", content: reply });
  addMessage("assistant", reply);
  speak(reply);
  LS.save();
  return true;
}

function checkReminders() {
  const now = Date.now();
  const due = state.reminders.filter((r) => r.at <= now);
  if (!due.length) return;
  state.reminders = state.reminders.filter((r) => r.at > now);
  LS.save();
  due.forEach((r) => {
    const msg = `Efendim, hatırlatmam: ${r.what}`;
    addMessage("assistant", msg);
    speak(msg);
    if ("Notification" in window && Notification.permission === "granted") {
      new Notification("Jarvis Hatırlatıcı", { body: r.what });
    }
  });
}

/* ---------------- Akıllı komutlar ---------------- */
const SITES = {
  youtube: "https://www.youtube.com",
  google: "https://www.google.com",
  whatsapp: "https://web.whatsapp.com",
  instagram: "https://www.instagram.com",
  facebook: "https://www.facebook.com",
  twitter: "https://twitter.com",
  x: "https://twitter.com",
  spotify: "https://open.spotify.com",
  netflix: "https://www.netflix.com",
  gmail: "https://mail.google.com",
  "e-posta": "https://mail.google.com",
  harita: "https://www.google.com/maps",
  maps: "https://www.google.com/maps",
  github: "https://github.com",
  chatgpt: "https://chat.openai.com",
  takvim: "https://calendar.google.com",
  haberler: "https://www.ntv.com.tr",
};

function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

function replyShort(text) {
  state.messages.push({ role: "assistant", content: text });
  addMessage("assistant", text);
  speak(text);
  LS.save();
}

function openUrl(url) {
  const w = window.open(url, "_blank", "noopener");
  if (!w) location.href = url;
}

function fireWebhook(url) {
  fetch(url, { mode: "no-cors" }).catch(() => {});
}

/* Komutu yakalarsa true döner (yapay zekaya gitmesine gerek kalmaz) */
function handleSmartCommand(raw) {
  const t = raw.toLowerCase().trim();
  let m;

  // --- Sesli notlar ---
  if ((m = raw.match(/^not al[:\s]+(.+)$/i))) {
    state.notes.push({ text: m[1].trim(), at: Date.now() });
    LS.save();
    replyShort("Not aldım efendim: " + m[1].trim());
    return true;
  }
  if (/notlar[ıi]m[ıi]?\s*(göster|oku|söyle|neler|listele)/.test(t)) {
    if (!state.notes.length) { replyShort("Henüz kayıtlı notunuz yok efendim."); return true; }
    replyShort("Notlarınız:\n" + state.notes.map((n, i) => `${i + 1}. ${n.text}`).join("\n"));
    return true;
  }
  if (/notlar[ıi]m[ıi]?\s*(temizle|sil)/.test(t)) {
    state.notes = [];
    LS.save();
    replyShort("Tüm notlar silindi efendim.");
    return true;
  }

  // --- YouTube / müzik (cihazda açılır) ---
  if ((m = t.match(/youtube'?[dt][ae]n?\s+(.+)$/)) || (m = t.match(/youtube\s+(.+)$/))) {
    let q = m[1].replace(/\s*(ara|bul|çal|aç|göster|dinle|oynat)\s*$/, "").trim();
    q = q.replace(/^(da|de|dan|den)\s+/, "").trim();
    if (q) {
      openUrl("https://www.youtube.com/results?search_query=" + encodeURIComponent(q));
      replyShort(`YouTube'da "${q}" arıyorum efendim.`);
      return true;
    }
  }
  if ((/\byoutube\b/.test(t) && /(aç|başlat|gir)/.test(t)) || /youtube'?u?\s*(aç|başlat)/.test(t)) {
    openUrl(SITES.youtube);
    replyShort("YouTube açılıyor efendim.");
    return true;
  }
  // Genel "<şarkı/sanatçı> çal / oynat / dinle"
  if ((m = t.match(/^(.+?)\s*(?:çal|çalsana|oynat|oynatır mısın|dinle)$/))) {
    let q = m[1].replace(/^(bana|bir|şu|şunu|bu)\s+/, "").trim();
    if (q && !/^(ses|müzik sesi)/.test(q)) {
      openUrl("https://www.youtube.com/results?search_query=" + encodeURIComponent(q));
      replyShort(`YouTube'da "${q}" arıyorum efendim.`);
      return true;
    }
  }
  if (/^müzik\s*(aç|çal|oynat|başlat)/.test(t) || /(müzik|muzik)\s*(aç|çal|dinle)/.test(t)) {
    openUrl(SITES.youtube);
    replyShort("Müzik için YouTube açılıyor efendim.");
    return true;
  }

  // --- Google arama ---
  if ((m = t.match(/google'?[dt]a\s+(.+?)\s*(?:ara|bul|bak)$/))) {
    const q = m[1].replace(/\s*(ara|bul|bak)\s*$/, "").trim();
    openUrl("https://www.google.com/search?q=" + encodeURIComponent(q));
    replyShort(`Google'da "${q}" arıyorum efendim.`);
    return true;
  }

  // --- Spotify ---
  if ((m = t.match(/spotify'?[dt]a\s+(.+?)\s*(?:çal|ara|aç)?$/))) {
    const q = m[1].replace(/\s*(çal|ara|aç)\s*$/, "").trim();
    openUrl("https://open.spotify.com/search/" + encodeURIComponent(q));
    replyShort(`Spotify'da "${q}" açıyorum efendim.`);
    return true;
  }

  // --- Harita ---
  if ((m = t.match(/(?:harita|maps)'?[dt]a?\s+(.+?)\s*(?:göster|ara|bul|aç|nerede)$/))) {
    const q = m[1].replace(/\s*(göster|ara|bul|aç|nerede)\s*$/, "").trim();
    openUrl("https://www.google.com/maps/search/" + encodeURIComponent(q));
    replyShort(`Haritada "${q}" arıyorum efendim.`);
    return true;
  }

  // --- Akıllı ev kısayolları (config.json / sunucu) ---
  for (const [key, url] of Object.entries(state.shortcuts)) {
    if (key && t.includes(key.toLowerCase())) {
      fireWebhook(url);
      replyShort("Tamam efendim, uyguladım.");
      return true;
    }
  }

  // --- Bilinen siteleri aç: "<site> aç" ---
  for (const [name, url] of Object.entries(SITES)) {
    if (new RegExp("\\b" + name + "\\b").test(t) && /(aç|başlat|gir|açsana)/.test(t)) {
      openUrl(url);
      replyShort(cap(name) + " açılıyor efendim.");
      return true;
    }
  }

  return false;
}

/* ---------------- Sohbet ---------------- */
async function handleUserInput(text) {
  text = (text || "").trim();
  const image = state.pendingImage || null;
  if (!text && !image) return;
  if (!text && image) text = "Bu görselde ne var? Kısaca açıkla.";
  if (state.busy) return;

  state.messages.push({ role: "user", content: text });
  addMessage("user", text, image);
  LS.save();
  clearPendingImage();

  if (!image) {
    if (trySetReminder(text)) return;
    if (handleSmartCommand(text)) return;
  }

  const typing = addTyping();
  state.busy = true;
  setState("Düşünüyorum...", "thinking");

  try {
    const body = { messages: state.messages };
    if (image) body.image = image;
    const r = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const d = await r.json();
    typing.remove();
    const reply = d.reply || d.error || "Bir hata oluştu efendim.";
    state.messages.push({ role: "assistant", content: reply });
    addMessage("assistant", reply);
    if (d.tools && d.tools.length) addToolBadges(d.tools);
    if (d.actions && d.actions.length) runActions(d.actions);
    LS.save();
    speak(reply);
  } catch (e) {
    typing.remove();
    const reply = "Sunucuya ulaşamadım efendim. server.py çalışıyor mu?";
    addMessage("assistant", reply);
    speak(reply);
  } finally {
    state.busy = false;
    if (!state.listening) setState("Hazırım efendim.");
  }
}

/* ---------------- Görsel ekleme (sürükle-bırak / yapıştır / seç) -------- */
function setPendingImage(dataUrl, name) {
  state.pendingImage = dataUrl;
  $("imgThumb").src = dataUrl;
  $("imgName").textContent = name || "görsel eklendi";
  $("imgPreview").hidden = false;
}

function clearPendingImage() {
  state.pendingImage = null;
  $("imgPreview").hidden = true;
  $("imgThumb").removeAttribute("src");
  if ($("imgInput")) $("imgInput").value = "";
}

function loadImageFile(file) {
  if (!file || !file.type.startsWith("image/")) { toast("Sadece görsel dosyaları"); return; }
  if (file.size > 6 * 1024 * 1024) { toast("Görsel çok büyük (en fazla 6 MB)"); return; }
  const reader = new FileReader();
  reader.onload = () => setPendingImage(reader.result, file.name);
  reader.readAsDataURL(file);
}

/* ---------------- Hafıza görünümü ---------------- */
async function openMemory() {
  $("memoryModal").classList.add("open");
  await renderMemory();
}

async function renderMemory() {
  const list = $("memList");
  list.innerHTML = "<p class='muted'>Yükleniyor...</p>";
  try {
    const r = await fetch("/api/memory");
    const d = await r.json();
    const mem = d.memories || [];
    if (!mem.length) { list.innerHTML = "<p class='muted'>Henüz hiçbir şey hatırlamıyorum.</p>"; return; }
    list.innerHTML = "";
    mem.forEach((m) => {
      const row = document.createElement("div");
      row.className = "mem-row";
      const span = document.createElement("span");
      span.textContent = m.content;
      const del = document.createElement("button");
      del.className = "chip-x";
      del.textContent = "🗑";
      del.addEventListener("click", async () => {
        await fetch("/api/memory", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "forget", id: m.id }),
        });
        renderMemory();
      });
      row.appendChild(span);
      row.appendChild(del);
      list.appendChild(row);
    });
  } catch (e) {
    list.innerHTML = "<p class='muted'>Hafıza yüklenemedi.</p>";
  }
}

async function memoryAdd() {
  const v = $("memInput").value.trim();
  if (!v) return;
  $("memInput").value = "";
  await fetch("/api/memory", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: "add", text: v }),
  });
  renderMemory();
}

/* ---------------- Bildirim izni ---------------- */
async function askNotify() {
  if (!("Notification" in window)) { toast("Bu cihaz bildirimi desteklemiyor"); return; }
  const p = await Notification.requestPermission();
  if (p === "granted") { toast("Bildirimler açıldı"); $("notifyBtn").classList.add("active"); }
  else toast("Bildirim izni verilmedi");
}

/* ---------------- Ayarlar ---------------- */
function syncSettingsUI() {
  $("optSpeak").checked = state.settings.speak;
  $("optWake").checked = state.settings.wake;
  $("optWakeWord").value = state.settings.wakeWord;
  $("optName").value = state.settings.name;
  $("speakToggle").classList.toggle("active", state.settings.speak);
  $("wakeBtn").classList.toggle("active", state.settings.wake);
  $("assistantName").textContent = state.settings.name.toUpperCase();
}

let PROVIDER_LIST = [];
let APP_VERSION = "";

async function loadProviders() {
  try {
    const r = await fetch("/api/providers");
    const d = await r.json();
    PROVIDER_LIST = d.providers || [];
    const sel = $("optProvider");
    sel.innerHTML = "";
    PROVIDER_LIST.forEach((p) => {
      const o = document.createElement("option");
      o.value = p.id;
      o.textContent = p.label + (p.free ? " (ücretsiz)" : "");
      sel.appendChild(o);
    });
    if (d.current) sel.value = d.current;
    updateProviderFields();
  } catch (e) { /* sunucu yoksa */ }
}

function currentProvider() {
  const id = $("optProvider").value;
  return PROVIDER_LIST.find((p) => p.id === id) || null;
}

function updateProviderFields() {
  const p = currentProvider();
  if (!p) return;
  $("optModel").value = p.model || p.default_model || "";
  $("keyLink").href = p.key_url || "#";
  $("optApiKey").placeholder = p.has_key ? "kayıtlı (değiştirmek için yazın)" : "bu sağlayıcı için anahtar";
  $("optApiKey").value = "";
}

async function saveAISettings() {
  const p = currentProvider();
  const body = {
    provider: $("optProvider").value,
    model: $("optModel").value.trim() || (p ? p.default_model : ""),
    assistant_name: state.settings.name,
  };
  const k = $("optApiKey").value.trim();
  if (k) body.api_key = k;
  try {
    const r = await fetch("/api/config", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const d = await r.json();
    toast("Kaydedildi: " + (p ? p.label : d.provider));
    await loadProviders();
    checkHealth();
  } catch (e) {
    toast("Kaydedilemedi (sunucu kapalı olabilir)");
  }
}

async function checkUpdate() {
  try {
    const r = await fetch("/api/version");
    const d = await r.json();
    APP_VERSION = d.version;
    $("versionInfo").textContent = "v" + d.version;
  } catch (e) {
    $("versionInfo").textContent = "?";
  }
}

async function autoReloadOnUpdate() {
  const before = APP_VERSION;
  await checkUpdate();
  if (before && APP_VERSION && APP_VERSION !== before) {
    toast("Yeni sürüm var, güncelleniyor...");
    if ("serviceWorker" in navigator) {
      const regs = await navigator.serviceWorker.getRegistrations();
      await Promise.all(regs.map((r) => r.update().catch(() => {})));
    }
    setTimeout(() => location.reload(), 1200);
  }
}

function bindEvents() {
  $("composer").addEventListener("submit", (e) => {
    e.preventDefault();
    const v = $("input").value;
    $("input").value = "";
    handleUserInput(v);
  });
  $("micBtn").addEventListener("click", toggleListen);

  document.querySelectorAll("#quickCmds button").forEach((b) => {
    b.addEventListener("click", () => handleUserInput(b.dataset.cmd));
  });

  $("speakToggle").addEventListener("click", () => {
    state.settings.speak = !state.settings.speak;
    if (!state.settings.speak && window.speechSynthesis) speechSynthesis.cancel();
    LS.save(); syncSettingsUI();
    toast(state.settings.speak ? "Sesli cevap açık" : "Sesli cevap kapalı");
  });

  $("notifyBtn").addEventListener("click", askNotify);
  $("memoryBtn").addEventListener("click", openMemory);
  $("closeMemory").addEventListener("click", () => $("memoryModal").classList.remove("open"));
  $("memAddBtn").addEventListener("click", memoryAdd);
  $("memInput").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); memoryAdd(); } });
  $("memClearBtn").addEventListener("click", async () => {
    await fetch("/api/memory", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "clear" }) });
    renderMemory();
  });

  // Görsel ekleme
  $("imgBtn").addEventListener("click", () => $("imgInput").click());
  $("imgInput").addEventListener("change", (e) => { if (e.target.files[0]) loadImageFile(e.target.files[0]); });
  $("imgClear").addEventListener("click", clearPendingImage);

  // Sürükle-bırak
  const dropzone = document.querySelector(".app");
  ["dragover", "dragenter"].forEach((ev) => dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("dragging"); }));
  ["dragleave", "dragend"].forEach((ev) => dropzone.addEventListener(ev, () => dropzone.classList.remove("dragging")));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragging");
    const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) loadImageFile(f);
  });

  // Ctrl+V ile yapıştırma
  document.addEventListener("paste", (e) => {
    const items = (e.clipboardData && e.clipboardData.items) || [];
    for (const it of items) {
      if (it.type && it.type.startsWith("image/")) {
        const f = it.getAsFile();
        if (f) { loadImageFile(f); e.preventDefault(); }
        break;
      }
    }
  });

  $("wakeBtn").addEventListener("click", toggleWake);
  $("settingsBtn").addEventListener("click", () => {
    syncSettingsUI();
    loadProviders();
    checkUpdate();
    $("settingsModal").classList.add("open");
  });
  $("closeSettings").addEventListener("click", () => $("settingsModal").classList.remove("open"));
  $("optProvider").addEventListener("change", updateProviderFields);
  $("optSaveBtn").addEventListener("click", saveAISettings);

  $("optSpeak").addEventListener("change", (e) => { state.settings.speak = e.target.checked; LS.save(); syncSettingsUI(); });
  $("optWake").addEventListener("change", (e) => {
    state.settings.wake = e.target.checked;
    LS.save();
    syncSettingsUI();
    if (state.settings.wake) safeStart(); else if (state.recognition) state.recognition.stop();
  });
  $("optWakeWord").addEventListener("input", (e) => { state.settings.wakeWord = e.target.value || "jarvis"; LS.save(); });
  $("optName").addEventListener("input", (e) => { state.settings.name = e.target.value || "Jarvis"; LS.save(); syncSettingsUI(); });
  $("clearBtn").addEventListener("click", () => {
    state.messages = [];
    localStorage.removeItem("jarvis.messages");
    renderHistory();
    $("settingsModal").classList.remove("open");
    toast("Sohbet temizlendi");
  });
}

/* ---------------- Kısayolları sunucudan al ---------------- */
async function loadShortcuts() {
  try {
    const r = await fetch("/api/shortcuts");
    const d = await r.json();
    state.shortcuts = d.shortcuts || {};
  } catch (e) { state.shortcuts = {}; }
}

/* ---------------- Başlat ---------------- */
function init() {
  LS.load();
  syncSettingsUI();
  bindEvents();
  initVoices();
  state.recognition = initRecognition();
  renderHistory();
  checkHealth();
  checkUpdate();
  loadShortcuts();
  setInterval(checkReminders, 15000);
  setInterval(autoReloadOnUpdate, 300000);

  if (isDesktopApp() || !micSupported()) {
    enableRecorderMode(isDesktopApp() ? "masaüstü uygulaması" : "tarayıcı konuşma servisi yok");
  }

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  }
  if ("Notification" in window && Notification.permission === "granted") {
    $("notifyBtn").classList.add("active");
  }
  if (state.settings.wake && !state.recorderMode) setTimeout(safeStart, 800);
}

window.addEventListener("pywebviewready", () => enableRecorderMode("pywebview hazır"));
window.addEventListener("load", init);
