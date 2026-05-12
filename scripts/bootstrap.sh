#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
export CONFIGO_ROOT="$ROOT"
OS_NAME="$(uname -s)"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== Configo Workspace Bootstrap ===${NC}"
echo "Root: $ROOT"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo -e "${YELLOW}Missing required command: $1${NC}"
    return 1
  fi
}

install_hint() {
  local package="$1"
  if command -v brew >/dev/null 2>&1; then
    echo "Install with: brew install $package"
  elif command -v apt-get >/dev/null 2>&1; then
    echo "Install with: sudo apt-get install -y $package"
  elif command -v dnf >/dev/null 2>&1; then
    echo "Install with: sudo dnf install -y $package"
  elif command -v pacman >/dev/null 2>&1; then
    echo "Install with: sudo pacman -S --noconfirm $package"
  else
    echo "Install $package with your system package manager and re-run bootstrap."
  fi
}

has_obsidian() {
  command -v obsidian >/dev/null 2>&1 || [[ -d "/Applications/Obsidian.app" ]] || [[ -d "$HOME/Applications/Obsidian.app" ]]
}

install_python_package() {
  local package="$1"
  python3 -m pip show "$package" >/dev/null 2>&1 || python3 -m pip install --user --quiet "$package"
}

require_cmd git
require_cmd python3

if ! python3 -m pip --version >/dev/null 2>&1; then
  echo -e "${YELLOW}pip for python3 is required. Install pip and re-run bootstrap.${NC}"
  install_hint python3-pip
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo -e "${YELLOW}GitHub CLI is required. Install gh and re-run bootstrap.${NC}"
  install_hint gh
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo -e "${YELLOW}GitHub CLI is not authenticated. Run 'gh auth login' and re-run bootstrap.${NC}"
  exit 1
fi

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo -e "${YELLOW}Node.js and npm are required. Install them and re-run bootstrap.${NC}"
  install_hint node
  exit 1
fi

if ! command -v claude >/dev/null 2>&1; then
  echo "Installing Claude Code..."
  npm install -g @anthropic-ai/claude-code
fi

if ! command -v jq >/dev/null 2>&1; then
  echo -e "${YELLOW}jq is recommended for some tooling but not required. Install manually if needed.${NC}"
  install_hint jq
fi

if ! has_obsidian; then
  echo -e "${YELLOW}Obsidian is not installed. Install manually if you want the shared vault UI.${NC}"
  if command -v brew >/dev/null 2>&1; then
    echo "Install with: brew install --cask obsidian"
  elif [[ "$OS_NAME" == "Darwin" ]]; then
    echo "Install from: https://obsidian.md/download"
  fi
fi

install_python_package graphify
install_python_package mempalace

ENGRAM_MARKER="$ROOT/.engram-installed"
if [ ! -f "$ENGRAM_MARKER" ]; then
  echo -e "${YELLOW}Engram is not installed by this script on Unix unless you do it manually.${NC}"
fi

python3 "$ROOT/tools/bootstrap_workspace.py" configure-home --root "$ROOT" --platform unix
python3 "$ROOT/tools/bootstrap_workspace.py" install-repo-support --root "$ROOT" --platform unix

if [ ! -f "$ROOT/graphify/GRAPH_REPORT.md" ]; then
  "$ROOT/scripts/update-graph.sh" --silent
fi

echo -e "${GREEN}Bootstrap complete.${NC}"
echo "Next steps:"
echo "  1. Copy Configo-Backend/.env.staging.example to Configo-Backend/.env.staging"
echo "  2. Fill in staging credentials"
echo "  3. Run ./scripts/dev.sh"
