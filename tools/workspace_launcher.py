from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

import setup_agents
from session_runtime import opencode_finalize, prepare


def _resolve_binary(name: str) -> str:
    direct = shutil.which(name)
    if direct:
        return direct
    home = Path.home()
    candidates: dict[str, list[Path]] = {
        "claude": [
            home / ".local" / "bin" / "claude.exe",
            home / ".local" / "bin" / "claude",
        ],
        "opencode": [
            home / "AppData" / "Roaming" / "npm" / "opencode.cmd",
            home / "AppData" / "Roaming" / "npm" / "opencode",
        ],
        "kimi": [
            home / ".local" / "bin" / "kimi.exe",
            home / ".local" / "bin" / "kimi",
        ],
    }
    for candidate in candidates.get(name, []):
        if candidate.exists():
            return str(candidate)
    return name


def _tool_env() -> dict[str, str]:
    env = os.environ.copy()
    extras = [
        str(Path.home() / ".local" / "bin"),
        str(Path.home() / "AppData" / "Roaming" / "npm"),
    ]
    current = env.get("PATH", "")
    for extra in reversed(extras):
        if extra and extra not in current:
            current = extra + os.pathsep + current
    env["PATH"] = current
    return env


def _run(args: list[str], cwd: Path) -> int:
    return subprocess.run(args, cwd=str(cwd), env=_tool_env(), check=False).returncode


def _capture_json(args: list[str], cwd: Path) -> list[dict]:
    result = subprocess.run(args, cwd=str(cwd), env=_tool_env(), capture_output=True, text=True, check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, dict):
        payload = payload.get("items", payload.get("sessions", []))
    return payload if isinstance(payload, list) else []


def _extract_id(entry: dict) -> str | None:
    for key in ("id", "sessionID", "sessionId"):
        value = entry.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _explicit_session(args: list[str], flags: tuple[str, ...]) -> str | None:
    for index, item in enumerate(args):
        if item in flags and index + 1 < len(args):
            return args[index + 1]
        for flag in flags:
            if item.startswith(f"{flag}="):
                return item.split("=", 1)[1]
    return None


def _has_any_flag(args: list[str], flags: tuple[str, ...]) -> bool:
    return any(item in flags or any(item.startswith(f"{flag}=") for flag in flags) for item in args)


def _system_prompt_append_text(root: Path) -> str | None:
    """Read the combined skill body that setup_agents.build_system_prompt_append
    writes to tools/.system_prompt_append.md. Returns None if it doesn't exist
    or is empty."""
    path = root / "tools" / ".system_prompt_append.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return text or None


def launch_claude(root: Path, cwd: Path, passthrough: list[str], conversation: str | None) -> int:
    setup_agents.configure_all(root)
    explicit_session = _explicit_session(passthrough, ("-r", "--resume"))
    state = prepare(root, cwd, "claude", None, conversation, explicit_session)
    claude_bin = _resolve_binary("claude")
    leading: list[str] = []
    # Inject the shared system-prompt-append body (caveman etc.) unless the
    # caller already passed --append-system-prompt themselves.
    if not _has_any_flag(passthrough, ("--append-system-prompt",)):
        body = _system_prompt_append_text(root)
        if body:
            leading.extend(["--append-system-prompt", body])
    args = [claude_bin, *leading, *passthrough]
    if not _has_any_flag(passthrough, ("-r", "--resume", "-c", "--continue")) and state.get("native_session_id"):
        args = [claude_bin, *leading, "-r", state["native_session_id"], *passthrough]
    return _run(args, cwd)


def launch_kimi(root: Path, cwd: Path, passthrough: list[str], conversation: str | None) -> int:
    """Launch the Kimi CLI in `cwd` with workspace_conversation_id correlation.

    Kimi CLI also has no documented --append-system-prompt equivalent yet,
    so the shared skill-inject body (caveman etc.) is not injected here.
    The kimi-cli --agent-file flag is for a different purpose (custom agent
    definitions), not system-prompt prepending.

    Kimi has no machine-readable `session list` yet (upstream MoonshotAI/kimi-cli#83),
    so the launcher can't back-fill a freshly-created native session id the way it
    does for OpenCode. Instead:
      - If metadata has a stored kimi_session_id, pass --session <id> (resume).
      - Else, default to --continue (most-recent session in this cwd) — Kimi's
        native scope already matches "per-worktree", which is what we want.
      - If the caller already passed --session/--resume/--continue in passthrough,
        leave it alone.
    """
    setup_agents.configure_all(root)
    explicit_session = _explicit_session(passthrough, ("-S", "--session", "-r", "--resume"))
    state = prepare(root, cwd, "kimi", None, conversation, explicit_session)
    kimi_bin = _resolve_binary("kimi")
    args = [kimi_bin, *passthrough]
    has_resume_flag = _has_any_flag(passthrough, ("-S", "--session", "-r", "--resume", "--continue"))
    if not has_resume_flag:
        stored = state.get("native_session_id")
        if stored:
            args = [kimi_bin, "--session", stored, *passthrough]
        else:
            args = [kimi_bin, "--continue", *passthrough]
    return _run(args, cwd)


def launch_opencode(root: Path, cwd: Path, passthrough: list[str], conversation: str | None) -> int:
    setup_agents.configure_all(root)
    opencode_bin = _resolve_binary("opencode")
    before = _capture_json([opencode_bin, "session", "list", "--format", "json", "--max-count", "20"], cwd)
    before_ids = [_extract_id(item) for item in before if _extract_id(item)]
    explicit_session = _explicit_session(passthrough, ("-s", "--session"))
    state = prepare(root, cwd, "opencode", None, conversation, explicit_session)
    args = [opencode_bin, *passthrough]
    if not _has_any_flag(passthrough, ("-s", "--session", "-c", "--continue")) and state.get("native_session_id"):
        args = [opencode_bin, "--session", state["native_session_id"], *passthrough]
    exit_code = _run(args, cwd)
    opencode_finalize(root, cwd, state["workspace_conversation_id"], [item for item in before_ids if item], explicit_session)
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("client", choices=("claude", "opencode", "kimi"))
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--conversation")
    parsed, passthrough = parser.parse_known_args()
    root = Path(parsed.root).resolve()
    cwd = Path(parsed.cwd).resolve()
    if passthrough and passthrough[0] == "--":
        passthrough = passthrough[1:]
    if parsed.client == "claude":
        return launch_claude(root, cwd, passthrough, parsed.conversation)
    if parsed.client == "kimi":
        return launch_kimi(root, cwd, passthrough, parsed.conversation)
    return launch_opencode(root, cwd, passthrough, parsed.conversation)


if __name__ == "__main__":
    raise SystemExit(main())
