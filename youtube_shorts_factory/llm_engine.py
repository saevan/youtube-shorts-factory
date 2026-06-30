"""
llm_engine.py — Fase 1: Ideation & Scripting (Dual LLM System)
  1. Gemini  → generate ide cerita finansial Gen Z/Alpha
  2. DeepSeek → validasi, haluskan gaya bahasa, pastikan durasi 45-60 detik
"""
import re
import logging
from google import genai
from google.genai import types
from openai import OpenAI

import config

logger = logging.getLogger(__name__)

# ─── Inisialisasi klien ───────────────────────────────────────────────────────
_gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)

_deepseek_client = OpenAI(
    api_key=config.DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com",
)


# ─── Fase 1A: Gemini — Generate Ide & Draft Script ───────────────────────────
def generate_story_idea() -> str:
    """
    Panggil Gemini untuk membuat ide cerita + draft script finansial.
    Return: string berisi draft script mentah dari Gemini.
    """
    prompt = f"""
Kamu adalah kreator konten YouTube Shorts spesialis {config.CONTENT_NICHE}.
Target audiensmu adalah {config.TARGET_AUDIENCE}.
Gaya storytelling: {config.STORYTELLING_STYLE}.

Tugasmu — BUAT SCRIPT GAYA BRAINROT:

1. Pilih SATU topik finansial yang relatable dan absurd untuk anak muda.
   Contoh: jebakan paylater, FOMO investasi, boncos gara-gara lifestyle inflation, dll.

2. Tulis SCRIPT pendek bergaya storytelling orang pertama ("gue"/"aku").
   GAYA BRAINROT = super santai, meme references, absurd, chaotic, pake bahasa campuran Indonesia-Inggris ga karuan.
   Contoh vibe: "bestie lo kira gue baik? literally gue punya paylater 5 bro. satunya buat nasi padang."
   Pake: literally, ngl, fr, bestie, bro, vibes, ngos-ngosan, kebangun, dll.

3. Script HARUS 60-100 kata (cocok buat 20-40 detik dengan TTS yang dipercepat).

4. STRUKTUR CEPAT:
   - HOOK (3 detik pertama): Langsung ke inti, kocak, bikin ngakak
   - STRUGGLE: Kenapa situasi ini relatable/bikin stres
   - PLOT TWIST: Pelajaran finansial yang sadar
   - CTA: "save this before lo nyesel" / "follow for more financial trauma"

5. JANGAN pake label [Hook] dll. Tulis script langsung, murni teks.
6. JANGAN terlalu serius. Ini brainrot, bukan pidato.

Tulis HANYA script-nya. Tidak perlu penjelasan lain.
"""
    logger.info("🤖 Gemini: Generating story idea...")
    response = _gemini_client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=prompt,
    )
    draft = response.text.strip()
    logger.info(f"✅ Gemini draft ({len(draft.split())} words):\n{draft[:200]}...")
    return draft


# ─── Fase 1B: DeepSeek — Validasi, Perbaiki & Finalisasi ─────────────────────
def refine_script_with_deepseek(draft_script: str) -> str:
    """
    Kirim draft dari Gemini ke DeepSeek Reasoner untuk:
    - Validasi flow cerita
    - Perbaiki gaya bahasa agar lebih natural Gen Z/Alpha Indonesia
    - Pastikan panjang script cocok untuk 45-60 detik
    Return: script final yang sudah bersih.
    """
    system_prompt = f"""
Kamu adalah script editor untuk YouTube Shorts brainrot {config.CONTENT_NICHE}.
Expert dalam gaya bahasa Gen Z & Alpha yang absurd, chaotic, dan engaging.
Tugasmu: perbaiki draft script biar lebih brainrot, lebih cepat, dan lebih relatable.
"""

    user_prompt = f"""
Berikut adalah DRAFT SCRIPT yang perlu kamu edit:

---
{draft_script}
---

TUGAS KAMU — EDIT JADI BRAINROT:

1. BUAT LEBIH CEPAT: Target 60-100 kata. Potong bagian yang lambat/ga penting.
2. GAYA BRAINROT: Pake bahasa campuran Indonesia-Inggris yang absurd.
   Wajib pake: "literally", "ngl", "fr", "bestie", "bro", "vibes", "ngos-ngosan".
   Boleh pake: "be like", "no cap", "for real", "stop it".
3. HOOK: Harus langsung kocak di 3 kata pertama. Contoh: "BESTIE GUE BONCOS."
4. PESAN: Tetap ada pelajaran finansial di akhir, tapi disamperin cara kocak.
5. CTA: Akhiri absurd. Contoh: "save this before lo jadi miskin jua" / "follow biar lo sadar"

OUTPUT:
- Hanya script final. Tanpa label, tanpa markdown, tanpa penjelasan.
- Murni teks doang.
"""

    logger.info("🧠 DeepSeek: Refining script...")
    response = _deepseek_client.chat.completions.create(
        model=config.DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=2048,
        temperature=1.0,  # DeepSeek Reasoner hanya support temperature=1
    )

    # DeepSeek Reasoner mungkin menghasilkan <think>...</think> block — kita strip
    raw_output = response.choices[0].message.content.strip()
    final_script = _strip_think_tags(raw_output)

    word_count = len(final_script.split())
    logger.info(f"✅ DeepSeek refined script ({word_count} words):\n{final_script[:200]}...")
    return final_script


def _strip_think_tags(text: str) -> str:
    """Hapus <think>...</think> block yang kadang muncul di output DeepSeek Reasoner."""
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return cleaned.strip()


# ─── Pipeline Utama Fase 1 ────────────────────────────────────────────────────
def generate_final_script() -> str:
    """
    Jalankan full pipeline Fase 1:
    Gemini (ideation) → DeepSeek (refinement) → script final
    """
    draft = generate_story_idea()
    final = refine_script_with_deepseek(draft)
    return final


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    script = generate_final_script()
    print("\n" + "=" * 60)
    print("FINAL SCRIPT:")
    print("=" * 60)
    print(script)
    print(f"\nWord count: {len(script.split())}")
