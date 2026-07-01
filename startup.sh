#!/bin/bash
# ============================================================
# startup.sh — Entrypoint untuk Railway
# 
# 1. Start Xvfb (virtual display untuk Chrome/Selenium)
# 2. Start healthcheck HTTP server (biar Railway tau container hidup)
# 3. Start scheduler YouTube Shorts Factory
# ============================================================
set -e

echo "══════════════════════════════════════════════"
echo "  🚀 YouTube Shorts Factory — Railway Startup"
echo "  $(date)"
echo "══════════════════════════════════════════════"

# ─── 1. Start Xvfb ──────────────────────────────────────────
echo "📺 Starting Xvfb virtual display (DISPLAY=:99)..."
Xvfb :99 -screen 0 1280x1024x24 -ac &
XVFB_PID=$!
sleep 2

if kill -0 $XVFB_PID 2>/dev/null; then
    echo "✅ Xvfb running (PID: $XVFB_PID)"
else
    echo "❌ Xvfb failed to start!"
    exit 1
fi

# ─── 2. Healthcheck HTTP server ─────────────────────────────
echo "🏥 Starting healthcheck server on port 8080..."
python -c "
import http.server
import json

class HealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'alive'}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Silent

server = http.server.HTTPServer(('0.0.0.0', 8080), HealthHandler)
server.serve_forever()
" &
HEALTH_PID=$!
echo "✅ Healthcheck server running (PID: $HEALTH_PID)"

# ─── 3. Inject Cookies dari Environment Variable ────────────
if [ -n "$YOUTUBE_COOKIES_B64" ]; then
    echo "🍪 YOUTUBE_COOKIES_B64 ditemukan! Meng-inject cookies..."
    echo "$YOUTUBE_COOKIES_B64" | python -c "
import sys, json, base64
cookies = json.loads(base64.b64decode(sys.stdin.read().strip()))
with open('/app/chrome_profile/cookies.json', 'w') as f:
    json.dump(cookies, f)
print(f'✅ {len(cookies)} cookies disimpan ke /app/chrome_profile/cookies.json')
" && echo "✅ Cookies berhasil di-inject!" || echo "⚠️  Gagal inject cookies"
fi

# ─── 4. Setup Chrome Profile jika belum ada ─────────────────
if [ ! -f "/app/chrome_profile/First Run" ]; then
    echo "⚠️  chrome_profile belum ada. Membuat baru..."
    mkdir -p /app/chrome_profile
fi

# ─── 5. Start Scheduler ─────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════"
echo "  ⏰ Starting Scheduler..."
echo "  📅 Jadwal: $(python -c 'import config; print(config.SCHEDULE_TIMES)')"
echo "══════════════════════════════════════════════"
echo ""

cd /app
python main.py &

# ─── Trap shutdown ──────────────────────────────────────────
trap "echo 'Shutting down...'; kill $XVFB_PID $HEALTH_PID 2>/dev/null; exit 0" SIGINT SIGTERM

# ─── Wait ───────────────────────────────────────────────────
wait
