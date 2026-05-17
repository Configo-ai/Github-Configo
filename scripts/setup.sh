#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

WIZARD_FLAGS=""
for arg in "$@"; do
  if [[ "$arg" == "--yes" || "$arg" == "--non-interactive" ]]; then
    WIZARD_FLAGS="--yes"
  fi
done

install_hint() {
  local package="$1"
  if command -v brew >/dev/null 2>&1; then
    echo "    Install with: brew install $package"
  elif command -v apt-get >/dev/null 2>&1; then
    echo "    Install with: sudo apt-get install -y $package"
  elif command -v dnf >/dev/null 2>&1; then
    echo "    Install with: sudo dnf install -y $package"
  elif command -v pacman >/dev/null 2>&1; then
    echo "    Install with: sudo pacman -S --noconfirm $package"
  fi
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "  Missing required command: $1"
    install_hint "$1"
    exit 1
  fi
}

ensure_npm_global() {
  local package="$1"
  local binary="$2"
  if ! command -v "$binary" >/dev/null 2>&1; then
    echo "  Installing $binary..."
    npm install -g "$package"
  else
    echo "  ✓ $binary already installed"
  fi
}

echo ""
echo "  Configo Workspace Setup"
echo "  $(date '+%H:%M:%S')"
echo ""

require_cmd git
require_cmd python3
require_cmd node
require_cmd npm
require_cmd pip3

REPOS=(
  "Configo-Backend:https://github.com/Configo-ai/Configo-Backend.git"
  "Configo-AI-Worker:https://github.com/Configo-ai/Configo-AI-Worker.git"
  "Configo-Frontend:https://github.com/Configo-ai/Configo-Frontend.git"
  "Configo-Web-Frontend:https://github.com/Configo-ai/Configo-Web-Frontend.git"
  "Configo-Developer-Frontend:https://github.com/Configo-ai/Configo-Developer-Frontend.git"
  "Configo-Deployment:https://github.com/Configo-ai/Configo-Deployment.git"
)

cd "$ROOT"

for repo in "${REPOS[@]}"; do
  NAME="${repo%%:*}"
  URL="${repo##*:}"
  if [ -d "$NAME" ]; then
    echo "  ✓ $NAME already exists, skipping"
  else
    echo "  Cloning $NAME..."
    git clone "$URL"
    echo "  ✓ $NAME cloned"
  fi
done

echo ""
echo "  Installing Python dependencies (mcp, textual)..."
pip3 install --quiet mcp textual
echo "  ✓ mcp + textual installed"

echo ""
echo "  Installing OpenCode $(python3 - <<'PY'
from pathlib import Path
import json
print(json.loads((Path('tools/workspace_runtime.yaml')).read_text())['opencode_version'])
PY
)..."
npm install -g "opencode-ai@$(python3 - <<'PY'
from pathlib import Path
import json
print(json.loads((Path('tools/workspace_runtime.yaml')).read_text())['opencode_version'])
PY
)"
echo "  ✓ OpenCode pinned"
ensure_npm_global "@augmentcode/auggie@latest" "auggie"
ensure_npm_global "@tobilu/qmd" "qmd"
ensure_npm_global "typescript-language-server" "typescript-language-server"
ensure_npm_global "pyright" "pyright-langserver"

echo ""
if command -v gopls >/dev/null 2>&1; then
  echo "  ✓ gopls already on PATH"
elif command -v go >/dev/null 2>&1; then
  echo "  Installing gopls (Go LSP)..."
  go install golang.org/x/tools/gopls@latest
  echo "  ✓ gopls installed (ensure \$(go env GOBIN) or \$GOPATH/bin is on PATH)"
else
  echo "  ! Go not on PATH; skipping gopls install"
fi

echo ""
if command -v ollama >/dev/null 2>&1; then
  echo "  ✓ Ollama already on PATH"
else
  echo "  Installing Ollama (local-model host for the MCP description compactor)..."
  if [[ "$(uname)" == "Darwin" ]]; then
    if command -v brew >/dev/null 2>&1; then
      brew install ollama || echo "  ! brew install ollama failed"
    else
      echo "  ! Install Homebrew or get Ollama manually from https://ollama.com/download"
    fi
  else
    curl -fsSL https://ollama.com/install.sh | sh || echo "  ! Ollama install script failed; install manually from https://ollama.com/download"
  fi
