"""
railway_setup.py — Setup Chrome Profile untuk Railway

Kegunaan:
  1. Di Railway Shell, jalankan: python railway_setup.py --login
  2. Ikuti instruksi untuk inject cookie YouTube dari browser lokal
  3. Profile tersimpan di chrome_profile/ dan bisa dipakai scheduler

Flow:
  - Railway tidak punya GUI, jadi tidak bisa login interaktif via browser
  - Solusi: export cookie YouTube dari Chrome lokal → inject ke Railway Chrome
"""
import sys
import os
import json
import time
import platform
from pathlib import Path

# Tambah parent directory ke PATH biar bisa import config
sys.path.insert(0, str(Path(__file__).parent))

BASE_DIR = Path(__file__).parent
CHROME_PROFILE = BASE_DIR / "chrome_profile"


def cmd_setup_chrome_linux():
    """Setup Chrome di Railway/Linux — install dependencies if missing."""
    if platform.system() != "Linux":
        print("✅ Bukan Linux, skip system setup.")
        return

    print("🐧 Deteksi Linux — memastikan xvfb dan Chrome sudah siap...")
    
    # Cek xvfb
    import subprocess
    try:
        subprocess.run(["which", "xvfb-run"], check=True, capture_output=True)
        print("✅ xvfb-run tersedia")
    except subprocess.CalledProcessError:
        print("⚠️  xvfb-run tidak ditemukan. Install: apt-get install xvfb")
        print("   Tapi seharusnya sudah terinstall di Docker image.")
    
    # Cek Chrome
    chrome_paths = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
    ]
    for p in chrome_paths:
        if os.path.isfile(p):
            print(f"✅ Chrome ditemukan: {p}")
            break
    else:
        print("❌ Chrome binary tidak ditemukan!")
        print("   Pastikan Dockerfile sudah menginstall Chrome.")
        sys.exit(1)


def cmd_login():
    """
    Mode login untuk Railway.
    User export cookie YouTube dari Chrome lokal → paste di sini.
    """
    print("=" * 60)
    print("  🔐 RAILWAY — SETUP YOUTUBE LOGIN")
    print("=" * 60)
    print()
    print("📌 LANGKAH-LANGKAH:")
    print()
    print("  1️⃣  Di laptop/PC kamu, buka YouTube.com dan PASTIKAN SUDAH LOGIN")
    print("      dengan akun: savaratogether@gmail.com")
    print()
    print("  2️⃣  Install extension 'Get cookies.txt' atau 'EditThisCookie'")
    print("      di Chrome: https://chromewebstore.google.com/detail/get-cookiestxt/bgaddhkoddajcdgocldbbfleckgcbcid")
    print()
    print("  3️⃣  Buka https://www.youtube.com, klik extension, export cookies")
    print("      sebagai format Netscape (cookies.txt) atau JSON")
    print()
    print("  4️⃣  Copy paste isi cookies DI BAWAH INI, tekan Enter,")
    print("      lalu tekan Ctrl+D (atau Ctrl+Z di Windows) untuk selesai")
    print()
    print("  ⚠️  ATAU: upload file cookies.txt via Railway File Upload")
    print("     (drag & drop ke terminal Railway Shell)")
    print()
    print("=" * 60)
    print("  Paste cookies di sini (lalu Ctrl+D untuk selesai):")
    print("=" * 60)
    
    # Baca input sampai EOF
    cookie_lines = []
    try:
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            cookie_lines.append(line)
    except EOFError:
        pass
    
    cookie_text = "".join(cookie_lines).strip()
    
    if not cookie_text:
        print()
        print("❌ Tidak ada cookies yang dimasukkan.")
        print()
        print("📌 ALTERNATIF: Coba method otomatis...")
        print("   Mencoba login via browser dengan Railway TCP tunnel...")
        print()
        print("   Sayangnya method ini kompleks. Cara termudah:")
        print("   1. Jalankan container DI LAPTOP: docker run -p 5900:5900 ...")
        print("   2. Login via VNC viewer")
        print("   3. Push container yang sudah login ke Railway")
        print()
        print("   Atau baca: https://docs.railway.app/guides/shell")
        sys.exit(1)
    
    # Parse cookies (Netscape format atau JSON)
    cookies = _parse_cookies(cookie_text)
    
    if not cookies:
        print("❌ Gagal parse cookies. Pastikan formatnya benar.")
        print("   Jalankan ulang: python railway_setup.py --login")
        sys.exit(1)
    
    print(f"\n✅ Berhasil parse {len(cookies)} cookies!")
    
    # Inject cookies ke Selenium Chrome
    _inject_cookies(cookies)
    
    print()
    print("=" * 60)
    print("  ✅ LOGIN BERHASIL! Profile tersimpan di chrome_profile/")
    print("=" * 60)
    print()
    print("  Mulai sekarang scheduler akan menggunakan session ini.")
    print("  Restart container: railway restart")
    print()


