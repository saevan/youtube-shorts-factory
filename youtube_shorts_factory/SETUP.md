# 🚀 SETUP GUIDE — YouTube Shorts Content Factory

Panduan lengkap setup dari nol sampai bisa jalan otomatis.

---

## 📁 Struktur Folder

```
youtube_shorts_factory/
├── main.py               # Pipeline utama & scheduler
├── config.py             # Konfigurasi global
├── llm_engine.py         # Fase 1: Gemini + DeepSeek
├── audio_generator.py    # Fase 2: TTS + subtitle
├── asset_manager.py      # Fase 3: Download BG video
├── video_maker.py        # Fase 4: Assembl video
├── uploader.py           # Fase 5: Upload YouTube
├── requirements.txt
├── .env.example
├── .env                  # ← BUAT INI (isi dari .env.example)
├── credentials/
│   ├── client_secret.json   # ← Download dari Google Cloud
│   └── youtube_token.json   # ← Auto-generated saat pertama kali login
├── assets/
│   ├── backgrounds/      # Video BG auto-download di sini
│   └── fonts/            # Font auto-download di sini
└── output/
    ├── audio/
    ├── subtitles/
    └── videos/
```

---

## ⚙️ LANGKAH 1: Install Python & Dependencies

Pastikan Python 3.10+ sudah terinstall.

```powershell
# Buat virtual environment (sangat disarankan)
python -m venv venv
venv\Scripts\activate

# Install semua dependencies
pip install -r requirements.txt

# Install yt-dlp (tool eksternal)
pip install yt-dlp

# Verifikasi edge-tts
edge-tts --list-voices | findstr "id-ID"
```

---

## 🔑 LANGKAH 2: Setup Gemini API Key (GRATIS)

