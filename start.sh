#!/bin/bash
# Athena2 Web Product Test Tool Startup Script

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# 1. Build frontend
echo "=== Building Frontend ==="
cd "$FRONTEND_DIR" && npm run build

# 2. Start backend (must run from web_product_test/ for package imports)
echo "=== Starting Backend ==="
cd "$SCRIPT_DIR"
exec python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8080