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

echo ""
echo "  Configo Workspace Setup"
echo "  $(date '+%H:%M:%S')"
echo ""

require_cmd git
require_cmd python3
require_cmd node
require_cmd npm

# Repository URLs
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
echo "  Installing OpenCode..."
if ! command -v opencode >/dev/null 2>&1; then
  npm install -g opencode-ai
  echo "  ✓ OpenCode installed"
else
  echo "  ✓ OpenCode already installed"
fi

echo ""
echo "  Installing Auggie CLI..."
if ! command -v auggie >/dev/null 2>&1; then
  npm install -g @augmentcode/auggie@latest
  echo "  ✓ Auggie installed"
else
  echo "  ✓ Auggie already installed"
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
echo "  Configuring OpenCode..."
python3 "$ROOT/tools/setup_opencode.py" configure --root "$ROOT"
echo "  ✓ OpenCode configured"

echo ""
echo "  Setup complete!"
echo "  ─────────────────────────────────────────────────────────"
echo "  Next steps:"
echo "  1. Run 'auggie login' if this machine is not already authenticated"
echo "  2. Install the Augment GitHub App and select the Configo repos for remote indexing"
echo "  3. Open OpenCode and confirm both 'augment-context-engine-local' and 'augment-context-engine-remote' are enabled"
echo "  4. Copy Configo-Backend/.env.staging.example to Configo-Backend/.env.staging"
echo "  5. Fill in your staging credentials in Configo-Backend/.env.staging"
echo "  6. Run ./scripts/dev.sh to start all servers"
echo "  ─────────────────────────────────────────────────────────"
echo ""
