"""
config.py — Konfigurasi global untuk YouTube Shorts Content Factory
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# ─── Load .env ───────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

# ─── API Keys ─────────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")

# ─── YouTube OAuth ────────────────────────────────────────────────────────────
YOUTUBE_CLIENT_SECRET_FILE: str = os.getenv(
    "YOUTUBE_CLIENT_SECRET_FILE", "credentials/client_secret.json"
)
YOUTUBE_TOKEN_FILE: str = os.getenv(
    "YOUTUBE_TOKEN_FILE", "credentials/youtube_token.json"
)
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# ─── Folder Paths ─────────────────────────────────────────────────────────────
ASSETS_DIR = BASE_DIR / "assets"
BG_VIDEO_DIR = ASSETS_DIR / "backgrounds"
FONTS_DIR = ASSETS_DIR / "fonts"
OUTPUT_DIR = BASE_DIR / "output"
AUDIO_DIR = OUTPUT_DIR / "audio"
SUBTITLE_DIR = OUTPUT_DIR / "subtitles"
VIDEO_DIR = OUTPUT_DIR / "videos"

for _d in [BG_VIDEO_DIR, FONTS_DIR, AUDIO_DIR, SUBTITLE_DIR, VIDEO_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ─── Video Spec ───────────────────────────────────────────────────────────────
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30

# ─── TTS ──────────────────────────────────────────────────────────────────────
# Pilih voice edge-tts yang natural. Cek daftar: edge-tts --list-voices | grep id-ID
TTS_VOICE = "id-ID-GadisNeural"   # Wanita, terdengar natural
TTS_RATE = "+30%"                  # Dipercepat ala brainrot (dari normal)
TTS_VOLUME = "+0%"

# ─── Font (akan auto-download via script jika belum ada) ─────────────────────
FONT_PATH = str(FONTS_DIR / "Montserrat-Bold.ttf")
FONT_FALLBACK = "Arial-Bold"       # Fallback jika font belum didownload

# ─── Subtitle Styling ────────────────────────────────────────────────────────
SUBTITLE_FONT_SIZE = 120           # Gede biar brainrot style
SUBTITLE_COLOR = "white"
SUBTITLE_STROKE_COLOR = "black"
SUBTITLE_STROKE_WIDTH = 6          # Tebal biar kebaca
SUBTITLE_Y_POSITION = 0.65        # Posisi vertikal (0=atas, 1=bawah), 65% dari atas

# ─── Background Video ─────────────────────────────────────────────────────────
BG_VIDEO_POOL_SIZE = int(os.getenv("BG_VIDEO_POOL_SIZE", "10"))
# Query yang akan di-search di YouTube — konsisten 1 tema: Minecraft Parkour
BG_VIDEO_QUERIES = [
    "minecraft parkour gameplay no commentary",
    "minecraft parkour satisfying moments",
    "minecraft parkour compilation no commentary",
    "minecraft parkour epic gameplay",
    "minecraft parkour speedrun",
]

# ─── Scheduler ────────────────────────────────────────────────────────────────
_raw_times = os.getenv("SCHEDULE_TIMES", "08:00,13:00,19:00")
SCHEDULE_TIMES = [t.strip() for t in _raw_times.split(",")]

# ─── LLM Models ───────────────────────────────────────────────────────────────
GEMINI_MODEL = "gemini-2.5-flash"          # Model terbaru Gemini (gratis)
DEEPSEEK_MODEL = "deepseek-reasoner"       # DeepSeek R1 Reasoner

# ─── Niche & Style ────────────────────────────────────────────────────────────
CONTENT_NICHE = "Edukasi Keuangan & Finansial (gaya brainrot)"
TARGET_AUDIENCE = "Gen Z dan Gen Alpha Indonesia (usia 15-27 tahun)"
STORYTELLING_STYLE = "brainrot, fast-paced, absurd, meme references, chaotic, relatable, pakai bahasa campuran Indonesia-Inggris"
VIDEO_DURATION_SECONDS = (20, 40)         # target durasi video brainrot (min, max)
