from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _emit_hook(event: str, message: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": message}}))


def _brief(root: Path) -> str:
    graph_report = root / "graphify" / "GRAPH_REPORT.md"
    settings = root / ".claude" / "settings.json"
    parts = [
        f"root={root.name}",
        f"graph={'ready' if graph_report.exists() else 'missing'}",
        f"claude-settings={'ready' if settings.exists() else 'missing'}",
    ]
    return " | ".join(parts)


def _post_edit_message() -> str:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    file_path = payload.get("tool_input", {}).get("file_path", "the edited file")
    return (
        f"You just edited {file_path}. Write or update a test that covers this change, "
        "and run the relevant verification before continuing."
    )


def _run_mempalace(*args: str, timeout: int = 10) -> str | None:
    executable = shutil.which("mempalace")
    if not executable:
        return None
    try:
        result = subprocess.run(
            [executable, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    output = result.stdout.strip()
    return output or None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brief", action="store_true")
    parser.add_argument("--fix", action="store_true")
    parser.add_argument("--pretool-json", action="store_true")
    parser.add_argument("--sessionstart-json", action="store_true")
    parser.add_argument("--post-edit-json", action="store_true")
    parser.add_argument("--stop-json", action="store_true")
    args = parser.parse_args()

    root = _root()

    if args.fix:
        graph_dir = root / "graphify"
        graph_dir.mkdir(exist_ok=True)
        print(f"Ensured graphify directory at {graph_dir}")
        return

    if args.pretool_json:
        graph_json = root / "graphify-out" / "graph.json"
        if not graph_json.exists():
            graph_json = root / "graphify" / "graph.json"
        if graph_json.exists():
            _emit_hook(
                "PreToolUse",
                "graphify: Knowledge graph exists. Read graphify/GRAPH_REPORT.md before deep raw-file searching.",
            )
        return

    if args.sessionstart_json:
        wake_up = _run_mempalace("wake-up")
        message = _brief(root)
        if wake_up:
            message = f"{message}\nmempalace wake-up:\n{wake_up}"
        _emit_hook("SessionStart", message)
        return

    if args.post_edit_json:
        _emit_hook("PostToolUse", _post_edit_message())
        return

    if args.stop_json:
        projects_dir = Path.home() / ".claude" / "projects"
        _run_mempalace(
            "mine",
            str(projects_dir),
            "--mode",
            "convos",
            "--wing",
            "claude-sessions",
            timeout=30,
        )
        _emit_hook("Stop", "Session complete. If graph-sensitive files changed, run scripts/update-graph.")
        return

    if args.brief:
        print(_brief(root))
        return

    print(_brief(root))


if __name__ == "__main__":
    main()
