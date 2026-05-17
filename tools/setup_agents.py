from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
from pathlib import Path

from runtime_manifest import plugins, repo_specs, server_names, skills_allow, system_prompt_appends, tool_profiles


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
# Includes pre-router per-repo `code-graph-<alias>` entries — the router collapses
# those into a single `code-graph` server that takes a `repo` parameter.
_LEGACY_MCP_NAMES = (
    "augment-context-engine",
    "augment-context-engine-local",
    "augment-context-engine-remote",
    "qmd-conversations",  # merged into qmd-knowledge
    "code-graph-backend",
    "code-graph-ai-worker",
    "code-graph-frontend",
    "code-graph-web-frontend",
    "code-graph-developer-frontend",
    "code-graph-deployment",
)


def _code_graph_rag_servers(root: Path) -> dict[str, dict]:
    """Single code-graph MCP entry that runs through tools/code_graph_router.py.

    The router spawns one upstream `npx @er77/code-graph-rag-mcp <root>`
    indexed over the whole workspace and adds an optional `repo` parameter
    to every tool, scoping query results to a sub-repo by file-path prefix.
    """
    from runtime_manifest import load_manifest

    cfg = (load_manifest(root).get("mcp") or {}).get("code_graph_rag") or {}
    if not cfg.get("enabled"):
        return {}
    package = cfg.get("package", "@er77/code-graph-rag-mcp")
    timeout_ms = cfg.get("timeout_ms", 80000)
    router_name = (cfg.get("router") or {}).get("name", "code-graph")
    router_script = root / "tools" / "code_graph_router.py"
    upstream_cmd, upstream_args = _spawn_cmd("npx", [package, str(root)])
    return {
        router_name: {
            "command": _python(),
            "args": [
                str(router_script),
                "--root",
                str(root),
                "--upstream",
                "--",
                upstream_cmd,
                *upstream_args,
            ],
            "env": {"MCP_TIMEOUT": str(timeout_ms)},
        }
    }


def _language_server_servers(root: Path) -> dict[str, dict]:
    """One mcp-language-server entry per language LSP defined in the manifest.

    Each entry runs `mcp-language-server --workspace <root> --lsp <bin> [extra]`,
    so a single Go process bridges any MCP client to the LSP. We point all of
    them at the workspace root — gopls / typescript-language-server / pyright
    all handle multi-module workspaces natively, so one MCP per language is
    enough to cover all six sub-repos.

    Skips any language whose LSP binary isn't on PATH (so installing only the
    LSPs you actually use is enough).
    """
    from runtime_manifest import load_manifest

    entries = (load_manifest(root).get("mcp") or {}).get("language_servers") or []
    if not entries:
        return {}
    bridge = shutil.which("mcp-language-server") or "mcp-language-server"
    out: dict[str, dict] = {}
    for entry in entries:
        name = entry.get("name")
        lsp = entry.get("lsp")
        if not name or not lsp:
            continue
        if shutil.which(lsp) is None:
            # LSP binary missing — skip silently so users can opt-in by installing.
            continue
        args = ["--workspace", str(root), "--lsp", lsp]
        extra = entry.get("extra_args") or []
        if extra:
            args.append("--")
            args.extend(extra)
        cmd, cmd_args = _spawn_cmd(bridge, args)
        out[name] = {"command": cmd, "args": cmd_args}
    return out


def _wrap_with_compactor(entry: dict, root: Path, model: str) -> dict:
    """Wrap an MCP server entry so the description-compactor middleware
    sits between the upstream and the MCP client. The middleware only
    mutates `tools/list` responses (rewriting descriptions terse via a
    local Ollama call); tool calls pass through untouched.
    """
    compactor = root / "tools" / "mcp_compactor.py"
    cmd = entry.get("command", "")
    args = list(entry.get("args", []))
    wrapped: dict = {
        "command": _python(),
        "args": [
            str(compactor),
            "--model",
            model,
            "--upstream",
            "--",
            cmd,
            *args,
        ],
    }
    if "env" in entry:
        wrapped["env"] = entry["env"]
    return wrapped


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
    servers.update(_code_graph_rag_servers(root))
    servers.update(_language_server_servers(root))
    opencode_config = _load_json(_opencode_config_dir() / "opencode.json")
    ctx7 = opencode_config.get("mcp", {}).get(names["context7"])
    if ctx7 and ctx7.get("type") == "remote" and ctx7.get("url"):
        entry: dict = {"type": "sse", "url": ctx7["url"]}
        if ctx7.get("headers"):
            entry["headers"] = ctx7["headers"]
        servers[names["context7"]] = entry

    # Wrap every local (stdio) entry with the description compactor so every
    # MCP client sees the same compressed tool descriptions. Remote/SSE entries
    # (like context7) pass through untouched — the compactor only speaks stdio.
    from runtime_manifest import load_manifest

    compactor_cfg = (load_manifest(root).get("mcp") or {}).get("description_compactor") or {}
    if compactor_cfg.get("enabled"):
        model = compactor_cfg.get("model", "llama3.2:3b")
        wrapped: dict[str, dict] = {}
        for name, entry in servers.items():
            # Skip non-stdio entries (SSE/remote MCP); they have no `command`.
            if "command" not in entry:
                wrapped[name] = entry
                continue
            wrapped[name] = _wrap_with_compactor(entry, root, model)
        servers = wrapped
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

    # Inject the combined skill body (caveman etc.) as a system-prompt
    # append via OpenCode's instructions[]. OpenCode reads each path on
    # every launch and prepends contents to the system prompt.
    append_path = _system_prompt_append_path(root)
    instructions = list(config.get("instructions", []))
    append_path_str = str(append_path)
    if append_path.exists():
        if append_path_str not in instructions:
            instructions.append(append_path_str)
    else:
        instructions = [p for p in instructions if p != append_path_str]
    if instructions:
        config["instructions"] = instructions
    else:
        config.pop("instructions", None)

    _write_json(config_path, config)

    home = Path.home()
    agents_source = home / ".agents" / "skills"
    opencode_skills_dir = opencode_dir / "skills"
    opencode_skills_dir.mkdir(parents=True, exist_ok=True)
    for name in ("impeccable", "caveman", "caveman-commit", "caveman-compress", "caveman-help", "caveman-review", "caveman-stats"):
        source = agents_source / name
        if source.exists():
            _replace_tree(source, opencode_skills_dir / name)


