"""
asset_manager.py — Fase 3: Background Video Management
  - Download video Creative Commons dari YouTube menggunakan yt-dlp
  - Trim / loop video sesuai durasi audio
  - Kelola pool video background lokal
"""
import random
import logging
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
from moviepy import VideoFileClip, concatenate_videoclips

import config

logger = logging.getLogger(__name__)


# ─── Download Background Video ────────────────────────────────────────────────
def download_background_videos(max_videos: int = None) -> list[Path]:
    """
    Download video background dari YouTube ke BG_VIDEO_DIR.
    Jika pool sudah cukup (>= max_videos), skip download.

    Returns: list dari Path video yang tersedia di pool.
    """
    if max_videos is None:
        max_videos = config.BG_VIDEO_POOL_SIZE

    existing = list(config.BG_VIDEO_DIR.glob("*.mp4"))
    if len(existing) >= max_videos:
        logger.info(f"📦 Pool sudah punya {len(existing)} video. Skip download.")
        return existing

    needed = max_videos - len(existing)
    logger.info(f"⬇️  Butuh {needed} video lagi. Mulai download...")

    query = random.choice(config.BG_VIDEO_QUERIES)
    logger.info(f"🔍 Query: '{query}'")

    # Dapatkan path ffmpeg dari imageio-ffmpeg (bundled)
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

    # yt-dlp command
    yt_dlp_cmd = [sys.executable, "-m", "yt_dlp"]
    cmd = yt_dlp_cmd + [
        f"ytsearch{needed}:{query}",
        "--format", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
        "--output", str(config.BG_VIDEO_DIR / "%(id)s.%(ext)s"),
        "--ffmpeg-location", str(ffmpeg_path),
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        "--merge-output-format", "mp4",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            logger.warning(f"⚠️  yt-dlp warning: {result.stderr[:500]}")
            # Fallback: coba lagi tanpa filter CC (yang mungkin terlalu strict)
            if "requested format not available" in result.stderr.lower() or not list(config.BG_VIDEO_DIR.glob("*.mp4")):
                logger.info("🔄 Mencoba fallback download tanpa filter...")
                _try_download_no_filter(query, needed, ffmpeg_path)
    except subprocess.TimeoutExpired:
        logger.error("❌ yt-dlp timeout setelah 10 menit")
    except FileNotFoundError:
        logger.error("❌ yt-dlp tidak ditemukan. Pastikan sudah install: pip install yt-dlp")

    all_videos = list(config.BG_VIDEO_DIR.glob("*.mp4"))
    logger.info(f"✅ Pool sekarang punya {len(all_videos)} video background")
    return all_videos


def _try_download_no_filter(query: str, count: int, ffmpeg_path: str) -> None:
    """Fallback: download tanpa filter Creative Commons."""
    logger.warning("⚠️  Fallback: download tanpa filter CC license")
    yt_dlp_cmd = [sys.executable, "-m", "yt_dlp"]
    cmd = yt_dlp_cmd + [
        f"ytsearch{count}:{query}",
        "--format", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
        "--output", str(config.BG_VIDEO_DIR / "%(id)s.%(ext)s"),
        "--ffmpeg-location", str(ffmpeg_path),
        "--no-playlist",
        "--quiet",
        "--merge-output-format", "mp4",
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=600)


# ─── Trim/Loop Background Video ──────────────────────────────────────────────
def prepare_background_clip(target_duration: float) -> VideoFileClip:
    """
    Pilih video background secara acak dari pool, lalu:
    - Crop ke 9:16 (potong tengah)
    - Loop jika video lebih pendek dari target_duration
    - Trim ke tepat target_duration

    Args:
        target_duration: Durasi target dalam detik (dari audio).

    Returns:
        MoviePy VideoFileClip yang sudah siap (tanpa audio asli).
    """
    pool = list(config.BG_VIDEO_DIR.glob("*.mp4"))
    if not pool:
        raise FileNotFoundError(
            "❌ Tidak ada video background di pool! "
            "Jalankan download_background_videos() terlebih dahulu."
        )

    chosen = random.choice(pool)
    logger.info(f"🎬 Background video dipilih: {chosen.name}")

    clip = VideoFileClip(str(chosen))

    # ── Crop ke aspek 9:16 (portrait) ──
    clip = _crop_to_9_16(clip)

    # ── Loop jika video lebih pendek dari target ──
    if clip.duration < target_duration:
        loops_needed = int(target_duration / clip.duration) + 2
        clip = concatenate_videoclips([clip] * loops_needed)
        logger.info(f"🔁 Video di-loop {loops_needed}x karena terlalu pendek")

    # ── Trim ke durasi tepat ──
    start_offset = random.uniform(0, max(0, clip.duration - target_duration - 1))
    clip = clip.subclipped(start_offset, start_offset + target_duration)

    # Hapus audio asli background
    clip = clip.without_audio()

    # Resize ke resolusi target
    clip = clip.resized((config.VIDEO_WIDTH, config.VIDEO_HEIGHT))

    logger.info(
        f"✅ Background clip siap: {clip.duration:.1f}s @ {clip.size[0]}x{clip.size[1]}"
    )
    return clip


def _crop_to_9_16(clip: VideoFileClip) -> VideoFileClip:
    """
    Crop video ke aspek rasio 9:16.
    Jika video landscape (16:9), crop dari tengah.
    Jika video sudah portrait, kembalikan langsung.
    """
    w, h = clip.size
    target_ratio = 9 / 16

    current_ratio = w / h
    if current_ratio > target_ratio:
        # Video terlalu lebar → crop kiri-kanan
        new_w = int(h * target_ratio)
        x_center = w / 2
        clip = clip.cropped(
            x1=x_center - new_w / 2,
            x2=x_center + new_w / 2,
            y1=0,
            y2=h,
        )
    elif current_ratio < target_ratio:
        # Video terlalu tinggi → crop atas-bawah
        new_h = int(w / target_ratio)
        y_center = h / 2
        clip = clip.cropped(
            x1=0,
            x2=w,
            y1=y_center - new_h / 2,
            y2=y_center + new_h / 2,
        )
    return clip


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    videos = download_background_videos(max_videos=3)
    print(f"\nPool: {[v.name for v in videos]}")
    if videos:
        clip = prepare_background_clip(target_duration=55.0)
        print(f"Clip duration: {clip.duration:.1f}s, size: {clip.size}")
        clip.close()
