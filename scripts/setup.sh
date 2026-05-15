#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

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
  local extra_flags="${3:-}"
  if ! command -v "$binary" >/dev/null 2>&1; then
    echo "  Installing $binary..."
    npm install -g "$package" $extra_flags
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
echo "  Installing OpenCode 1.14.35..."
npm install -g opencode-ai@1.14.35
echo "  ✓ OpenCode pinned to 1.14.35"
ensure_npm_global "@augmentcode/auggie@latest" "auggie"
ensure_npm_global "@tobilu/qmd" "qmd"
ensure_npm_global "@rynfar/meridian" "meridian" "--ignore-scripts"
ensure_npm_global "bun" "bun"

echo ""
echo "  Installing oh-my-openagent (ultrawork)..."
if bunx oh-my-openagent install --no-tui --claude=yes --openai=no --gemini=no --copilot=no --skip-auth; then
  echo "  ✓ oh-my-openagent ready"
else
  echo "  ! oh-my-openagent install failed - run manually: bunx oh-my-openagent install"
fi

echo ""
echo "  Installing claude-opencode launcher globally..."
NPM_BIN=$(npm prefix -g 2>/dev/null)/bin
if [ -n "$NPM_BIN" ]; then
  cp "$SCRIPT_DIR/claude-opencode.sh" "$NPM_BIN/claude-opencode"
  chmod +x "$NPM_BIN/claude-opencode"
  echo "  ✓ claude-opencode installed to $NPM_BIN"
else
  echo "  ! Could not determine npm global bin directory"
fi

if ! command -v claude >/dev/null 2>&1; then
  echo "  ! Claude Code CLI is not installed. Meridian needs 'claude login' later."
else
  echo ""
  echo "  Running meridian setup (configures OpenCode plugin)..."
  if meridian setup; then
    echo "  ✓ Meridian plugin configured for OpenCode"
  else
    echo "  ! meridian setup failed - run manually after 'claude login'"
  fi
fi

echo ""
echo "  Installing Superpowers for OpenCode..."
mkdir -p "$HOME/.config/opencode"
npm install "superpowers@git+https://github.com/obra/superpowers.git" --prefix "$HOME/.config/opencode"
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
python3 "$ROOT/tools/setup_workspace.py" --root "$ROOT" wizard --yes

echo ""
echo "  Setup complete!"
echo "  ─────────────────────────────────────────────────────────"
echo "  Next steps:"
echo "  1. Run 'claude login' if not already authenticated"
echo "  2. Launch OpenCode with 'claude-opencode' (Meridian starts automatically)"
echo "  3. In OpenCode, run /init-deep to generate AGENTS.md files across all repos"
echo "  4. Use './scripts/ws new <task> frontend backend' for cross-repo worktrees"
echo "  5. Copy Configo-Backend/.env.staging.example to Configo-Backend/.env.staging"
echo "  6. Fill in your staging credentials in Configo-Backend/.env.staging"
echo "  7. Run ./scripts/dev.sh to start all servers"
echo "  ─────────────────────────────────────────────────────────"
echo ""
