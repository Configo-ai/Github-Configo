#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
SILENT=false

if [[ "${1:-}" == "--silent" ]]; then
  SILENT=true
fi

log() {
  $SILENT || echo -e "$1"
}

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

GRAPHIFY_DIR="$ROOT/graphify"
export GRAPHIFY_OUT="$GRAPHIFY_DIR"

log "${YELLOW}Updating knowledge graph...${NC}"

if ! command -v graphify >/dev/null 2>&1; then
  log "${YELLOW}graphify not installed. Installing...${NC}"
  python3 -m pip install graphify --user --quiet
fi

mkdir -p "$GRAPHIFY_DIR"
graphify --update ${SILENT:+--quiet} 2>/dev/null || true

python3 "$ROOT/tools/bootstrap_workspace.py" install-repo-support --root "$ROOT" --platform unix >/dev/null
python3 "$ROOT/tools/bootstrap_workspace.py" write-claude-md --root "$ROOT"

log "${GREEN}Knowledge graph updated.${NC}"