1. Buka [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Login dengan akun Google
3. Klik **"Create API Key"**
4. Copy API Key yang muncul
5. Paste ke file `.env`:
   ```
   GEMINI_API_KEY=AIza...your_key_here
   ```

> **Catatan:** Model `gemini-1.5-flash` gratis dengan limit 15 request/menit dan 1 juta token/hari — cukup untuk 3 video/hari.

---

## 🔑 LANGKAH 3: Setup DeepSeek API Key

1. Buka [https://platform.deepseek.com/](https://platform.deepseek.com/)
2. Daftar akun (bisa pakai email biasa)
3. Masuk ke menu **API Keys** → Klik **"Create new API key"**
4. Copy API Key
5. Paste ke file `.env`:
   ```
   DEEPSEEK_API_KEY=sk-...your_key_here
   ```

> **Catatan:** Model `deepseek-reasoner` (R1) sangat terjangkau. Estimasi biaya: ~$0.002 per video (hampir gratis).

---

## 🔑 LANGKAH 4: Setup YouTube Data API v3 (OAuth 2.0)

Ini bagian paling krusial. Ikuti langkah-langkah berikut dengan teliti.

> **⏱️ Estimasi waktu:** 15-20 menit (sekali setup, tidak perlu diulang)

---

### 4A: Buat Project di Google Cloud Console

1. Buka [Google Cloud Console](https://console.cloud.google.com/)
2. Pastikan login dengan **akun Google yang terhubung ke channel YouTube** tujuan upload
3. Di bagian atas (sebelah kiri search bar), klik nama project saat ini
4. Di modal yang muncul, klik **"New Project"**
5. Isi:
   - **Project name**: `youtube-shorts-factory` (atau nama lain)
   - **Location**: biarkan default (No organization)
6. Klik **"Create"**
7. Tunggu beberapa detik sampai notifikasi muncul, lalu klik **"Select Project"**

---

### 4B: Aktifkan YouTube Data API v3

1. Di sidebar kiri (hamburger menu ☰) → **APIs & Services** → **Library**
2. Di kolom search, ketik: `YouTube Data API v3`
3. Klik kartu **"YouTube Data API v3"**
4. Klik tombol **"Enable"** (biru)
5. Tunggu sampai halaman berubah menjadi dashboard API

---

### 4C: Konfigurasi OAuth Consent Screen

Langkah ini Wajib — Google memerlukan consent screen meskipun hanya untuk akun sendiri.

1. Di sidebar kiri → **APIs & Services** → **OAuth consent screen**
2. Pilih **"External"** (satunya-satunya opsi) → klik **"Create"**
3. **Step 1: App information**
   - **App name**: `YouTube Shorts Factory`
   - **User support email**: pilih email Google kamu
   - **Logo**: kosongkan (tidak wajib)
   - **App domain**: kosongkan
   - **Authorized domains**: kosongkan
   - **Developer contact information**: isi email Google kamu
   - Klik **"Save and Continue"**
4. **Step 2: Scopes** (klik **"Add or Remove Scopes"**)
   - Di panel samping, centang scope: `.../auth/youtube.upload`
   - Klik **"Update"**
   - Klik **"Save and Continue"**
5. **Step 3: Test users**
   - Klik **"+ ADD USERS"**
   - Masukkan **email YouTube channel kamu** (yang akan dipakai upload)
   - Klik **"Add"**
   - Klik **"Save and Continue"**
6. **Step 4: Summary** → review → klik **"Back to Dashboard"**

> ⚠️ **PENTING:** Aplikasi dalam mode "Testing" — ini cukup untuk penggunaan pribadi.
> Token OAuth akan kadaluarsa **7 hari** setelah dibuat. Untuk memperpanjang, kamu perlu:
> - Setelah testing selesai, submit OAuth consent screen untuk **verifikasi** (butuh beberapa hari)
> - Atau, cukup login ulang setiap 7 hari (token akan direfresh otomatis)

---

### 4D: Buat OAuth 2.0 Client ID (Desktop App)

1. Di sidebar kiri → **APIs & Services** → **Credentials**
2. Klik tombol **"+ CREATE CREDENTIALS"** (di bagian atas)
3. Pilih **"OAuth client ID"**
4. **Application type**: pilih **"Desktop app"**
5. **Name**: `YouTube Shorts Factory Desktop` (atau terserah)
6. Klik **"Create"**
7. Akan muncul popup **"OAuth client created"**:
   - Klik **"DOWNLOAD JSON"** — file akan terunduh ke komputer
   - File bernama seperti: `client_secret_123456789-xxxx.apps.googleusercontent.com.json`
8. **Rename** file tersebut menjadi: `client_secret.json`
9. **Pindahkan** ke folder: [`youtube_shorts_factory/credentials/client_secret.json`](youtube_shorts_factory/credentials/)

> ✅ **Cek:** Pastikan file `credentials/client_secret.json` ada dan berisi JSON dengan field `"installed"`.

---

### 4E: Jalankan Autentikasi Pertama (OAuth Flow)

1. Buka terminal di folder [`youtube_shorts_factory/`](youtube_shorts_factory/)
2. Jalankan:

```powershell
.\venv\Scripts\python uploader.py
```

3. Akan muncul log: `🔐 Memulai YouTube OAuth flow (buka browser)...`
4. **Browser akan terbuka otomatis** (jika tidak, buka link yang tercetak di terminal):
   - Login dengan **akun Google yang terdaftar sebagai Test User** (langkah 4C)
   - Klik **"Continue"**
   - Klik **"Allow"** untuk memberikan akses upload ke YouTube
5. Browser akan menampilkan: `Authentication successful. You can close this tab.`
6. Kembali ke terminal — akan terlihat log:
   ```
   💾 Token disimpan: credentials/youtube_token.json
   🚀 Mengupload: ...
   ```
7. **File token** akan tersimpan di: [`credentials/youtube_token.json`](youtube_shorts_factory/credentials/)

---

### Troubleshooting OAuth

| Masalah | Solusi |
|---------|--------|
| **"Error 403: access_denied"** | Email yang dipakai belum ditambahkan sebagai **Test User** di OAuth consent screen (langkah 4C.5) |
| **"redirect_uri_mismatch"** | Pastikan Application type = **Desktop app** (bukan Web app) |
| **"Invalid client"** | File `client_secret.json` rusak — download ulang dari Google Cloud Console |
| **"Token has expired"** | Hapus `youtube_token.json` → jalankan `python uploader.py` lagi |
| **Browser tidak terbuka** | Copas URL dari terminal ke browser manual |
| **Quota exceeded** | YouTube API quota default 10.000 unit/hari. 1 upload ≈ 1.600 unit. Coba lagi besok |

> **ℹ️ Setelah autentikasi pertama**, token akan otomatis di-refresh tanpa perlu login ulang selama token valid.

---

## 📄 LANGKAH 5: Buat File .env

Di folder `youtube_shorts_factory`, buat file `.env` (salin dari `.env.example`):

```powershell
Copy-Item .env.example .env
```

Edit file `.env` dan isi semua nilai:

```env
GEMINI_API_KEY=AIza...
DEEPSEEK_API_KEY=sk-...
YOUTUBE_CLIENT_SECRET_FILE=credentials/client_secret.json
YOUTUBE_TOKEN_FILE=credentials/youtube_token.json
SCHEDULE_TIMES=08:00,13:00,19:00
BG_VIDEO_POOL_SIZE=10
```

---

## 🧪 LANGKAH 6: Test Setiap Fase

Lakukan test bertahap:

```powershell
# Test Fase 1: LLM Script Generation
python llm_engine.py

# Test Fase 2: TTS & Subtitle
python audio_generator.py

# Test Fase 3: Download Background Video (download 3 dulu)
python asset_manager.py

# Test Fase 4: Video Assembly
python video_maker.py

# Test Fase 5: Upload Metadata Generation (tanpa upload)
python uploader.py

# Test Full Pipeline SEKARANG (tanpa menunggu jadwal)
python main.py --run-now
```

---

## ▶️ LANGKAH 7: Jalankan Scheduler

Setelah semua test berhasil:

```powershell
# Jalankan scheduler (berjalan terus di background)
python main.py
```

Atau untuk berjalan terus di background Windows:

```powershell
# Gunakan PM2 (install dulu: npm install -g pm2)
pm2 start "python main.py" --name youtube-factory
pm2 save
pm2 startup
```

---

## 📊 Monitoring

- Log tersimpan di `pipeline.log` secara otomatis
- Setiap video berhasil upload akan tercatat dengan URL YouTube Shorts-nya

---

## 🔧 Troubleshooting

| Masalah | Solusi |
|---------|--------|
| `edge-tts` gagal | Cek koneksi internet — edge-tts butuh internet |
| `yt-dlp` tidak dapat video CC | Ubah `BG_VIDEO_QUERIES` di `config.py` |
| MoviePy error ffmpeg | Run: `imageio_ffmpeg.get_ffmpeg_exe()` di Python |
| YouTube upload quota exceeded | Quota default: 10.000 unit/hari — 1 upload ≈ 1.600 unit |
| Token expired | Hapus `credentials/youtube_token.json`, jalankan `python uploader.py` lagi |