fi
if command -v ollama >/dev/null 2>&1; then
  ollama pull llama3.2:3b
  echo "  ✓ llama3.2:3b ready"
fi

echo ""
if command -v mcp-language-server >/dev/null 2>&1; then
  echo "  ✓ mcp-language-server already on PATH"
elif command -v go >/dev/null 2>&1; then
  echo "  Installing mcp-language-server via go install..."
  go install github.com/isaacphi/mcp-language-server@latest
  echo "  ✓ mcp-language-server installed (ensure \$(go env GOBIN) or \$GOPATH/bin is on PATH)"
else
  echo "  ! Go not on PATH; skipping mcp-language-server install"
  echo "    Install Go from https://go.dev/dl, then re-run setup."
fi

echo ""
if command -v kimi >/dev/null 2>&1; then
  echo "  ✓ kimi already installed"
else
  echo "  Installing Kimi Code CLI via uv..."
  if ! command -v uv >/dev/null 2>&1; then
    echo "  Installing uv..."
    pip3 install --quiet --user uv
    # uv's user-install scripts dir may not be on PATH yet in this shell.
    USER_BIN="$(python3 -m site --user-base 2>/dev/null)/bin"
    [ -d "$USER_BIN" ] && export PATH="$USER_BIN:$PATH"
  fi
  if uv tool install --python 3.13 kimi-cli; then
    echo "  ✓ kimi installed - run \`kimi\` then \`/login\` to authenticate"
  else
    echo "  ! Kimi CLI install failed - run \`uv tool install --python 3.13 kimi-cli\` manually"
  fi
fi

echo ""
echo "  Applying local qmd patches (QMD_LLAMA_GPU=vulkan/metal/cuda support)..."
python3 "$ROOT/tools/patch_qmd.py"

echo ""
echo "  Persisting CLAUDE_CODE_SUBAGENT_MODEL=haiku (parallel Task subagents default cheap)..."
PROFILE_FILE="$HOME/.zshrc"
[ -f "$HOME/.bashrc" ] && PROFILE_FILE="$HOME/.bashrc"
if ! grep -q "CLAUDE_CODE_SUBAGENT_MODEL=" "$PROFILE_FILE" 2>/dev/null; then
  echo 'export CLAUDE_CODE_SUBAGENT_MODEL=haiku' >> "$PROFILE_FILE"
fi
echo "  ✓ CLAUDE_CODE_SUBAGENT_MODEL added to $PROFILE_FILE"

echo ""
echo "  Installing Superpowers for OpenCode..."
OPENCODE_CONFIG_DIR="$HOME/.config/opencode"
if [[ "$(uname)" == "Darwin" ]]; then
  OPENCODE_CONFIG_DIR="$HOME/Library/Application Support/opencode"
fi
mkdir -p "$OPENCODE_CONFIG_DIR"
npm install "superpowers@git+https://github.com/obra/superpowers.git" --prefix "$OPENCODE_CONFIG_DIR"
echo "  ✓ Superpowers installed"

echo ""
echo "  Configuring Context7 for OpenCode..."
if npx -y ctx7 setup --opencode --yes; then
  echo "  ✓ Context7 configured"
else
  echo "  ! Context7 setup needs manual completion"
fi

echo ""
echo "  Launching setup wizard..."
python3 "$ROOT/tools/setup_workspace.py" --root "$ROOT" wizard $WIZARD_FLAGS

echo ""
echo "  Setup complete!"
echo "  ─────────────────────────────────────────────────────────"
echo "  Next steps:"
echo "  1. Run 'claude login' if Claude is not authenticated yet"
echo "  2. Launch Claude with 'bash scripts/claude-workspace.sh'"
echo "  3. Launch OpenCode with 'bash scripts/opencode-workspace.sh'"
echo "  4. Use 'bash scripts/ws new <task> frontend backend' for cross-repo worktrees"
echo "  5. Copy Configo-Backend/.env.staging.example to Configo-Backend/.env.staging"
echo "  6. Fill in your staging credentials in Configo-Backend/.env.staging"
echo "  7. Run ./scripts/dev.sh to start all servers"
echo "  ─────────────────────────────────────────────────────────"
echo ""
