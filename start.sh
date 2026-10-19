#!/bin/bash
# Athena2 Web Product Test Tool Startup Script

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# 1. Build frontend
echo "=== Building Frontend ==="
cd "$FRONTEND_DIR" && npm run build

# 2. Start MediaMTX (WebRTC relay, V4.0)
pkill -f mediamtx 2>/dev/null; sleep 1  # 先杀旧进程, 再起新的
if [ -x /opt/mediamtx/mediamtx ]; then
  echo "=== Starting MediaMTX ==="
  ( /opt/mediamtx/mediamtx /media/cvitek/xiaohao.liu/product_test/mediamtx.yml & )
  MEDIAMTX_PID=$!
  trap "kill $MEDIAMTX_PID 2>/dev/null; exit" EXIT INT TERM
  sleep 2
  echo "MediaMTX PID=$MEDIAMTX_PID"
else
  echo "[WARN] MediaMTX not found, skip"
fi
echo

# 3. Start backend (must run from web_product_test/ for package imports)
echo "=== Starting Backend ==="
cd "$SCRIPT_DIR"
exec python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8099