def _agents_skill_dir() -> Path:
    """Where Superpowers (and our setup) installs skills."""
    return Path.home() / ".agents" / "skills"


def _read_skill_body(name: str) -> str | None:
    """Return the body of ~/.agents/skills/<name>/SKILL.md without its YAML
    frontmatter, or None if the skill isn't installed.

    Frontmatter (between leading `---` markers) is metadata for the Skill
    tool, not content the model should read; we strip it so injected text
    is purely the prose the skill author wrote.
    """
    path = _agents_skill_dir() / name / "SKILL.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), -1)
        if end > 0:
            text = "\n".join(lines[end + 1 :]).lstrip("\n")
    return text.strip()


def _system_prompt_append_path(root: Path) -> Path:
    return root / "tools" / ".system_prompt_append.md"


def build_system_prompt_append(root: Path) -> Path | None:
    """Concatenate every skill body listed in `system_prompt_appends` into a
    single file at tools/.system_prompt_append.md. Returns the path, or None
    if no skills are configured / installed.

    Called by configure_all so the file is fresh after every setup. The two
    launchers read this file: Claude inlines its contents via
    --append-system-prompt; OpenCode references the path via instructions[].
    """
    names = system_prompt_appends(root)
    if not names:
        return None
    sections: list[str] = []
    for name in names:
        body = _read_skill_body(name)
        if not body:
            continue
        sections.append(f"# {name}\n\n{body}")
    if not sections:
        return None
    out = _system_prompt_append_path(root)
    out.write_text("\n\n---\n\n".join(sections) + "\n", encoding="utf-8")
    return out


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


def apply_profile(root: Path, profile_name: str) -> dict:
    """Filter the active MCP server set down to the named profile's whitelist.

    Writes the filtered set to both Claude Code's settings.json and OpenCode's
    opencode.json. The "all" profile (or a profile whose value is None/empty)
    restores the full set by calling configure_all().

    Returns a payload describing what was applied.
    """
    profiles = tool_profiles(root)
    if profile_name not in profiles:
        raise SystemExit(
            f"Unknown profile {profile_name!r}. Known profiles: {', '.join(sorted(profiles))}"
        )
    whitelist = profiles[profile_name]
    if not whitelist:
        # `all`-style profile: restore the full set.
        configure_all(root)
        return {"profile": profile_name, "kept": "all", "dropped": []}

    keep = set(whitelist)
    # Always keep the configo-ws bridge so the TUI / worktree tooling keeps
    # working regardless of profile. Drop this and you'd lose the cross-client
    # correlation MCP entirely.
    keep.add("configo-ws")

    dropped: list[str] = []
    # Filter Claude Code settings.
    settings_path = Path.home() / ".claude" / "settings.json"
    settings = _load_json(settings_path)
    servers = settings.get("mcpServers") or {}
    for name in list(servers):
        if name not in keep:
            dropped.append(name)
            servers.pop(name, None)
    settings["mcpServers"] = servers
    _write_json(settings_path, settings)

    # Filter OpenCode mirror.
    oc_config_path = _opencode_config_dir() / "opencode.json"
    oc_config = _load_json(oc_config_path)
    oc_mcp = oc_config.get("mcp") or {}
    for name in list(oc_mcp):
        if name not in keep:
            oc_mcp.pop(name, None)
    oc_config["mcp"] = oc_mcp
    _write_json(oc_config_path, oc_config)

    return {"profile": profile_name, "kept": sorted(keep), "dropped": sorted(set(dropped))}


def configure_all(root: Path) -> None:
    """Configure every supported coding-agent client: OpenCode, Claude Code, Kimi."""
    # Generate the shared system-prompt-append file first so the per-client
    # configurations below can reference it.
    build_system_prompt_append(root)
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
