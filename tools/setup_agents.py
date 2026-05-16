from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
from pathlib import Path

from runtime_manifest import plugins, repo_specs, server_names, skills_allow


def _cmd(name: str) -> str:
    return f"{name}.cmd" if platform.system() == "Windows" else name


def _python() -> str:
    return "python" if platform.system() == "Windows" else "python3"


def _spawn_cmd(name: str, args: list[str]) -> tuple[str, list[str]]:
    """Return (command, args) for spawning a CLI tool over stdio.

    On Windows we wrap `.cmd` shims with `cmd /c` because many MCP clients
    spawn child processes without a shell, which can break stdio pipes on
    `.cmd` files (Connection closed -32000).
    """
    if platform.system() == "Windows":
        return "cmd", ["/c", name, *args]
    return name, args


def _opencode_config_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "opencode"
    if system == "Darwin":
        candidates = [
            Path.home() / "Library" / "Application Support" / "opencode",
            Path.home() / ".config" / "opencode",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]
    return Path.home() / ".config" / "opencode"


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _replace_tree(source: Path, target: Path) -> None:
    if target.is_symlink() or target.exists():
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()
    shutil.copytree(source, target)


def _remove_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    shutil.rmtree(path)


def cleanup_legacy() -> None:
    home = Path.home()
    _remove_path(home / ".claude" / "statusline-command.sh")
    _remove_path(home / ".config" / "opencode" / "plugins" / "superpowers.js")
    _remove_path(home / ".config" / "opencode" / "skills" / "superpowers")


def _code_workspace_paths(root: Path) -> list[Path]:
    return [root / repo.directory for repo in repo_specs(root) if (root / repo.directory).exists()]


def _auggie_args(root: Path) -> list[str]:
    workspaces = _code_workspace_paths(root)
    if not workspaces:
        workspaces = [root]
    args = ["--mcp", "-w", str(workspaces[0])]
    for repo_dir in workspaces[1:]:
        args.extend(["--add-workspace", str(repo_dir)])
    return args


def _hook_command(root: Path) -> str:
    script = root / "tools" / "session_runtime.py"
    return f'{_python()} "{script}" claude-hook --root "{root}"'


# MCP server names that are no longer used; cleaned up from any client config we touch.
_LEGACY_MCP_NAMES = (
    "augment-context-engine",
    "augment-context-engine-local",
    "augment-context-engine-remote",
    "qmd-conversations",  # merged into qmd-knowledge (single qmd mcp exposes all collections)
)


def _build_mcp_servers(root: Path, names: dict[str, str]) -> dict[str, dict]:
    """Build the Claude-Code-style `mcpServers` dict shared across MCP clients."""
    auggie_cmd, auggie_args = _spawn_cmd("auggie", _auggie_args(root))
    qmd_cmd, qmd_args = _spawn_cmd("qmd", ["mcp"])
    ws_script = root / "tools" / "ws_mcp.py"
    servers: dict[str, dict] = {
        names["auggie"]: {"command": auggie_cmd, "args": auggie_args},
        names["qmd_knowledge"]: {"command": qmd_cmd, "args": qmd_args},
        names["ws"]: {
            "command": _python(),
            "args": [str(ws_script), "--root", str(root)],
        },
    }
    opencode_config = _load_json(_opencode_config_dir() / "opencode.json")
    ctx7 = opencode_config.get("mcp", {}).get(names["context7"])
    if ctx7 and ctx7.get("type") == "remote" and ctx7.get("url"):
        entry: dict = {"type": "sse", "url": ctx7["url"]}
        if ctx7.get("headers"):
            entry["headers"] = ctx7["headers"]
        servers[names["context7"]] = entry
    return servers


def configure_claude_code(root: Path) -> None:
    home = Path.home()
    settings_path = home / ".claude" / "settings.json"
    settings = _load_json(settings_path)

    names = server_names(root)
    mcp_servers = settings.setdefault("mcpServers", {})
    for legacy in _LEGACY_MCP_NAMES:
        mcp_servers.pop(legacy, None)
    mcp_servers.update(_build_mcp_servers(root, names))

    permissions = settings.setdefault("permissions", {})
    allow = permissions.setdefault("allow", [])
    mcp_server_names = set(mcp_servers.keys()) | set(names.values())
    raw_entries = skills_allow(root)
    translated: list[str] = []
    for item in raw_entries:
        bare = item.rstrip("*")
        if bare in mcp_server_names:
            translated.append(f"mcp__{bare}")
        else:
            translated.append(f"Skill({item})")
    # Drop any legacy raw entries that this script wrote in older runs.
    legacy = set(raw_entries)
    permissions["allow"] = [entry for entry in allow if entry not in legacy]
    allow = permissions["allow"]
    for entry in translated:
        if entry not in allow:
            allow.append(entry)

    statusline_script = root / "tools" / "statusline.py"
    if statusline_script.exists():
        settings["statusLine"] = {
            "type": "command",
            "command": f'{_python()} "{statusline_script}"',
            "padding": 0,
        }

    hooks = settings.setdefault("hooks", {})
    hook_command = _hook_command(root)
    session_start_entries = hooks.setdefault("SessionStart", [])
    start_config = {"matcher": "startup", "hooks": [{"type": "command", "command": hook_command}]}
    if start_config not in session_start_entries:
        session_start_entries.append(start_config)
    for event in ("Stop", "SessionEnd"):
        entries = hooks.setdefault(event, [])
        config = {"hooks": [{"type": "command", "command": hook_command}]}
        if config not in entries:
            entries.append(config)

    _write_json(settings_path, settings)


