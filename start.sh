#!/bin/bash
# Athena2 Web Product Test Tool Startup Script

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# 1. Build frontend
echo "=== Building Frontend ==="
cd "$FRONTEND_DIR" && npm run build

# 2. Cleanup: 只用 ss 定位端口进程, 不用 pkill (高负载下遍历 /proc 会挂起)
echo "=== Cleaning up ==="
for port in 1935 8889 9997 8099; do
    pid=$(ss -tlnp "sport = :$port" 2>/dev/null | grep -oP "pid=\K\d+" | head -1)
    if [ -n "$pid" ]; then
        echo "  Killing PID $pid (port $port)"
        kill $pid 2>/dev/null
    fi
done
sleep 1

# 3. Start MediaMTX
if [ -x /opt/mediamtx/mediamtx ]; then
  echo "=== Starting MediaMTX ==="
  nohup /opt/mediamtx/mediamtx "$SCRIPT_DIR/mediamtx.yml" > "$SCRIPT_DIR/mediamtx_run.log" 2>&1 &
  sleep 2
  echo "MediaMTX started"
else
  echo "[WARN] MediaMTX not found"
fi
echo

# 4. Start backend
echo "=== Starting Backend (:8099) ==="
cd "$SCRIPT_DIR"
exec python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8099
