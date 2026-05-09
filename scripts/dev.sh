#!/bin/bash
# Configo Local Dev Launcher (Linux/Mac)
# Starts: Backend (Go with staging Supabase) > All 3 Frontends (Vite)
#
# Usage:  ./scripts/dev.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

echo ""
echo "  Configo Local Dev Launcher"
echo "  $(date '+%H:%M:%S')"
echo ""

# Paths
BACKEND_DIR="$ROOT/Configo-Backend"
MAIN_DIR="$ROOT/Configo-Frontend"
WEB_DIR="$ROOT/Configo-Web-Frontend"
DEVELOPER_DIR="$ROOT/Configo-Developer-Frontend"

# Kill existing processes on our ports
cleanup() {
    echo ""
    echo "Stopping dev servers..."
    pkill -f "vite.*8080" || true
    pkill -f "vite.*8081" || true
    pkill -f "vite.*8082" || true
    pkill -f "go run.*cmd/api/main.go" || true
}

trap cleanup EXIT

# Start Go backend with staging env
echo "Starting Go backend (staging Supabase)..."
cd "$BACKEND_DIR"
if [ -f .env.staging ]; then
    set -a
    source .env.staging
    set +a
    go run ./cmd/api/main.go > /tmp/configo-backend.log 2>&1 &
    BACKEND_PID=$!
    echo "  Backend PID: $BACKEND_PID (logs: /tmp/configo-backend.log)"
else
    echo "  ERROR: .env.staging not found in Configo-Backend"
    echo "  Copy .env.staging.example to .env.staging and fill in credentials"
    exit 1
fi

# Wait for backend to be ready
sleep 2

# Start Configo-Frontend (main)
echo "Starting Configo-Frontend on port 8080..."
cd "$MAIN_DIR"
npm run dev -- --host > /tmp/configo-main.log 2>&1 &
MAIN_PID=$!
echo "  Main PID: $MAIN_PID (logs: /tmp/configo-main.log)"

# Start Configo-Web-Frontend
echo "Starting Configo-Web-Frontend on port 8081..."
cd "$WEB_DIR"
npm run dev -- --host > /tmp/configo-web.log 2>&1 &
WEB_PID=$!
echo "  Web PID: $WEB_PID (logs: /tmp/configo-web.log)"

# Start Configo-Developer-Frontend
echo "Starting Configo-Developer-Frontend on port 8082..."
cd "$DEVELOPER_DIR"
npm run dev -- --host > /tmp/configo-developer.log 2>&1 &
DEVELOPER_PID=$!
echo "  Developer PID: $DEVELOPER_PID (logs: /tmp/configo-developer.log)"

echo ""
echo "  All servers started!"
echo "  ─────────────────────────────────────────────────────────"
echo "  Main Frontend:      http://localhost:8080"
echo "  Web Frontend:       http://localhost:8081"
echo "  Developer Frontend: http://localhost:8082"
echo "  Backend API:        http://localhost:9090 (or PORT from .env.staging)"
echo "  ─────────────────────────────────────────────────────────"
echo ""
echo "Press Ctrl+C to stop all servers"

# Wait for all background processes
wait
