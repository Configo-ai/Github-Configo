#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

command="${1:-list}"

case "$command" in
  list)
    exec python3 "$ROOT/tools/session_runtime.py" list --root "$ROOT" --cwd "$PWD"
    ;;
  use)
    conversation="${2:-}"
    if [ -z "$conversation" ]; then
      echo "Usage: bash scripts/cross-resume.sh use <workspace_conversation_id>"
      exit 1
    fi
    exec python3 "$ROOT/tools/session_runtime.py" activate --root "$ROOT" --cwd "$PWD" --conversation "$conversation"
    ;;
  claude)
    conversation="${2:-}"
    shift 2 || true
    if [ -z "$conversation" ]; then
      echo "Usage: bash scripts/cross-resume.sh claude <workspace_conversation_id> [claude args...]"
      exit 1
    fi
    exec python3 "$ROOT/tools/workspace_launcher.py" claude --root "$ROOT" --cwd "$PWD" --conversation "$conversation" -- "$@"
    ;;
  opencode)
    conversation="${2:-}"
    shift 2 || true
    if [ -z "$conversation" ]; then
      echo "Usage: bash scripts/cross-resume.sh opencode <workspace_conversation_id> [opencode args...]"
      exit 1
    fi
    exec python3 "$ROOT/tools/workspace_launcher.py" opencode --root "$ROOT" --cwd "$PWD" --conversation "$conversation" -- "$@"
    ;;
  *)
    cat <<EOF
Usage:
  bash scripts/cross-resume.sh
  bash scripts/cross-resume.sh list
  bash scripts/cross-resume.sh use <workspace_conversation_id>
  bash scripts/cross-resume.sh claude <workspace_conversation_id> [claude args...]
  bash scripts/cross-resume.sh opencode <workspace_conversation_id> [opencode args...]
EOF
    exit 1
    ;;
esac
