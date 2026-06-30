@echo off
chcp 65001 >nul
set GCLOUD="C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"

echo ==============================================
echo   GOOGLE CLOUD AUTH LOGIN
echo ==============================================
echo.
echo STEP 1: Running gcloud auth login...
echo.
%GCLOUD% auth login --no-launch-browser 2>&1 | findstr /r "https://accounts.google.com"
echo.
echo ==============================================
echo STEP 2: Buka link di atas di browser kamu
echo Login dengan akun Google yang terhubung
echo ke channel YouTube tujuan upload
echo.
echo Setelah login, browser akan menampilkan
echo kode verifikasi. Copy kode tersebut.
echo ==============================================
echo.
set /p CODE="STEP 3: Paste kode verifikasi di sini: "
echo.
echo %CODE% | %GCLOUD% auth login --no-launch-browser 2>&1
echo.
if %ERRORLEVEL% EQU 0 (
    echo ✅ Login berhasil!
) else (
    echo ❌ Login gagal, coba lagi.
)
pause
