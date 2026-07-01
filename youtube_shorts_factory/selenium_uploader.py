"""
Selenium-based YouTube Studio Uploader
Bypass OAuth consent screen issues entirely.
User login manual sekali di browser, session tersimpan.
Cookie injection via YOUTUBE_COOKIES_B64 environment variable for Railway.
"""
import sys
import os
import json
import time
import platform
import subprocess
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import TimeoutException
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    print("❌ Install dulu: pip install selenium webdriver-manager")
    sys.exit(1)

BASE_DIR = Path(__file__).parent
CHROME_PROFILE = BASE_DIR / "chrome_profile"
COOKIES_FILE = CHROME_PROFILE / "cookies.json"  # Injected by startup.sh from YOUTUBE_COOKIES_B64
VIDEOS_DIR = BASE_DIR / "output" / "videos"

def cari_video_terbaru() -> Path | None:
    videos = sorted(VIDEOS_DIR.glob("*.mp4"))
    non_test = [v for v in videos if "test_session" not in v.name]
    return (non_test or videos)[-1] if videos else None

def _find_chrome_binary() -> str:
    """Cari lokasi Chrome binary di berbagai OS."""
    system = platform.system()
    
    if system == "Windows":
        # Path umum Chrome di Windows
        candidates = [
            r"C:\Users\ACER\AppData\Local\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe"),
        ]
        for path in candidates:
            if os.path.isfile(path):
                return path
        # Fallback: coba where command
        try:
            result = subprocess.run(["where", "chrome"], capture_output=True, text=True, check=True)
            return result.stdout.strip().split("\n")[0]
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        raise FileNotFoundError("Chrome binary tidak ditemukan di Windows!")
    
    elif system == "Linux":
        # Railway / Linux umum
        candidates = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
        ]
        for path in candidates:
            if os.path.isfile(path):
                return path
        # Fallback: coba which
        try:
            result = subprocess.run(["which", "google-chrome"], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        try:
            result = subprocess.run(["which", "chromium"], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        raise FileNotFoundError("Chrome binary tidak ditemukan di Linux!")
    
    else:
        raise RuntimeError(f"Unsupported OS: {system}")


def setup_driver() -> webdriver.Chrome:
    options = Options()
    
    # Deteksi OS dan cari Chrome binary
    CHROME_BIN = _find_chrome_binary()
    print(f"🔍 Chrome binary: {CHROME_BIN}")
    options.binary_location = CHROME_BIN
    
    # Profile terpisah (biar gak bentrok sama Chrome yg sedang berjalan)
    options.add_argument(f"--user-data-dir={CHROME_PROFILE.absolute()}")
    options.add_argument("--profile-directory=Default")
    
    # Anti-deteksi
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--window-size=1280,800")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--remote-debugging-port=0")
    
    # Linux-specific: disable GPU (ga ada GPU di container)
    if platform.system() == "Linux":
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
    
    print("🔧 Menyiapkan Chrome...")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


def _inject_cookies_from_file(driver: webdriver.Chrome) -> bool:
    """
    Load cookies dari COOKIES_FILE (diiject oleh startup.sh dari YOUTUBE_COOKIES_B64)
    dan inject ke browser Selenium sebelum navigasi ke YouTube.
    """
    if not COOKIES_FILE.exists():
        print("📭 File cookies tidak ditemukan, lanjut tanpa cookie injection.")
        return False

    try:
        with open(COOKIES_FILE, 'r') as f:
            cookies = json.load(f)

        if not cookies:
            print("📭 File cookies kosong.")
            return False

        print(f"🍪 Ditemukan {len(cookies)} cookies di {COOKIES_FILE.name}")

        # Filter hanya cookie youtube.com & google.com
        youtube_cookies = [
            c for c in cookies
            if "youtube.com" in c.get("domain", "") or "google.com" in c.get("domain", "")
        ]
        if not youtube_cookies:
            youtube_cookies = cookies  # fallback: inject semua

        print(f"   {len(youtube_cookies)} cookie untuk YouTube/Google akan di-inject")

        # Buka YouTube dulu (domain required untuk add_cookie)
        print("   Membuka youtube.com...")
        driver.get("https://www.youtube.com")
        time.sleep(2)

        # Inject cookies
        success_count = 0
        for cookie in youtube_cookies:
            try:
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
            except Exception:
                pass  # Abaikan cookie yang gagal

        print(f"   ✅ {success_count}/{len(youtube_cookies)} cookie berhasil diinject")

        # Verifikasi: refresh YouTube
        print("   Verifikasi login...")
        driver.get("https://www.youtube.com")
        time.sleep(3)

        page_source = driver.page_source.lower()
        if "avatar" in page_source or "channel" in page_source:
            print("   ✅ Session YouTube aktif! (avatar/channel ditemukan)")
            return True
        else:
            # Coba cek studio
            driver.get("https://studio.youtube.com")
            time.sleep(3)
            current_url = driver.current_url.lower()
            if "studio.youtube.com" in current_url and "signin" not in current_url:
                print("   ✅ Dashboard YouTube Studio terbuka! Login via cookie berhasil.")
                return True
            else:
                print("   ⚠️ Cookie mungkin expired, akan fallback ke manual login.")
                return False

    except Exception as e:
        print(f"   ⚠️ Error inject cookies: {e}")
        return False


def tunggu_login(driver: webdriver.Chrome) -> bool:
    print()
    print("=" * 60)
    print("  🚀 BROWSER TERBUKA - YOUTUBE STUDIO")
    print("=" * 60)
    print()
    print("  1️⃣  Browser Chrome akan terbuka")
    print("  2️⃣  Login dengan akun Google kamu (savaratogether@gmail.com)")
    print("  3️⃣  Setelah masuk dashboard YouTube Studio, biarkan saja")
    print("  4️⃣  Script akan lanjut otomatis")
    print()
    print("  ⏳ Menunggu login... (maks 10 menit)")
    print()
    
    driver.get("https://studio.youtube.com")
    
    start = time.time()
    timeout = 600  # 10 menit
    
    while time.time() - start < timeout:
        url = driver.current_url.lower()
        
        # Sudah di dashboard
        if any(x in url for x in ["studio.youtube.com"]):
            # Cek apakah masih di halaman login
            if "accounts.google.com" not in url and "signin" not in url:
                print()
                print("✅ Berhasil login ke YouTube Studio!")
                return True
        
        remaining = int(timeout - (time.time() - start))
        if remaining % 30 == 0:  # Update setiap 30 detik
            print(f"⏳ Masih menunggu login... ({remaining//60} menit {remaining%60} detik)")
        
        time.sleep(2)
    
    print()
    print("❌ Timeout menunggu login.")
    return False

def _cari_file_input(driver: webdriver.Chrome, timeout: int = 15) -> webdriver.remote.webelement.WebElement | None:
    """Cari file input (hidden atau visible)"""
    for _ in range(timeout):
        # Approach: langsung cari input[type='file'] - biasanya hidden
        try:
            fi = driver.find_element(By.CSS_SELECTOR, "input[type='file']")
            # File input biasanya hidden, jangan cek is_displayed()
            return fi
        except:
            pass
        # Klik "Select files" button jika ada (trigger hidden input)
        try:
            for xp in [
                "//*[contains(text(),'Select files')]",
                "//*[contains(text(),'Pilih file')]",
                "//*[contains(text(),'Browse')]",
                "//*[contains(text(),'Telusuri')]",
                "//*[@aria-label='Select files']",
            ]:
                try:
                    btn = driver.find_element(By.XPATH, xp)
                    if btn.is_displayed():
                        btn.click()
                        time.sleep(1)
                        return driver.find_element(By.CSS_SELECTOR, "input[type='file']")
                except:
                    continue
        except:
            pass
        time.sleep(1)
    return None


def _set_title_js(driver: webdriver.Chrome, title: str) -> bool:
    """Set judul video via JavaScript injection (bypass shadow DOM issues)"""
    js = """
    const titleText = arguments[0];
    let found = false;
    
    // Fungsi untuk mencari di dalam shadow roots
    function findInShadow(root, selectors) {
        for (const sel of selectors) {
            try {
                // Cari di light DOM
                let el = root.querySelector(sel);
                if (el) return el;
                
                // Cari di shadow DOM semua elemen
                const all = root.querySelectorAll('*');
                for (const elem of all) {
                    if (elem.shadowRoot) {
                        el = findInShadow(elem.shadowRoot, [sel]);
                        if (el) return el;
                    }
                }
            } catch(e) {}
        }
        return null;
    }
    
    const selectors = [
        '#title-textarea', '#textbox', 'ytcp-video-title #textbox',
        '#title-textarea #contenteditable', '#title-textarea div[contenteditable]',
        'input#title', 'input[name="title"]', '#title-text',
        'ytcp-mention-input', '[aria-label*="Title"]', '[aria-label*="Judul"]',
        '[placeholder*="Title"]', '[placeholder*="Judul"]',
        '.ytcp-video-title', '#title-container input'
    ];
    
    const el = findInShadow(document, selectors);
    if (el) {
        // Focus
        el.focus();
        el.click();
        
        // Set value via multiple methods
        if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
            el.value = titleText;
        } else {
            // contenteditable
            el.textContent = titleText;
        }
        
        // Dispatch events
        el.dispatchEvent(new Event('focus', {bubbles: true}));
        el.dispatchEvent(new Event('input', {bubbles: true}));
        el.dispatchEvent(new Event('change', {bubbles: true}));
        el.dispatchEvent(new Event('blur', {bubbles: true}));
        
        return true;
    }
    return false;
    """
    try:
        result = driver.execute_script(js, title[:100])
        if result:
            print("   ✅ Judul diisi (via JS)")
            return True
    except:
        pass
    return False


def _upload_ke_classic_page(driver: webdriver.Chrome, video_path: Path, title: str) -> bool:
    """Upload via classic youtube.com/upload (mungkin redirect ke studio)"""
    print("📋 Menggunakan youtube.com/upload...")
    
    try:
        # Tunggu file input
        fi = _cari_file_input(driver, 10)
        if not fi:
            print("   ⚠️ Refresh halaman...")
            driver.get("https://www.youtube.com/upload")
            time.sleep(8)
            fi = _cari_file_input(driver, 10)
        
        if not fi:
            print("❌ Tidak dapat menemukan file input")
            return False
        
        fi.send_keys(str(video_path.absolute()))
        print("   ✅ File diupload, menunggu proses (30 detik)...")
        time.sleep(30)
        
        # === Isi judul via JavaScript ===
        print("   Isi judul...")
        title_found = _set_title_js(driver, title)
        
        # Fallback Selenium jika JS gagal
        if not title_found:
            for sel in [
                "#title-textarea", "#textbox", "#textbox[contenteditable]",
                "ytcp-video-title #textbox", "ytcp-mention-input div#contenteditable",
                "#title-container input", "input#title", "input[name='title']",
            ]:
                try:
                    tb = driver.find_element(By.CSS_SELECTOR, sel)
                    if tb.is_displayed():
                        tb.click()
                        time.sleep(0.5)
                        tb.clear()
                        tb.send_keys(title[:100])
                        title_found = True
                        print("   ✅ Judul diisi (selenium)")
                        break
                except:
                    continue
        
        if not title_found:
            print("   ⚠️ Gagal isi judul")
        
        # === Not for kids ===
        try:
            for xp in [
                "//*[@name='VIDEO_MADE_FOR_KIDS_NOT_MFK']",
                "//span[contains(text(),'No, it')]/..",
                "//*[contains(text(),'Bukan untuk anak')]/..",
            ]:
                try:
                    el = driver.find_element(By.XPATH, xp)
                    if el.is_displayed():
                        el.click()
                        break
                except:
                    continue
        except:
            pass
        
        # === Next buttons ===
        for i in range(3):
            try:
                nb = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, "//ytcp-button//span[contains(text(),'Next')]/.."))
                )
                nb.click()
                time.sleep(2)
            except:
                break
        
        # === Visibility: Unlisted ===
        try:
            for xp in [
                "//*[@name='UNLISTED']",
                "//span[contains(text(),'Unlisted')]/..",
                "//*[contains(text(),'Tidak terdaftar')]/..",
            ]:
                try:
                    el = driver.find_element(By.XPATH, xp)
                    if el.is_displayed():
                        el.click()
                        break
                except:
                    continue
        except:
            pass
        
        time.sleep(1)
        
        # === Done/Save ===
        for sel in [
            "ytcp-button#done-button",
            "//ytcp-button//span[contains(text(),'Done')]/..",
            "//ytcp-button//span[contains(text(),'Save')]/..",
            "//ytcp-button//span[contains(text(),'Simpan')]/..",
            "//*[contains(text(),'PUBLISH')]/..",
        ]:
            try:
                if sel.startswith("//"):
                    el = driver.find_element(By.XPATH, sel)
                else:
                    el = driver.find_element(By.CSS_SELECTOR, sel)
                if el.is_displayed():
                    el.click()
                    time.sleep(2)
                    print("   ✅ Done/Save")
                    break
            except:
                continue
        
        print("✅ Video terupload!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def upload_video(driver: webdriver.Chrome, video_path: Path, title: str) -> bool:
    print()
    print(f"📤 Upload: {video_path.name}")
    
    try:
        # === APPROACH 1: YouTube Studio via Create button ===
        print("1️⃣ Mencoba YouTube Studio (via Create button)...")
        driver.get("https://studio.youtube.com")
        time.sleep(5)
        
        print("   Mencari tombol Create...")
        create_found = False
        for sel in [
            "[aria-label='Create']", "[aria-label='Buat']", "#create-icon",
            "ytcp-button#create-icon", "yt-icon-button#create-icon",
            "tp-yt-paper-icon-button#create-icon",
        ]:
            try:
                btn = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                if btn.is_displayed():
                    btn.click()
                    create_found = True
                    print(f"   ✅ Create button: {sel}")
                    break
            except:
                continue
        
        if create_found:
            time.sleep(3)  # Tunggu dropdown
            
            print("   Mencari opsi Upload videos...")
            upload_found = False
            for xp in [
                "//*[contains(text(),'Upload video')]",
                "//*[contains(text(),'Upload videos')]",
                "//*[contains(text(),'Upload')]",
                "//tp-yt-paper-item//span",
                "//ytcp-ve//span[contains(text(),'Upload')]",
                "//ytcp-menu-item[@role='menuitem']",
            ]:
                try:
                    items = driver.find_elements(By.XPATH, xp)
                    for item in items:
                        txt = item.text.lower()
                        if item.is_displayed() and ("upload" in txt or "unggah" in txt):
                            item.click()
                            upload_found = True
                            print(f"   ✅ Upload option ditemukan: '{item.text[:30]}'")
                            break
                    if upload_found:
                        break
                except:
                    continue
            
            if upload_found:
                time.sleep(5)
                # Cari file input
                fi = _cari_file_input(driver, 10)
                if fi:
                    fi.send_keys(str(video_path.absolute()))
                    print("   ✅ File terupload, proses selanjutnya...")
                    time.sleep(25)
                    
                    # Isi judul — prioritaskan JavaScript injection (shadow DOM)
                    print("   Isi judul...")
                    title_found = _set_title_js(driver, title)
                    
                    # Fallback Selenium jika JS gagal
                    if not title_found:
                        for sel in ["#title-textarea", "#textbox", "ytcp-video-title #textbox",
                                     "div#contenteditable", "[contenteditable]"]:
                            try:
                                tb = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                                if tb.is_displayed():
                                    tb.click()
                                    time.sleep(0.3)
                                    tb.clear()
                                    tb.send_keys(title[:100])
                                    print("   ✅ Judul diisi (selenium fallback)")
                                    title_found = True
                                    break
                            except:
                                continue
                    
                    if not title_found:
                        print("   ⚠️ Gagal isi judul — melanjutkan...")
                    
                    # Not for kids
                    for xp in ["//*[@name='VIDEO_MADE_FOR_KIDS_NOT_MFK']",
                               "//span[contains(text(),'No, it')]/..",
                               "//*[contains(text(),'Bukan untuk anak')]/.."]:
                        try:
                            el = driver.find_element(By.XPATH, xp)
                            if el.is_displayed():
                                el.click()
                                break
                        except:
                            continue
                    
                    # Next buttons
                    for i in range(3):
                        try:
                            nb = WebDriverWait(driver, 4).until(
                                EC.element_to_be_clickable((By.XPATH, "//ytcp-button//span[contains(text(),'Next')]/.."))
                            )
                            nb.click()
                            time.sleep(2)
                        except:
                            break
                    
                    # Visibility
                    for xp in ["//*[@name='UNLISTED']", "//span[contains(text(),'Unlisted')]/..",
                               "//*[contains(text(),'Tidak terdaftar')]/.."]:
                        try:
                            el = driver.find_element(By.XPATH, xp)
                            if el.is_displayed():
                                el.click()
                                break
                        except:
                            continue
                    
                    time.sleep(1)
                    
                    # Save
                    for sel in ["ytcp-button#done-button", "//ytcp-button//span[contains(text(),'Done')]/..",
                                 "//ytcp-button//span[contains(text(),'Save')]/..",
                                 "//ytcp-button//span[contains(text(),'Simpan')]/.."]:
                        try:
                            if sel.startswith("//"):
                                el = driver.find_element(By.XPATH, sel)
                            else:
                                el = driver.find_element(By.CSS_SELECTOR, sel)
                            if el.is_displayed():
                                el.click()
                                time.sleep(2)
                                break
                        except:
                            continue
                    
                    print("✅ Upload via Studio selesai!")
                    return True
        
        # === APPROACH 2: Classic youtube.com/upload ===
        print()
        print("2️⃣ Fallback ke youtube.com/upload...")
        driver.get("https://www.youtube.com/upload")
        time.sleep(5)
        return _upload_ke_classic_page(driver, video_path, title)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("=" * 60)
    print("  YOUTUBE STUDIO UPLOADER v2")
    print("  (Upload lewat browser - Bypass OAuth)")
    print("=" * 60)
    print()
    
    # Ambil SEMUA video (kecuali test_session)
    videos = sorted(VIDEOS_DIR.glob("*.mp4"))
    non_test = [v for v in videos if "test_session" not in v.name]
    
    if not non_test:
        print("❌ Tidak ada video untuk diupload")
        return
    
    print(f"📦 Total {len(non_test)} video untuk diupload:")
    for v in non_test:
        size_mb = v.stat().st_size / (1024 * 1024)
        print(f"   🎬 {v.name} ({size_mb:.1f} MB)")
    print()
    
    driver = setup_driver()
    
    if not tunggu_login(driver):
        print("\n⏹️  Browser akan ditutup...")
        time.sleep(5)
        driver.quit()
        return
    
    success_count = 0
    for i, video in enumerate(non_test):
        print()
        print("=" * 60)
        print(f"  [{i+1}/{len(non_test)}] Upload: {video.name}")
        print("=" * 60)
        
        # Generate title dari nama file
        title = "Jebakan Paylater: Gue Kira Uang Gratis! 💸 #shorts"
        
        success = upload_video(driver, video, title)
        
        if success:
            success_count += 1
            print(f"✅ [{i+1}/{len(non_test)}] Upload berhasil!")
        else:
            print(f"⚠️ [{i+1}/{len(non_test)}] Upload gagal")
        
        time.sleep(3)
    
    print()
    print("=" * 60)
    print(f"  📊 HASIL: {success_count}/{len(non_test)} video terupload!")
    print("=" * 60)
    print("  📌 Cek: https://studio.youtube.com")
    
    print("\n⏹️  Browser akan ditutup dalam 5 detik...")
    time.sleep(5)
    driver.quit()

# ─── Pipeline Integration ────────────────────────────────────────────────────

def upload_video_pipeline(video_path: Path, script: str) -> str:
    """
    Fungsi yang dipanggil oleh main.py (pipeline).
    - video_path: path ke file .mp4
    - script: teks skrip (untuk generate title)
    Returns: URL YouTube Shorts atau raise exception.
    """
    # Ambil judul dari script (kalimat pertama)
    title = script.strip().split('\n')[0][:100]
    if not title:
        title = "YouTube Shorts #shorts"
    # Tambah #shorts
    if "#shorts" not in title.lower():
        title = title + " #shorts"
    
    print()
    print("=" * 60)
    print("  📤 PIPELINE UPLOAD via Selenium")
    print("=" * 60)
    print(f"  🎬 Video: {video_path.name}")
    print(f"  📝 Title: {title}")
    print()
    
    try:
        driver = setup_driver()
        
        # ─── Cookie Injection ────────────────────────────────────────────
        # Coba inject cookies dari file (YOUTUBE_COOKIES_B64 via startup.sh)
        cookies_injected = _inject_cookies_from_file(driver)
        
        if cookies_injected:
            # Langsung ke YouTube Studio — seharusnya sudah login
            print("   🚀 Navigasi ke YouTube Studio...")
            driver.get("https://studio.youtube.com")
            time.sleep(5)
            
            # Verifikasi: cek apakah benar-benar sampai dashboard
            current_url = driver.current_url.lower()
            if "accounts.google.com" not in current_url and "signin" not in current_url:
                print("✅ Login via cookie berhasil! Dashboard YouTube Studio terbuka.")
            else:
                print("⚠️  Cookie gagal, fallback ke manual login...")
                cookies_injected = False  # fallback
        
        if not cookies_injected:
            # Cek login (session tersimpan di chrome_profile)
            print("📋 Memeriksa session tersimpan di chrome_profile...")
            driver.get("https://studio.youtube.com")
            time.sleep(5)
            
            if "accounts.google.com" in driver.current_url or "signin" in driver.current_url:
                # Belum login — butuh user intervensi
                print("⚠️  Belum login! Chrome akan terbuka.")
                print("   Silakan login dengan akun YouTube kamu.")
                print("   Script akan menunggu 10 menit...")
                
                start = time.time()
                timeout = 600
                while time.time() - start < timeout:
                    url = driver.current_url.lower()
                    if "studio.youtube.com" in url and "accounts.google.com" not in url:
                        print("✅ Login berhasil!")
                        break
                    remaining = int(timeout - (time.time() - start))
                    if remaining % 60 == 0:
                        print(f"⏳ Menunggu login... ({remaining//60} menit)")
                    time.sleep(2)
                else:
                    driver.quit()
                    raise TimeoutError("Timeout menunggu login")
        
        # Upload
        success = upload_video(driver, video_path, title)
        
        driver.quit()
        
        if not success:
            raise RuntimeError("Upload video via Selenium gagal")
        
        # Return URL — user cek di studio.youtube.com
        return f"https://studio.youtube.com (upload: {video_path.name})"
        
    except Exception as e:
        print(f"❌ Pipeline upload error: {e}")
        raise


if __name__ == "__main__":
    main()
