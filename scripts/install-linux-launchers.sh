#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
APPLICATIONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"

mkdir -p "$APPLICATIONS_DIR"

write_desktop_file() {
  local file_name="$1"
  local display_name="$2"
  local exec_path="$3"
  local comment="$4"

  cat >"$APPLICATIONS_DIR/$file_name" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=$display_name
Comment=$comment
Exec=$exec_path
Path=$ROOT
Terminal=true
Categories=Development;
StartupNotify=true
EOF
}

write_desktop_file \
  "configo-claude-workspace.desktop" \
  "Configo Claude Workspace" \
  "$ROOT/scripts/claude-workspace.sh" \
  "Launch Claude with the shared Configo workspace runtime"

write_desktop_file \
  "configo-opencode-workspace.desktop" \
  "Configo OpenCode Workspace" \
  "$ROOT/scripts/opencode-workspace.sh" \
  "Launch OpenCode with the shared Configo workspace runtime"

write_desktop_file \
  "configo-cross-resume.desktop" \
  "Configo Cross Resume" \
  "$ROOT/scripts/cross-resume.sh" \
  "List and resume shared Configo workspace conversations"

chmod +x \
  "$APPLICATIONS_DIR/configo-claude-workspace.desktop" \
  "$APPLICATIONS_DIR/configo-opencode-workspace.desktop" \
  "$APPLICATIONS_DIR/configo-cross-resume.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi

echo "Installed Linux app launchers in $APPLICATIONS_DIR:"
echo " - Configo Claude Workspace"
echo " - Configo OpenCode Workspace"
echo " - Configo Cross Resume"
