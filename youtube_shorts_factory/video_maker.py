"""
video_maker.py — Fase 4: Video Assembly
  - Gabungkan background video + voiceover audio
  - Render subtitle dinamis (sinkron waktu) di atas video
  - Export ke .mp4 resolusi 1080x1920 (9:16 YouTube Shorts)
"""
import logging
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import (
    VideoFileClip,
    AudioFileClip,
    ImageClip,
    CompositeVideoClip,
    concatenate_videoclips,
)

import config
from audio_generator import parse_vtt_cues
from asset_manager import prepare_background_clip

logger = logging.getLogger(__name__)


# ─── Download Font jika belum ada ─────────────────────────────────────────────
FONT_URLS = [
    # Noto Sans Display - optimized untuk digital/layar (prioritas utama)
    "https://raw.githubusercontent.com/notofonts/noto-fonts/main/hinted/ttf/NotoSansDisplay/NotoSansDisplay-Bold.ttf",
    # Noto Sans - fallback utama
    "https://raw.githubusercontent.com/notofonts/noto-fonts/main/hinted/ttf/NotoSans/NotoSans-Bold.ttf",
    # Noto Sans dari repo lama googlefonts
    "https://raw.githubusercontent.com/googlefonts/noto-fonts/main/hinted/ttf/NotoSans/NotoSans-Bold.ttf",
]


def ensure_font() -> str:
    """Download Montserrat-Bold.ttf jika belum ada. Return path ke font."""
    font_path = Path(config.FONT_PATH)
    if font_path.exists():
        return str(font_path)

    logger.info(f"📥 Downloading font: {font_path.name}")
    for url in FONT_URLS:
        try:
            logger.info(f"  Mencoba: {url}")
            urllib.request.urlretrieve(url, font_path)
            if font_path.exists() and font_path.stat().st_size > 1000:
                logger.info(f"✅ Font disimpan: {font_path}")
                return str(font_path)
        except Exception as e:
            logger.warning(f"  Gagal: {e}")
            continue
    logger.warning(f"⚠️  Semua URL font gagal. Gunakan fallback: {config.FONT_FALLBACK}")
    return config.FONT_FALLBACK


