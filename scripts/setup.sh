#!/bin/bash
# Configo Workspace Setup Script
# Clones all Configo repositories if they don't exist

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

echo ""
echo "  Configo Workspace Setup"
echo "  $(date '+%H:%M:%S')"
echo ""

# Repository URLs
REPOS=(
  "Configo-Backend:https://github.com/Configo-ai/Configo-Backend.git"
  "Configo-AI-Worker:https://github.com/Configo-ai/Configo-AI-Worker.git"
  "Configo-Frontend:https://github.com/Configo-ai/Configo-Frontend.git"
  "Configo-Web-Frontend:https://github.com/Configo-ai/Configo-Web-Frontend.git"
  "Configo-Developer-Frontend:https://github.com/Configo-ai/Configo-Developer-Frontend.git"
  "Configo-Deployment:https://github.com/Configo-ai/Configo-Deployment.git"
  "configo-knowledge:https://github.com/Configo-ai/configo-knowledge.git"
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
echo "  Setup complete!"
echo "  ─────────────────────────────────────────────────────────"
echo "  Next steps:"
echo "  1. Copy Configo-Backend/.env.staging.example to Configo-Backend/.env.staging"
echo "  2. Fill in your staging credentials in Configo-Backend/.env.staging"
echo "  3. Run ./scripts/dev.sh to start all servers"
echo "  ─────────────────────────────────────────────────────────"
echo ""
