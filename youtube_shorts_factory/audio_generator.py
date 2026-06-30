"""
audio_generator.py — Fase 2: Text-to-Speech & Subtitle Generation
  - Gunakan edge-tts (Microsoft TTS, gratis)
  - Output: file .mp3 (audio) dan .vtt (subtitle dengan timestamp)
"""
import asyncio
import re
import logging
from pathlib import Path
from datetime import datetime, timedelta

import edge_tts

import config

logger = logging.getLogger(__name__)


# ─── TTS & Subtitle Generation ───────────────────────────────────────────────
async def _generate_tts_async(
    script: str, audio_path: Path, subtitle_path: Path
) -> None:
    """
    Jalankan edge-tts secara async untuk menghasilkan audio + subtitle.
    Menggunakan edge-tts 7.x API (SubMaker.feed + get_srt).
    """
    communicate = edge_tts.Communicate(
        text=script,
        voice=config.TTS_VOICE,
        rate=config.TTS_RATE,
        volume=config.TTS_VOLUME,
        boundary="WordBoundary",
    )

    # edge-tts SubMaker untuk generate subtitle (feed API 7.x)
    submaker = edge_tts.SubMaker()
    audio_bytes = b""

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_bytes += chunk["data"]
        elif chunk["type"] == "WordBoundary":
            submaker.feed(chunk)

    # Simpan audio
    audio_path.write_bytes(audio_bytes)
    logger.info(f"🎙️  Audio saved: {audio_path} ({len(audio_bytes) / 1024:.1f} KB)")

    # Dapatkan SRT mentah (word-by-word) lalu konversi ke VTT dengan pengelompokan
    raw_srt = submaker.get_srt()
    vtt_content = _srt_to_vtt_grouped(raw_srt, words_per_cue=2)  # Brainrot: per 2 kata biar cepet berganti
    subtitle_path.write_text(vtt_content, encoding="utf-8")
    logger.info(f"📝 Subtitle saved: {subtitle_path}")


def generate_audio_and_subtitle(script: str, session_id: str) -> dict:
    """
    Generate audio dan subtitle dari script teks.

    Args:
        script: Script teks yang sudah final.
        session_id: ID unik sesi (dipakai sebagai nama file).

    Returns:
        dict dengan keys:
          - 'audio_path': Path ke file .mp3
          - 'subtitle_path': Path ke file .vtt
          - 'duration': Estimasi durasi audio dalam detik
    """
    audio_path = config.AUDIO_DIR / f"{session_id}.mp3"
    subtitle_path = config.SUBTITLE_DIR / f"{session_id}.vtt"

    logger.info(f"🎙️  Generating TTS dengan voice: {config.TTS_VOICE}")
    asyncio.run(_generate_tts_async(script, audio_path, subtitle_path))

    # Hitung durasi dari file VTT
    duration = _estimate_duration_from_vtt(subtitle_path)
    logger.info(f"⏱️  Estimated duration: {duration:.1f}s")

    return {
        "audio_path": audio_path,
        "subtitle_path": subtitle_path,
        "duration": duration,
    }


# ─── Konversi SRT ke VTT dengan Pengelompokan Kata ────────────────────────────
def _srt_to_vtt_grouped(srt_content: str, words_per_cue: int = 4) -> str:
    """
    Konversi SRT word-by-word dari edge-tts ke VTT dengan pengelompokan kata.

    edge-tts 7.x menghasilkan SRT per-kata. Fungsi ini mengelompokkan
    beberapa kata menjadi satu cue subtitle agar lebih mudah dibaca.

    Args:
        srt_content: Konten SRT dari submaker.get_srt()
        words_per_cue: Jumlah kata per grup subtitle (default: 4)

    Returns:
        str: Konten VTT dengan cue yang sudah dikelompokkan
    """
    # Parse SRT blocks
    blocks = re.split(r"\n\s*\n", srt_content.strip())
    word_cues = []

    for block in blocks:
        lines = block.strip().splitlines()
        if not lines:
            continue

        # Cari baris timestamp (format SRT: 00:00:01,000 --> 00:00:02,000)
        timestamp_line = None
        text_lines = []
        for i, line in enumerate(lines):
            if "-->" in line:
                timestamp_line = line
                text_lines = lines[i + 1 :]
                break

        if not timestamp_line:
            continue

        # Parse SRT timestamp (koma sebagai desimal)
        match = re.match(
            r"(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})",
            timestamp_line,
        )
        if not match:
            continue

        start_srt = match.group(1).replace(",", ".")
        end_srt = match.group(2).replace(",", ".")
        text = " ".join(text_lines).strip()

        if text:
            word_cues.append({
                "start": _vtt_time_to_seconds(start_srt),
                "end": _vtt_time_to_seconds(end_srt),
                "text": text,
            })

    if not word_cues:
        return "WEBVTT\n\n"

    # Kelompokkan word cues
    grouped = []
    for i in range(0, len(word_cues), words_per_cue):
        group = word_cues[i : i + words_per_cue]
        start = group[0]["start"]
        end = group[-1]["end"]
        text = " ".join(c["text"] for c in group)
        grouped.append({"start": start, "end": end, "text": text})

    # Generate VTT
    lines = ["WEBVTT", ""]
    for cue in grouped:
        start_str = _seconds_to_vtt_time(cue["start"])
        end_str = _seconds_to_vtt_time(cue["end"])
        lines.append(f"{start_str} --> {end_str}")
        lines.append(cue["text"])
        lines.append("")

    return "\n".join(lines)