# ─── Render Satu Frame Subtitle ───────────────────────────────────────────────
def _make_subtitle_clip(
    text: str,
    duration: float,
    font_path: str,
    video_width: int,
    video_height: int,
) -> ImageClip:
    """
    Buat ImageClip berisi teks subtitle dengan styling premium:
    - Font bold besar
    - Warna putih dengan stroke/outline hitam
    - Background semi-transparan ringan
    """
    font_size = config.SUBTITLE_FONT_SIZE
    stroke_w = config.SUBTITLE_STROKE_WIDTH
    padding = 30
    max_text_width = video_width - (padding * 4)

    # Buat font PIL
    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        font = ImageFont.load_default()

    # Word-wrap: pecah teks jadi baris
    lines = _wrap_text(text, font, max_text_width)

    # Ukur total tinggi teks
    dummy_img = Image.new("RGBA", (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)
    line_height = font_size + 10
    total_text_height = line_height * len(lines) + padding * 2

    # Tinggi & lebar canvas subtitle
    canvas_w = video_width
    canvas_h = total_text_height + stroke_w * 2

    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    y_cursor = padding
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (canvas_w - text_w) // 2

        # Stroke (outline hitam) — gambar di 8 arah
        for dx in range(-stroke_w, stroke_w + 1):
            for dy in range(-stroke_w, stroke_w + 1):
                if dx == 0 and dy == 0:
                    continue
                draw.text(
                    (x + dx, y_cursor + dy),
                    line,
                    font=font,
                    fill=(0, 0, 0, 240),
                )

        # Teks utama (putih)
        draw.text((x, y_cursor), line, font=font, fill=(255, 255, 255, 255))
        y_cursor += line_height

    # Tambah drop shadow halus
    shadow_img = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_img)
    # (sudah tercover oleh stroke, skip extra shadow)

    # Posisi Y di canvas video
    y_pos = int(video_height * config.SUBTITLE_Y_POSITION - canvas_h / 2)
    y_pos = max(0, min(y_pos, video_height - canvas_h))

    img_array = np.array(img)
    clip = (
        ImageClip(img_array, is_mask=False)
        .with_duration(duration)
        .with_position(("center", y_pos))
    )
    return clip


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Pecah teks panjang menjadi baris-baris yang muat dalam max_width."""
    words = text.split()
    lines = []
    current_line = []

    dummy = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy)

    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]

    if current_line:
        lines.append(" ".join(current_line))

    return lines if lines else [text]


# ─── Pipeline Utama Fase 4 ────────────────────────────────────────────────────
def assemble_video(
    audio_path: Path,
    subtitle_path: Path,
    session_id: str,
) -> Path:
    """
    Rakit video final:
    1. Load audio voiceover (dapat durasi aktual)
    2. Ambil background clip dari pool
    3. Render semua subtitle cues sebagai ImageClip
    4. Composite & export .mp4

    Returns: Path ke file video final .mp4
    """
    output_path = config.VIDEO_DIR / f"{session_id}.mp4"
    font_path = ensure_font()

    # ── 1. Load audio ──────────────────────────────────────────────────────────
    logger.info(f"🎵 Loading audio: {audio_path}")
    audio_clip = AudioFileClip(str(audio_path))
    duration = audio_clip.duration
    logger.info(f"⏱️  Durasi audio aktual: {duration:.2f}s")

    # ── 2. Background video ────────────────────────────────────────────────────
    logger.info("🎬 Menyiapkan background clip...")
    bg_clip = prepare_background_clip(target_duration=duration)

    # Pastikan resolusi benar
    bg_clip = bg_clip.resized((config.VIDEO_WIDTH, config.VIDEO_HEIGHT))
    bg_clip = bg_clip.with_audio(audio_clip)

    # ── 3. Subtitle clips ──────────────────────────────────────────────────────
    logger.info("📝 Rendering subtitle...")
    cues = parse_vtt_cues(subtitle_path)
    subtitle_clips = []
    for cue in cues:
        start = cue["start"]
        end = min(cue["end"], duration)
        cue_duration = end - start
        if cue_duration <= 0:
            continue

        sub_clip = _make_subtitle_clip(
            text=cue["text"],
            duration=cue_duration,
            font_path=font_path,
            video_width=config.VIDEO_WIDTH,
            video_height=config.VIDEO_HEIGHT,
        ).with_start(start)

        subtitle_clips.append(sub_clip)

    logger.info(f"✅ {len(subtitle_clips)} subtitle cues di-render")

    # ── 4. Composite & Export ──────────────────────────────────────────────────
    logger.info("🎞️  Compositing video...")
    final_video = CompositeVideoClip(
        [bg_clip] + subtitle_clips,
        size=(config.VIDEO_WIDTH, config.VIDEO_HEIGHT),
    )

    logger.info(f"💾 Exporting ke: {output_path}")
    final_video.write_videofile(
        str(output_path),
        fps=config.VIDEO_FPS,
        codec="libx264",
        audio_codec="aac",
        bitrate="4000k",
        audio_bitrate="192k",
        threads=4,
        logger=None,   # Suppress moviepy verbose output
    )

    # Cleanup
    audio_clip.close()
    bg_clip.close()
    final_video.close()

    logger.info(f"✅ Video final: {output_path}")
    return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Test dengan file dummy — pastikan ada file .mp3 dan .vtt di output/
    from pathlib import Path

    test_audio = config.AUDIO_DIR / "test_session_001.mp3"
    test_subtitle = config.SUBTITLE_DIR / "test_session_001.vtt"

    if test_audio.exists() and test_subtitle.exists():
        result = assemble_video(test_audio, test_subtitle, "test_session_001")
        print(f"Video selesai: {result}")
    else:
        print("Jalankan dulu: python audio_generator.py")
