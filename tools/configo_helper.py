"""Top-level entry point for the Configo workspace helper.

Installed onto PATH by `setup_agents.install_configo_helper` so you can run
`configo-helper` from any directory. Defaults to opening the TUI; designed
to grow more subcommands (doctor, status, etc.) without breaking the bare
command.

Subcommands:
  tui       Open the three-pane workspace TUI (default)
  doctor    Run the workspace doctor (setup_workspace.doctor)
  status    Print a one-line workspace summary
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Force UTF-8 so any rich output (panels, glyphs) renders on Windows.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _default_root() -> Path:
    """Resolve the workspace root.

    Priority:
      1. $CONFIGO_REPO_ROOT (set by the installer shim)
      2. The parent of this file's directory (works when run from a checkout)
    """
    import os

    explicit = os.environ.get("CONFIGO_REPO_ROOT")
    if explicit:
        return Path(explicit).resolve()
    return Path(__file__).resolve().parents[1]


def _cmd_tui(root: Path, _rest: list[str]) -> int:
    import workspace_tui

    sys.argv = ["workspace_tui.py", "--root", str(root)]
    return workspace_tui.main()


def _cmd_doctor(root: Path, _rest: list[str]) -> int:
    import setup_workspace

    return setup_workspace.doctor(root)


def _cmd_new(root: Path, rest: list[str]) -> int:
    import argparse as _argparse
    import os as _os

    import session_runtime

    inner = _argparse.ArgumentParser(prog="configo-helper new")
    inner.add_argument("--cwd", default=_os.getcwd(), help="Scope (cwd) to activate the new conversation for.")
    inner.add_argument("--no-activate", action="store_true", help="Mint an id but don't make it active for this scope.")
    parsed = inner.parse_args(rest)
    payload = session_runtime.create_conversation(
        root,
        Path(parsed.cwd).resolve(),
        activate_for_scope=not parsed.no_activate,
    )
    verb = "Active" if payload["activated"] else "Created"
    print(f"{verb} workspace conversation: {payload['workspace_conversation_id']} (scope: {payload['scope_key']})")
    return 0


def _cmd_status(root: Path, _rest: list[str]) -> int:
    import session_runtime
    from runtime_manifest import repo_specs

    repos = repo_specs(root)
    cloned = sum(1 for spec in repos if (root / spec.directory).exists())
    convs = session_runtime.list_conversations(root, root)
    worktrees_dir = root / ".worktrees"
    wt_count = sum(1 for child in worktrees_dir.iterdir() if child.is_dir()) if worktrees_dir.exists() else 0
    print(f"root: {root}")
    print(f"repos: {cloned}/{len(repos)} cloned")
    print(f"conversations: {len(convs)}")
    print(f"worktrees: {wt_count}")
    return 0


COMMANDS = {
    "tui": _cmd_tui,
    "doctor": _cmd_doctor,
    "status": _cmd_status,
    "new": _cmd_new,
}


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="configo-helper",
        description="Configo workspace helper — TUI, doctor, status.",
    )
    parser.add_argument("--root", default=None, help="Workspace root (defaults to $CONFIGO_REPO_ROOT or repo checkout).")
    parser.add_argument("command", nargs="?", default="tui", choices=sorted(COMMANDS.keys()))
    parsed, rest = parser.parse_known_args()
    root = Path(parsed.root).resolve() if parsed.root else _default_root()
    if not root.exists():
        sys.stderr.write(f"configo-helper: workspace root not found: {root}\n")
        return 2
    return COMMANDS[parsed.command](root, rest)


if __name__ == "__main__":
    sys.exit(main())