def _seconds_to_vtt_time(seconds: float) -> str:
    """Konversi detik (float) ke format VTT timestamp: HH:MM:SS.mmm."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


# ─── Parse VTT untuk ambil durasi & cue list ─────────────────────────────────
def _estimate_duration_from_vtt(vtt_path: Path) -> float:
    """
    Baca file VTT dan ambil waktu akhir cue terakhir sebagai durasi total.
    Return durasi dalam detik (float).
    """
    content = vtt_path.read_text(encoding="utf-8")
    # Cari semua timestamp --> format: HH:MM:SS.mmm --> HH:MM:SS.mmm
    times = re.findall(
        r"(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})", content
    )
    if not times:
        return 55.0  # fallback jika VTT kosong

    last_end = times[-1][1]
    return _vtt_time_to_seconds(last_end)


def _vtt_time_to_seconds(time_str: str) -> float:
    """Konversi string HH:MM:SS.mmm ke detik (float)."""
    h, m, rest = time_str.split(":")
    s, ms = rest.split(".")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def parse_vtt_cues(vtt_path: Path) -> list[dict]:
    """
    Parse file .vtt dan kembalikan list of cue dict:
    [{"start": float, "end": float, "text": str}, ...]
    Digunakan oleh video_maker.py untuk render subtitle.
    """
    content = vtt_path.read_text(encoding="utf-8")
    cues = []

    # Split per blok (separator: baris kosong)
    blocks = re.split(r"\n\s*\n", content)
    for block in blocks:
        lines = block.strip().splitlines()
        if not lines:
            continue

        # Cari baris timestamp
        timestamp_line = None
        text_lines = []
        for i, line in enumerate(lines):
            if "-->" in line:
                timestamp_line = line
                text_lines = lines[i + 1 :]
                break

        if not timestamp_line:
            continue

        match = re.match(
            r"(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})",
            timestamp_line,
        )
        if not match:
            continue

        start = _vtt_time_to_seconds(match.group(1))
        end = _vtt_time_to_seconds(match.group(2))
        text = " ".join(text_lines).strip()

        if text:
            cues.append({"start": start, "end": end, "text": text})

    return cues


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_script = (
        "Gue pernah bokek parah di tanggal 20, padahal baru gajian tanggal 1. "
        "Literally semua uang gue habis buat bayar paylater yang numpuk. "
        "Ngl, gue baru sadar kalau gue udah terjebak lifestyle inflation. "
        "Setiap naik gaji, pengeluaran gue ikut naik. "
        "Sampai akhirnya gue coba satu trik simpel: bayar diri sendiri dulu. "
        "Langsung transfer 20% gaji ke rekening tabungan sebelum beli apapun. "
        "Tiga bulan kemudian? Gue punya dana darurat pertama dalam hidup gue. "
        "Fr, cobain deh. Save video ini biar lu inget."
    )
    result = generate_audio_and_subtitle(test_script, "test_session_001")
    print(f"\nAudio: {result['audio_path']}")
    print(f"Subtitle: {result['subtitle_path']}")
    print(f"Duration: {result['duration']:.1f}s")
    cues = parse_vtt_cues(result["subtitle_path"])
    print(f"Total cues: {len(cues)}")
    for c in cues[:5]:
        print(f"  [{c['start']:.2f}s -> {c['end']:.2f}s] {c['text']}")