def configure_kimi(root: Path) -> None:
    """Mirror the MCP server config into `~/.kimi/mcp.json` for Kimi Code CLI.

    Kimi's mcp.json uses Claude Code's exact schema, so the dict produced
    by `_build_mcp_servers` is reused verbatim. Kimi auto-discovers skills
    from `~/.claude/skills/` and `~/.agents/skills/` by default, so no
    extra config is needed for skill parity. Hooks/statusline aren't wired
    yet (kimi's hook schema is beta and undocumented; no statusline knob).
    """
    if not shutil.which("kimi"):
        return
    mcp_path = Path.home() / ".kimi" / "mcp.json"
    config = _load_json(mcp_path)
    servers = config.setdefault("mcpServers", {})
    for legacy in _LEGACY_MCP_NAMES:
        servers.pop(legacy, None)
    names = server_names(root)
    servers.update(_build_mcp_servers(root, names))
    _write_json(mcp_path, config)


def configure_opencode(root: Path) -> None:
    cleanup_legacy()
    opencode_dir = _opencode_config_dir()
    config_path = opencode_dir / "opencode.json"
    config = _load_json(config_path)
    config["$schema"] = "https://opencode.ai/config.json"
    config["autoupdate"] = False

    names = server_names(root)
    mcp = config.setdefault("mcp", {})
    for legacy in _LEGACY_MCP_NAMES:
        mcp.pop(legacy, None)
    auggie_cmd, auggie_args = _spawn_cmd("auggie", _auggie_args(root))
    mcp[names["auggie"]] = {
        "type": "local",
        "command": [auggie_cmd, *auggie_args],
        "enabled": True,
    }
    qmd_cmd, qmd_args = _spawn_cmd("qmd", ["mcp"])
    mcp[names["qmd_knowledge"]] = {
        "type": "local",
        "command": [qmd_cmd, *qmd_args],
        "enabled": True,
    }
    ws_script = root / "tools" / "ws_mcp.py"
    mcp[names["ws"]] = {
        "type": "local",
        "command": [_python(), str(ws_script), "--root", str(root)],
        "enabled": True,
    }

    plugin_path = _opencode_config_dir() / "node_modules" / plugins(root)[0]
    plugin_values = list(config.get("plugin", []))
    if str(plugin_path) not in plugin_values:
        plugin_values.append(str(plugin_path))
    config["plugin"] = plugin_values

    provider = config.setdefault("provider", {})
    anthropic = provider.setdefault("anthropic", {})
    anthropic.pop("apiKey", None)
    options = anthropic.setdefault("options", {})
    options.pop("baseURL", None)
    if not options:
        anthropic.pop("options", None)

    permission = config.setdefault("permission", {})
    skill_permission = permission.setdefault("skill", {})
    for pattern in skills_allow(root):
        skill_permission[pattern] = "allow"

    _write_json(config_path, config)

    home = Path.home()
    agents_source = home / ".agents" / "skills"
    opencode_skills_dir = opencode_dir / "skills"
    opencode_skills_dir.mkdir(parents=True, exist_ok=True)
    for name in ("impeccable", "caveman", "caveman-commit", "caveman-compress", "caveman-help", "caveman-review", "caveman-stats"):
        source = agents_source / name
        if source.exists():
            _replace_tree(source, opencode_skills_dir / name)


def _configo_helper_target_dir() -> Path:
    """Where the `configo-helper` shim is installed.

    Picks an existing PATH-friendly directory:
      - Windows: %APPDATA%\\npm (alongside opencode.cmd / qmd.cmd / auggie.cmd)
      - macOS/Linux: ~/.local/bin (a well-known XDG-style user bin dir)
    """
    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "npm"
    return Path.home() / ".local" / "bin"


def install_configo_helper(root: Path) -> None:
    """Drop a shim onto PATH so `configo-helper` works from any directory.

    The shim bakes in the absolute repo path via CONFIGO_REPO_ROOT so the
    helper doesn't need to guess where the workspace lives.
    """
    helper = root / "tools" / "configo_helper.py"
    target_dir = _configo_helper_target_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    if platform.system() == "Windows":
        shim_path = target_dir / "configo-helper.cmd"
        contents = (
            "@echo off\r\n"
            "setlocal\r\n"
            f"set CONFIGO_REPO_ROOT={root}\r\n"
            f'python "{helper}" %*\r\n'
        )
        shim_path.write_text(contents, encoding="utf-8")
    else:
        shim_path = target_dir / "configo-helper"
        contents = (
            "#!/bin/sh\n"
            f'export CONFIGO_REPO_ROOT="{root}"\n'
            f'exec python3 "{helper}" "$@"\n'
        )
        shim_path.write_text(contents, encoding="utf-8")
        shim_path.chmod(0o755)


def configure_all(root: Path) -> None:
    """Configure every supported coding-agent client: OpenCode, Claude Code, Kimi."""
    configure_opencode(root)
    configure_claude_code(root)
    configure_kimi(root)
    install_configo_helper(root)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("configure", "cleanup"))
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if args.command == "cleanup":
        cleanup_legacy()
    else:
        configure_all(root)


if __name__ == "__main__":
    main()
