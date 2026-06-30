"""
uploader.py — Fase 5: Auto Upload ke YouTube Shorts
  - Gunakan YouTube Data API v3 dengan OAuth 2.0
  - Generate judul, deskripsi, tags otomatis via Gemini
  - Upload video sebagai YouTube Shorts (#shorts)
"""
import json
import logging
import os
import pickle
from pathlib import Path

from google import genai
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import config

logger = logging.getLogger(__name__)

_gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)


# ─── Fase 5A: Generate Metadata Video ────────────────────────────────────────
def generate_video_metadata(script: str) -> dict:
    """
    Gunakan Gemini untuk generate judul, deskripsi, dan tags
    berdasarkan script video.

    Returns:
        dict: {"title": str, "description": str, "tags": list[str]}
    """
    prompt = f"""
Kamu adalah spesialis SEO YouTube untuk konten edukasi keuangan Gen Z Indonesia.
Berikut adalah script video YouTube Shorts:

---
{script}
---

Tugasmu adalah membuat metadata YouTube yang optimal:

1. JUDUL: Maksimal 90 karakter total (termasuk #shorts di akhir).
   Harus clickbait tapi genuine, menggunakan angka atau pertanyaan jika relevan.
   Format: [Judul menarik] #shorts

2. DESKRIPSI: 3-4 kalimat yang menggambarkan video.
   Line pertama adalah hook (paling penting untuk SEO).
   Tambahkan hashtag di akhir: #finansial #genz #edukasikeuangan #shorts #investing

3. TAGS: List 15 tags relevan dalam bahasa Indonesia dan Inggris.
   Tags harus mix: broad (finance, money) + specific (paylater, nabung, inflasi).

Jawab HANYA dalam format JSON yang valid seperti ini (tanpa markdown code block):
{{
  "title": "judul di sini #shorts",
  "description": "deskripsi di sini...",
  "tags": ["tag1", "tag2", "tag3", ...]
}}
"""

    logger.info("🤖 Gemini: Generating video metadata...")
    response = _gemini_client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=prompt,
    )
    raw = response.text.strip()

    # Bersihkan jika ada markdown code block
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        metadata = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"❌ Gagal parse JSON metadata: {e}\nRaw: {raw[:300]}")
        # Fallback metadata
        metadata = {
            "title": "Kesalahan finansial yang bikin bokek #shorts",
            "description": (
                "Pelajaran keuangan penting yang wajib diketahui Gen Z Indonesia. "
                "Jangan sampai uangmu habis sia-sia!\n\n"
                "#finansial #genz #edukasikeuangan #shorts"
            ),
            "tags": [
                "edukasi keuangan", "finansial gen z", "tips nabung",
                "financial literacy", "money tips indonesia",
                "paylater bahaya", "investasi pemula", "shorts",
            ],
        }

    # Validasi & trim judul
    title = metadata.get("title", "")
    if len(title) > 100:
        title = title[:97] + "..."
    if "#shorts" not in title.lower():
        title = title[:93] + " #shorts"
    metadata["title"] = title

    logger.info(f"✅ Metadata: {title}")
    return metadata


# ─── Fase 5B: Autentikasi YouTube OAuth ──────────────────────────────────────
def get_youtube_service():
    """
    Return authenticated YouTube API service.
    Pertama kali: buka browser untuk OAuth consent.
    Selanjutnya: gunakan token tersimpan di YOUTUBE_TOKEN_FILE.
    """
    creds = None
    token_path = Path(config.YOUTUBE_TOKEN_FILE)
    secret_path = Path(config.YOUTUBE_CLIENT_SECRET_FILE)

    if not secret_path.exists():
        raise FileNotFoundError(
            f"❌ File client_secret.json tidak ditemukan di {secret_path}.\n"
            "Lihat SETUP.md untuk cara mendapatkannya dari Google Cloud Console."
        )

    # Load token jika sudah ada
    if token_path.exists():
        with open(token_path, "rb") as f:
            creds = pickle.load(f)

    # Refresh atau buat token baru
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("🔄 Refreshing YouTube OAuth token...")
            creds.refresh(Request())
        else:
            logger.info("🔐 Memulai YouTube OAuth flow (buka browser)...")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(secret_path), config.YOUTUBE_SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Simpan token
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)
        logger.info(f"💾 Token disimpan: {token_path}")

    return build("youtube", "v3", credentials=creds)


# ─── Fase 5C: Upload Video ────────────────────────────────────────────────────
def upload_video(video_path: Path, script: str) -> str:
    """
    Upload video ke YouTube dengan metadata yang di-generate Gemini.

    Args:
        video_path: Path ke file .mp4
        script: Script teks (untuk generate metadata)

    Returns:
        str: YouTube Video ID dari video yang diupload
    """
    metadata = generate_video_metadata(script)
    youtube = get_youtube_service()

    request_body = {
        "snippet": {
            "title": metadata["title"],
            "description": metadata["description"],
            "tags": metadata["tags"],
            "categoryId": "27",  # 27 = Education
            "defaultLanguage": "id",
            "defaultAudioLanguage": "id",
        },
        "status": {
            "privacyStatus": "public",     # Langsung publik
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 10,  # 10 MB per chunk
    )

    logger.info(f"🚀 Mengupload: {video_path.name}")
    logger.info(f"   Judul: {metadata['title']}")

    request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            progress = int(status.progress() * 100)
            logger.info(f"   Upload progress: {progress}%")

    video_id = response["id"]
    video_url = f"https://youtube.com/shorts/{video_id}"
    logger.info(f"✅ Video berhasil diupload! URL: {video_url}")

    return video_id


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_script = (
        "Gue pernah bokek parah di tanggal 20, padahal baru gajian tanggal 1. "
        "Semua uang habis buat bayar paylater. Ternyata ini namanya lifestyle inflation."
    )
    metadata = generate_video_metadata(test_script)
    print(f"Title: {metadata['title']}")
    print(f"Description:\n{metadata['description']}")
    print(f"Tags: {metadata['tags']}")