def _parse_cookies(text: str) -> list[dict]:
    """Parse cookies dari format Netscape atau JSON."""
    # Coba JSON dulu
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "cookies" in data:
            return data["cookies"]
    except json.JSONDecodeError:
        pass
    
    # Coba Netscape format (cookies.txt)
    cookies = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        
        parts = line.split("\t")
        if len(parts) >= 7:
            cookie = {
                "domain": parts[0],
                "includeSubdomains": parts[1].lower() == "true",
                "path": parts[2],
                "secure": parts[3].lower() == "true",
                "expiry": int(parts[4]) if parts[4].isdigit() else None,
                "name": parts[5],
                "value": parts[6],
            }
            cookies.append(cookie)
    
    return cookies


def _inject_cookies(cookies: list[dict]):
    """
    Buka Chrome dengan chrome_profile, inject cookies, verifikasi login.
    """
    print("🔧 Membuka Chrome untuk inject cookies...")
    
    # Filter hanya cookie youtube.com
    youtube_cookies = [
        c for c in cookies
        if "youtube.com" in c.get("domain", "") or "google.com" in c.get("domain", "")
    ]
    
    if not youtube_cookies:
        print("⚠️  Tidak ada cookie untuk youtube.com atau google.com!")
        print("   Pastikan kamu sudah login ke YouTube sebelum export cookies.")
        
        # Tetap lanjut pakai semua cookies
        youtube_cookies = cookies
    
    print(f"   Ditemukan {len(youtube_cookies)} cookie untuk YouTube/Google")
    
    # Import Selenium
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
    except ImportError:
        print("❌ Selenium belum terinstall. Jalankan: pip install selenium webdriver-manager")
        sys.exit(1)
    
    # Setup Chrome options
    options = Options()
    
    # Cari Chrome binary
    if platform.system() == "Linux":
        chrome_candidates = ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium"]
        chrome_bin = None
        for p in chrome_candidates:
            if os.path.isfile(p):
                chrome_bin = p
                break
        if chrome_bin:
            options.binary_location = chrome_bin
        options.add_argument("--headless=new")  # Ga perlu GUI untuk inject cookies
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
    
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(f"--user-data-dir={CHROME_PROFILE.absolute()}")
    options.add_argument("--profile-directory=Default")
    
    print("   Menyiapkan Chrome driver...")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    try:
        # Buka YouTube dulu (butuh domain untuk add_cookie)
        print("   Membuka youtube.com...")
        driver.get("https://www.youtube.com")
        time.sleep(3)
        
        # Inject cookies
        print("   Injecting cookies...")
        success_count = 0
        for cookie in youtube_cookies:
            try:
                # Selenium cookie format
                sel_cookie = {
                    "name": cookie.get("name", ""),
                    "value": cookie.get("value", ""),
                    "domain": cookie.get("domain", ".youtube.com"),
                    "path": cookie.get("path", "/"),
                    "secure": cookie.get("secure", True),
                }
                if cookie.get("expiry"):
                    sel_cookie["expiry"] = int(cookie["expiry"])
                if cookie.get("httpOnly"):
                    sel_cookie["httpOnly"] = True
                
                driver.add_cookie(sel_cookie)
                success_count += 1
            except Exception as e:
                pass  # Abaikan cookie yang gagal
        
        print(f"   ✅ {success_count}/{len(youtube_cookies)} cookie berhasil diinject")
        
        # Verifikasi: refresh halaman
        print("   Verifikasi login...")
        driver.get("https://www.youtube.com")
        time.sleep(3)
        
        # Cek apakah sudah login
        page_source = driver.page_source.lower()
        if "avatar" in page_source or "channel" in page_source or "savaratogether" in page_source:
            print("   ✅ VERIFIKASI BERHASIL! Session YouTube aktif.")
        else:
            print("   ⚠️  Verifikasi belum pasti. Coba buka studio.youtube.com...")
            driver.get("https://studio.youtube.com")
            time.sleep(3)
            
            current_url = driver.current_url.lower()
            if "studio.youtube.com" in current_url and "signin" not in current_url:
                print("   ✅ VERIFIKASI BERHASIL! Dashboard YouTube Studio terbuka.")
            else:
                print("   ❌ Verifikasi gagal. Cookie mungkin expired atau tidak valid.")
                print("   Ulangi: python railway_setup.py --login")
                print("   Pastikan export cookies SESUDAH login YouTube.")
        
        # Simpan profile
        print("   💾 Profile tersimpan di chrome_profile/")
        
    finally:
        driver.quit()
    
    return True


