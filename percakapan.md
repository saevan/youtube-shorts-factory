# Log Percakapan

File ini mencatat progres dan panduan untuk YouTube Shorts Factory.

---

## 📊 Status Pipeline (30 Juni 2026)

| Fase | Status | Keterangan |
|------|--------|------------|
| 1️⃣ Ideation & Scripting | ✅ OK | Gemini + DeepSeek |
| 2️⃣ Audio & Subtitle | ✅ OK | TTS edge-tts |
| 3️⃣ Background Video | ✅ OK (timeout fix 300→600s) | yt-dlp download |
| 4️⃣ Video Assembly | ✅ OK | MoviePy render |
| 5️⃣ Upload YouTube | ❌ BLOKIR | **Butuh `client_secret.json`** |

### Fix yang sudah dilakukan
- [`asset_manager.py`](youtube_shorts_factory/asset_manager.py): timeout yt-dlp dinaikkan 300s → 600s

---

## 📋 PANDUAN SETUP `client_secret.json` (Google Cloud Console)

Ikuti langkah-langkah di bawah secara berurutan. Pastikan login dengan **akun Google yang terhubung ke channel YouTube** tujuan upload.

### Langkah 1: Buka Google Cloud Console
👉 [Klik link ini untuk membuka Google Cloud Console](https://console.cloud.google.com/)

### Langkah 2: Buat Project Baru
1. Klik dropdown nama project (atas, sebelah kiri search bar)
2. Klik **"New Project"**
3. Isi **Project name**: `youtube-shorts-factory`
4. Klik **"Create"**
5. Tunggu notifikasi, lalu klik **"Select Project"**

### Langkah 3: Aktifkan YouTube Data API v3
1. Di sidebar kiri ☰ → **APIs & Services** → **Library**
2. Search: `YouTube Data API v3`
3. Klik kartunya → klik **"Enable"**

### Langkah 4: Setup OAuth Consent Screen (Detail)

> **Catatan:** Saat klik "OAuth consent screen" di sidebar, Anda akan masuk ke halaman **OAuth Overview**. Itu benar! Cari tombol **"CREATE"** atau **"GET STARTED"** untuk mulai.

#### 4A: App Information
1. Pastikan Anda di halaman **OAuth consent screen** (dari sidebar ☰ → **APIs & Services** → **OAuth consent screen**)
2. Jika halaman **OAuth Overview** muncul → klik tombol **"CREATE"** atau **"GET STARTED"** (biru, di tengah)
3. Pilih **"External"** (satu-satunya opsi) → klik **"Create"** (atau **"START"**)
4. Isi form:
   - **App name**: `YouTube Shorts Factory`
   - **User support email**: pilih email Google kamu dari dropdown
   - **Logo**: kosongkan (lewati)
   - **App domain**: kosongkan
   - **Authorized domains**: kosongkan
   - **Developer contact information**: isi email Google kamu
5. Klik **"Save and Continue"** (biru, di bawah)

#### 4B: Scopes
1. Di halaman **Scopes**, klik **"Add or Remove Scopes"**
2. Panel samping akan muncul → di kolom filter, ketik: `youtube.upload`
3. Centang **`.../auth/youtube.upload`**
4. Klik **"Update"** (tombol di atas panel)
5. Klik **"Save and Continue"**

#### 4C: Test Users
1. Klik **"+ ADD USERS"** (atau **"Add Users"**)
2. Masukkan **email YouTube channel kamu** (yang akan dipakai upload video)
3. Klik **"Add"**
4. Klik **"Save and Continue"**

#### 4D: Summary
1. Review semua yang sudah diisi
2. Klik **"Back to Dashboard"** (jangan klik "Submit for Verification" — mode Testing sudah cukup)

> ✅ **Selesai!** Lanjut ke Langkah 5 untuk download file `client_secret.json`

### Langkah 5: Download `client_secret.json`
1. Sidebar kiri ☰ → **APIs & Services** → **Credentials**
2. Klik **"+ CREATE CREDENTIALS"** → **"OAuth client ID"**
3. **Application type**: **"Desktop app"**
4. **Name**: `YouTube Shorts Factory Desktop`
5. Klik **"Create"**
6. Akan muncul popup → klik **"DOWNLOAD JSON"**
7. File terdownload: `client_secret_123...json`
8. **Rename jadi**: `client_secret.json`
9. **Pindahkan** ke folder: [`youtube_shorts_factory/credentials/client_secret.json`](youtube_shorts_factory/credentials/)

### ✅ Setelah itu:
Kembali ke sini, saya akan:
1. Jalankan OAuth login (browser akan terbuka)
2. Test pipeline manual: `python main.py --run-now`
3. Satu video yang sudah siap akan otomatis terupload!

---

## ⚠️ Catatan Penting
- Aplikasi dalam mode **"Testing"** — token OAuth berlaku **7 hari**
- Setelah 7 hari, token akan di-refresh otomatis selama Anda pernah login sekali
- Jika token expired, hapus `credentials/youtube_token.json` dan login ulang
