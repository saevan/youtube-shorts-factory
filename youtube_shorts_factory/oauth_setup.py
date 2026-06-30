"""
Script OAuth untuk mendapatkan YouTube token.
Jalankan: python oauth_setup.py
"""
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
from pathlib import Path

# Konfigurasi
SECRET_PATH = Path("credentials/client_secret.json")
TOKEN_PATH = Path("credentials/youtube_token.json")
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

print("=" * 60)
print("  YOUTUBE OAUTH SETUP")
print("=" * 60)
print()

if not SECRET_PATH.exists():
    print(f"\u274c File {SECRET_PATH} tidak ditemukan!")
    print("   Download dulu dari Google Cloud Console")
    sys.exit(1)

print(f"\u2705 client_secret.json ditemukan")
print(f"\U0001f4c1 Token akan disimpan di: {TOKEN_PATH}")
print()

# Hapus token lama kalau ada
if TOKEN_PATH.exists():
    print("\U0001f5d1\ufe0f  Token lama ditemukan, akan dihapus...")
    TOKEN_PATH.unlink()

print("\U0001f510 Memulai OAuth flow...")
print()
print("=" * 60)
print("  Browser akan terbuka secara otomatis.")
print("  Jika tidak, buka link yang tercetak di atas.")
print("=" * 60)
print()

flow = InstalledAppFlow.from_client_secrets_file(str(SECRET_PATH), SCOPES)

# run_local_server akan membuka browser dan menunggu callback
creds = flow.run_local_server(
    port=8080,
    authorization_prompt_message="",
    success_message="Auth berhasil! Silakan tutup browser dan kembali ke terminal.",
    open_browser=True
)

# Simpan token
TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
with open(TOKEN_PATH, "wb") as f:
    pickle.dump(creds, f)

print()
print("=" * 60)
print("  \u2705 OAUTH BERHASIL!")
print(f"  \U0001f4c1 Token tersimpan di: {TOKEN_PATH}")
print("=" * 60)
