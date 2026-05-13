from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

DEFAULT_REMOTE_MCP_URL = os.environ.get(
    "AUGMENT_REMOTE_MCP_URL",
    "https://api.augmentcode.com/mcp",
)
LEGACY_LOCAL_MCP_NAME = "augment-context-engine"
LOCAL_MCP_NAME = "augment-context-engine-local"
REMOTE_MCP_NAME = "augment-context-engine-remote"

REPOS = [
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
    _remove_path(root / ".engram-installed")
    _remove_path(root / "graphify-out")

    home = Path.home()
    _remove_path(home / ".mempalace")
    _remove_path(home / ".claude" / "statusline-command.sh")
    _remove_path(home / ".config" / "opencode" / "plugins" / "superpowers.js")
    _remove_path(home / ".config" / "opencode" / "skills" / "superpowers")

    for repo in REPOS:
        _remove_path(root / repo / "graphify-out")


def _workspace_paths(root: Path) -> list[Path]:
    workspaces = [root]
    for repo in REPOS:
        repo_dir = root / repo
        if repo_dir.exists():
            workspaces.append(repo_dir)
    return workspaces


def _local_mcp_command(root: Path) -> list[str]:
    command = ["auggie", "--mcp", "--mcp-auto-workspace", "-w", str(root)]
    for repo_dir in _workspace_paths(root)[1:]:
        command.extend(["--add-workspace", str(repo_dir)])
    return command


def configure_opencode(root: Path) -> None:
    cleanup_legacy(root)

    home = Path.home()
    opencode_dir = home / ".config" / "opencode"
    config_path = opencode_dir / "opencode.json"
    config = _load_json(config_path)

    config["$schema"] = "https://opencode.ai/config.json"

    mcp = config.setdefault("mcp", {})
    legacy_local = mcp.pop(LEGACY_LOCAL_MCP_NAME, None)

    local_server = {}
    if isinstance(legacy_local, dict) and legacy_local.get("type") == "local":
        local_server.update(legacy_local)
    if isinstance(mcp.get(LOCAL_MCP_NAME), dict):
        local_server.update(mcp[LOCAL_MCP_NAME])
    local_server.update(
        {
            "type": "local",
            "command": _local_mcp_command(root),
            "enabled": True,
        }
    )
    mcp[LOCAL_MCP_NAME] = local_server

    remote_server = {}
    if isinstance(mcp.get(REMOTE_MCP_NAME), dict):
        remote_server.update(mcp[REMOTE_MCP_NAME])
    remote_server.setdefault("type", "remote")
    remote_server.setdefault("url", DEFAULT_REMOTE_MCP_URL)
    remote_server.setdefault("enabled", True)
    mcp[REMOTE_MCP_NAME] = remote_server

    plugin_path = opencode_dir / "node_modules" / "superpowers"
    plugins = list(config.get("plugin", []))
    plugin_str = str(plugin_path)
    if plugin_str not in plugins:
        plugins.append(plugin_str)
    config["plugin"] = plugins

    permission = config.setdefault("permission", {})
    skill_permission = permission.setdefault("skill", {})
    for pattern in ("impeccable", "caveman*", "superpowers*", "context7"):
        skill_permission[pattern] = "allow"

    _write_json(config_path, config)

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
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if args.command == "cleanup":
        cleanup_legacy(root)
    else:
        configure_opencode(root)


if __name__ == "__main__":
    main()