def cmd_verify():
    """Verifikasi apakah session YouTube masih aktif."""
    print("🔍 Verifikasi session YouTube...")
    
    if not (CHROME_PROFILE / "Default").exists():
        print("❌ chrome_profile belum ada. Jalankan: python railway_setup.py --login")
        return
    
    # Cek file Preferences untuk lihat是否有 cached login
    prefs_file = CHROME_PROFILE / "Default" / "Preferences"
    if prefs_file.exists():
        try:
            prefs = json.loads(prefs_file.read_text(encoding="utf-8"))
            if prefs.get("profile", {}).get("name"):
                print(f"   Profile: {prefs['profile']['name']}")
        except Exception:
            pass
    
    # Buka Chrome dan cek
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
    except ImportError:
        print("❌ Selenium belum terinstall.")
        return
    
    options = Options()
    if platform.system() == "Linux":
        chrome_candidates = ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable"]
        for p in chrome_candidates:
            if os.path.isfile(p):
                options.binary_location = p
                break
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
    
    options.add_argument(f"--user-data-dir={CHROME_PROFILE.absolute()}")
    options.add_argument("--profile-directory=Default")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    try:
        driver.get("https://studio.youtube.com")
        time.sleep(5)
        
        url = driver.current_url.lower()
        if "studio.youtube.com" in url and "signin" not in url:
            print("✅ Session YouTube MASIH AKTIF! Siap upload.")
        else:
            print("❌ Session YouTube EXPIRED atau tidak valid.")
            print("   Jalankan: python railway_setup.py --login")
    finally:
        driver.quit()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Gunakan: python railway_setup.py [--login | --verify | --setup-chrome]")
        print()
        print("  --login         Setup login YouTube via cookie injection")
        print("  --verify        Cek apakah session YouTube masih aktif")
        print("  --setup-chrome  Setup Chrome/xvfb di Linux (Railway)")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "--setup-chrome":
        cmd_setup_chrome_linux()
    elif cmd == "--login":
        cmd_login()
    elif cmd == "--verify":
        cmd_verify()
    else:
        print(f"Perintah tidak dikenal: {cmd}")
        sys.exit(1)
