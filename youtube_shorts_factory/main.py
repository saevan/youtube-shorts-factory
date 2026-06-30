"""
main.py — Fase 6: Pipeline Utama & Scheduler
  - Jalankan semua fase (1-5) dalam satu pipeline
  - Schedule otomatis 3x sehari (default: 08:00, 13:00, 19:00 WIB)
"""
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path

import schedule

import config
from llm_engine import generate_final_script
from audio_generator import generate_audio_and_subtitle
from asset_manager import download_background_videos
from video_maker import assemble_video
# from uploader import upload_video  # OAuth — diganti Selenium
from selenium_uploader import upload_video_pipeline

# ─── Logging Setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(config.BASE_DIR / "pipeline.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")


# ─── Full Pipeline ─────────────────────────────────────────────────────────────
def run_pipeline() -> None:
    """
    Jalankan satu siklus penuh pembuatan & upload YouTube Shorts.
    Fase 1 → 2 → 3 → 4 → 5
    """
    session_id = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    logger.info("=" * 60)
    logger.info(f"🚀 MULAI PIPELINE — Session: {session_id}")
    logger.info("=" * 60)

    try:
        # ── FASE 1: Script Generation ──────────────────────────────────────────
        logger.info("\n📌 [FASE 1] Ideation & Scripting...")
        script = generate_final_script()
        if not script or len(script.split()) < 50:
            raise ValueError(f"Script terlalu pendek atau kosong: '{script[:100]}'")
        logger.info(f"   Script ({len(script.split())} kata) siap.\n")

        # ── FASE 2: Audio & Subtitle ───────────────────────────────────────────
        logger.info("📌 [FASE 2] Audio & Subtitle Generation...")
        audio_result = generate_audio_and_subtitle(script, session_id)
        audio_path: Path = audio_result["audio_path"]
        subtitle_path: Path = audio_result["subtitle_path"]
        duration: float = audio_result["duration"]
        logger.info(f"   Audio: {audio_path.name} ({duration:.1f}s)\n")

        if duration < 20 or duration > 90:
            logger.warning(
                f"⚠️  Durasi audio {duration:.1f}s di luar range ideal (20-90s). "
                "Lanjutkan tetap..."
            )

        # ── FASE 3: Background Video ───────────────────────────────────────────
        logger.info("📌 [FASE 3] Background Video Pool...")
        download_background_videos()
        logger.info("   Pool background video siap.\n")

        # ── FASE 4: Video Assembly ─────────────────────────────────────────────
        logger.info("📌 [FASE 4] Video Assembly...")
        video_path = assemble_video(audio_path, subtitle_path, session_id)
        logger.info(f"   Video: {video_path.name}\n")

        # ── FASE 5: Upload ke YouTube via Selenium ─────────────────────────────
        logger.info("📌 [FASE 5] Upload ke YouTube (Selenium)...")
        upload_result = upload_video_pipeline(video_path, script)
        logger.info(f"   ✅ SUKSES! {upload_result}\n")

        logger.info("=" * 60)
        logger.info(f"🎉 PIPELINE SELESAI — {session_id}")
        logger.info(f"   Upload: {upload_result}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ PIPELINE GAGAL pada session {session_id}: {e}", exc_info=True)
        logger.info("=" * 60)
        logger.info("⚠️  Pipeline gagal. Akan dicoba lagi pada jadwal berikutnya.")
        logger.info("=" * 60)


# ─── Scheduler ────────────────────────────────────────────────────────────────
def start_scheduler() -> None:
    """
    Jadwalkan pipeline untuk berjalan sesuai SCHEDULE_TIMES di config.
    Default: 08:00, 13:00, 19:00 WIB.
    """
    logger.info("⏰ Memulai Scheduler YouTube Shorts Factory")
    logger.info(f"   Jadwal upload: {config.SCHEDULE_TIMES}")
    logger.info(f"   Niche: {config.CONTENT_NICHE}")
    logger.info(f"   Target audiens: {config.TARGET_AUDIENCE}")
    logger.info("   Tekan Ctrl+C untuk berhenti.\n")

    for time_str in config.SCHEDULE_TIMES:
        schedule.every().day.at(time_str).do(run_pipeline)
        logger.info(f"   ✅ Terjadwal: setiap hari jam {time_str}")

    logger.info("")

    # Run loop
    while True:
        next_run = schedule.next_run()
        logger.info(
            f"⏳ Menunggu... Jadwal berikutnya: {next_run.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        try:
            # Tunggu maksimal 60 menit, cek setiap menit
            for _ in range(60):
                schedule.run_pending()
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("\n🛑 Scheduler dihentikan oleh user (Ctrl+C).")
            break


# ─── Entry Point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--run-now":
        # Mode manual: langsung jalankan pipeline tanpa scheduler
        logger.info("🏃 Mode manual: run_now")
        run_pipeline()
    else:
        # Mode default: jalankan scheduler
        start_scheduler()
