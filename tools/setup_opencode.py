from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
from pathlib import Path


def _cmd(name: str) -> str:
    return f"{name}.cmd" if platform.system() == "Windows" else name


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
        for c in candidates:
            if c.exists():
                return c
        return candidates[0]
    return Path.home() / ".config" / "opencode"

AUGGIE_MCP_NAME = "auggie"
_LEGACY_MCP_NAMES = ("augment-context-engine", "augment-context-engine-local")
QMD_MCP_NAME = "qmd-knowledge"
REMOTE_MCP_NAME = "augment-context-engine-remote"
MERIDIAN_BASE_URL = "http://127.0.0.1:3456"

CODE_REPOS = [
    "Configo-Backend",
    "Configo-AI-Worker",
    "Configo-Frontend",
    "Configo-Web-Frontend",
    "Configo-Developer-Frontend",
    "Configo-Deployment",
]

SKILL_NAMES = [
    "impeccable",
    "caveman",
    "caveman-commit",
    "caveman-compress",
    "caveman-help",
    "caveman-review",
    "caveman-stats",
]


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


def cleanup_legacy(root: Path) -> None:
    home = Path.home()
    _remove_path(home / ".claude" / "statusline-command.sh")
    _remove_path(home / ".config" / "opencode" / "plugins" / "superpowers.js")
    _remove_path(home / ".config" / "opencode" / "skills" / "superpowers")


def _code_workspace_paths(root: Path) -> list[Path]:
    return [root / repo for repo in CODE_REPOS if (root / repo).exists()]


def _local_mcp_command(root: Path) -> list[str]:
    workspaces = _code_workspace_paths(root)
    if not workspaces:
        workspaces = [root]

    command = [_cmd("auggie"), "--mcp", "-w", str(workspaces[0])]
    for repo_dir in workspaces[1:]:
        command.extend(["--add-workspace", str(repo_dir)])
    return command


def configure_claude_code(root: Path) -> None:
    home = Path.home()
    settings_path = home / ".claude" / "settings.json"
    settings = _load_json(settings_path)

    mcp_servers = settings.setdefault("mcpServers", {})
    for legacy in _LEGACY_MCP_NAMES:
        mcp_servers.pop(legacy, None)

    auggie_cmd = _local_mcp_command(root)
    mcp_servers[AUGGIE_MCP_NAME] = {
        "command": auggie_cmd[0],
        "args": auggie_cmd[1:],
    }
    mcp_servers[QMD_MCP_NAME] = {
        "command": _cmd("qmd"),
        "args": ["mcp"],
    }

    opencode_config = _load_json(_opencode_config_dir() / "opencode.json")
    ctx7 = opencode_config.get("mcp", {}).get("context7")
    if ctx7 and ctx7.get("type") == "remote" and ctx7.get("url"):
        entry: dict = {"type": "sse", "url": ctx7["url"]}
        if ctx7.get("headers"):
            entry["headers"] = ctx7["headers"]
        mcp_servers["context7"] = entry
    else:
        mcp_servers.pop("context7", None)

    _write_json(settings_path, settings)


def configure_opencode(root: Path, *, use_meridian: bool = True) -> None:
    cleanup_legacy(root)

    home = Path.home()
    opencode_dir = _opencode_config_dir()
    config_path = opencode_dir / "opencode.json"
    config = _load_json(config_path)

    config["$schema"] = "https://opencode.ai/config.json"
    config["autoupdate"] = False

    mcp = config.setdefault("mcp", {})
    for legacy in _LEGACY_MCP_NAMES:
        mcp.pop(legacy, None)

    mcp[AUGGIE_MCP_NAME] = {
        "type": "local",
        "command": _local_mcp_command(root),
        "enabled": True,
    }
    mcp[QMD_MCP_NAME] = {
        "type": "local",
        "command": [_cmd("qmd"), "mcp"],
        "enabled": True,
    }
    mcp.pop(REMOTE_MCP_NAME, None)

    plugin_path = _opencode_config_dir() / "node_modules" / "superpowers"
    plugins = list(config.get("plugin", []))
    plugin_str = str(plugin_path)
    if plugin_str not in plugins:
        plugins.append(plugin_str)
    config["plugin"] = plugins

    provider = config.setdefault("provider", {})
    anthropic = provider.setdefault("anthropic", {})
    anthropic_options = anthropic.setdefault("options", {})
    if use_meridian:
        anthropic_options["baseURL"] = MERIDIAN_BASE_URL
    else:
        anthropic_options.pop("baseURL", None)
        if not anthropic_options:
            anthropic.pop("options", None)

    permission = config.setdefault("permission", {})
    skill_permission = permission.setdefault("skill", {})
    for pattern in ("impeccable", "caveman*", "superpowers*", "context7"):
        skill_permission[pattern] = "allow"

    _write_json(config_path, config)
    configure_claude_code(root)

    agents_source = home / ".agents" / "skills"
    opencode_skills_dir = opencode_dir / "skills"
    opencode_skills_dir.mkdir(parents=True, exist_ok=True)
    for name in SKILL_NAMES:
        source = agents_source / name
        if source.exists():
            _replace_tree(source, opencode_skills_dir / name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("configure", "cleanup"))
    parser.add_argument("--root", required=True)
    parser.add_argument("--no-meridian", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if args.command == "cleanup":
        cleanup_legacy(root)
    else:
        configure_opencode(root, use_meridian=not args.no_meridian)


if __name__ == "__main__":
    main()
