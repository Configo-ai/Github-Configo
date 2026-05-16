#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

exec python3 "$ROOT/tools/workspace_launcher.py" claude --root "$ROOT" --cwd "$PWD" -- "$@"
