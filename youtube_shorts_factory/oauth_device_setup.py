"""
OAuth Device Flow - Tidak perlu setup consent screen yang ribet.
Cocok untuk testing apps yang belum diverifikasi.
"""
import sys
import os
import json
import time
import pickle
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

import requests

# Konfigurasi
SECRET_PATH = Path("credentials/client_secret.json")
TOKEN_PATH = Path("credentials/youtube_token.json")
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

print("=" * 60)
print("  YOUTUBE OAUTH - DEVICE FLOW")
print("=" * 60)
print()

if not SECRET_PATH.exists():
    print("File client_secret.json tidak ditemukan!")
    sys.exit(1)

# Load client config — support Web ("web") dan Desktop ("installed")
with open(SECRET_PATH) as f:
    config = json.load(f)
if "web" in config:
    client_id = config["web"]["client_id"]
    client_secret = config["web"]["client_secret"]
    print("Tipe: Web application")
elif "installed" in config:
    client_id = config["installed"]["client_id"]
    client_secret = config["installed"]["client_secret"]
    print("Tipe: Desktop app")
else:
    print("Format client_secret.json tidak dikenal!")
    print("Isi file: " + json.dumps(config, indent=2)[:200])
    sys.exit(1)

print("Client ID: " + client_id[:30] + "...")
print()

# Step 1: Dapatkan device code
print("Meminta device code...")
resp = requests.post("https://oauth2.googleapis.com/device/code", data={
    "client_id": client_id,
    "scope": " ".join(SCOPES),
})
if resp.status_code != 200:
    print("Gagal: " + resp.text)
    sys.exit(1)

data = resp.json()
device_code = data["device_code"]
user_code = data["user_code"]
verification_url = data["verification_url"]
interval = data.get("interval", 5)

print()
print("=" * 60)
print("  LANGKAH 1: Buka link di browser Anda")
print("  " + verification_url)
print()
print("  Masukkan kode: " + user_code)
print("=" * 60)
print()

# Buka browser otomatis
try:
    import webbrowser
    webbrowser.open(verification_url)
    print("Browser otomatis terbuka...")
except Exception:
    print("Browser tidak bisa dibuka otomatis.")
    print("Silakan buka manual: " + verification_url)

print()
print("Masukkan kode: " + user_code)
print("Kemudian klik 'Continue' dan berikan izin akses YouTube.")
print()
print("Menunggu Anda menyelesaikan di browser...")

# Step 2: Polling token
token_data = None
for attempt in range(60):
    time.sleep(interval)
    
    resp = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": client_id,
        "client_secret": client_secret,
        "device_code": device_code,
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
    })
    
    result = resp.json()
    
    if resp.status_code == 200 and "access_token" in result:
        token_data = result
        break
    elif result.get("error") == "authorization_pending":
        continue
    elif result.get("error") == "slow_down":
        interval += 5
        continue
    elif result.get("error") == "access_denied":
        print()
        print("Akses ditolak oleh user.")
        sys.exit(1)
    elif result.get("error") == "expired_token":
        print()
        print("Kode kadaluarsa. Silakan jalankan ulang.")
        sys.exit(1)
    
    if attempt % 6 == 0:
        print(".", end="", flush=True)

print()

if not token_data:
    print()
    print("Timeout menunggu autentikasi. Jalankan ulang.")
    sys.exit(1)

# Step 3: Simpan token sebagai pickle untuk kompatibilitas dengan uploader.py
from google.oauth2.credentials import Credentials

creds = Credentials(
    token=token_data["access_token"],
    refresh_token=token_data.get("refresh_token"),
    token_uri="https://oauth2.googleapis.com/token",
    client_id=client_id,
    client_secret=client_secret,
    scopes=SCOPES,
)

TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
with open(TOKEN_PATH, "wb") as f:
    pickle.dump(creds, f)

print()
print("=" * 60)
print("  OAUTH BERHASIL!")
print("  Token tersimpan: " + str(TOKEN_PATH))
print()
if token_data.get("refresh_token"):
    print("  Refresh token tersedia - token bisa diperbarui otomatis")
else:
    print("  Refresh token TIDAK tersedia")
    print("  Token akan kadaluarsa dalam 1 jam")
print("=" * 60)
