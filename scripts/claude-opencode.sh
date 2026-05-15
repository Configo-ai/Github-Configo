#!/bin/bash
set -euo pipefail

if ! curl -s --max-time 1 http://127.0.0.1:3456 >/dev/null 2>&1; then
    echo "Starting Meridian..."
    meridian &
    sleep 2
fi

export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-x}"
export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-http://127.0.0.1:3456}"
exec opencode "$@"
