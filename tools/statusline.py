"""Cross-platform statusline for Claude Code (and OpenCode if it adopts the same contract).

Reads a single JSON object from stdin describing the session and prints a
one-line status string to stdout. Designed to be fast — Claude Code may call
this on every redraw.

JSON input shape (from Claude Code, fields may be absent):
    {"session_id": "...", "transcript_path": "...", "cwd": "...",
     "model": {"id": "...", "display_name": "..."},
     "workspace": {"current_dir": "...", "project_dir": "..."}, ...}
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _git_branch(cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _cwd_label(cwd_str: str) -> str:
    if not cwd_str:
        return ""
    p = Path(cwd_str)
    home = Path.home()
    try:
        rel = p.relative_to(home)
        return f"~/{rel.as_posix()}" if rel.parts else "~"
    except ValueError:
        return p.as_posix()


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    data: dict = {}
    if raw.strip():
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}

    model = (data.get("model") or {})
    model_name = model.get("display_name") or model.get("id") or ""

    cwd_str = (
        (data.get("workspace") or {}).get("current_dir")
        or data.get("cwd")
        or os.getcwd()
    )
    cwd = Path(cwd_str) if cwd_str else Path.cwd()
    branch = _git_branch(cwd)
    cwd_label = _cwd_label(str(cwd))

    parts = [s for s in (model_name, (f"⎇ {branch}" if branch else ""), cwd_label) if s]
    sys.stdout.write(" │ ".join(parts))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
