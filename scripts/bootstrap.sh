#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== Configo Workspace Bootstrap ==="
echo "Root: $ROOT"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1"
    return 1
  fi
}

require_cmd git
require_cmd python3
require_cmd node
require_cmd npm

if ! command -v opencode >/dev/null 2>&1; then
  echo "Installing OpenCode..."
  npm install -g opencode-ai
fi

if ! command -v auggie >/dev/null 2>&1; then
  echo "Installing Auggie CLI..."
  npm install -g @augmentcode/auggie@latest
fi

mkdir -p "$HOME/.config/opencode"
npm install "superpowers@git+https://github.com/obra/superpowers.git" --prefix "$HOME/.config/opencode"
npx -y ctx7 setup --opencode --yes || true
python3 "$ROOT/tools/setup_opencode.py" configure --root "$ROOT"

echo "Bootstrap complete."
echo "Next steps:"
echo "  1. Run 'auggie login' if this machine is not already authenticated"
echo "  2. Open https://app.augmentcode.com/mcp/configuration and choose the OpenCode remote MCP config"
echo "  3. Install the Augment GitHub App there and select the Configo repos for remote indexing"
echo "  4. Add/authenticate the remote MCP in OpenCode using Augment's generated config"
echo "  5. Open OpenCode and verify 'augment-context-engine-local' is available"
echo "  6. Copy Configo-Backend/.env.staging.example to Configo-Backend/.env.staging"
echo "  7. Fill in staging credentials"
echo "  8. Run ./scripts/dev.sh"
