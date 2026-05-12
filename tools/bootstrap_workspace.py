from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPOS = [
    "Configo-Backend",
    "Configo-AI-Worker",
    "Configo-Frontend",
    "Configo-Web-Frontend",
    "Configo-Developer-Frontend",
    "Configo-Deployment",
]

REPO_DOCS = {
    "Configo-Backend": "backend",
    "Configo-AI-Worker": "ai-worker",
    "Configo-Frontend": "frontend",
    "Configo-Web-Frontend": "web-frontend",
    "Configo-Developer-Frontend": "developer-frontend",
    "Configo-Deployment": "deployment",
}


def _copy_tree(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def _ensure_graph_link(root: Path, link_path: Path, platform: str) -> None:
    target = root / "graphify"
    if link_path.exists() or link_path.is_symlink():
        return
    if platform == "windows":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link_path), str(target)],
            check=False,
            cwd=root,
        )
        if not link_path.exists():
            shutil.copytree(target, link_path)
    else:
        link_path.symlink_to(target, target_is_directory=True)


def configure_home(root: Path, platform: str) -> None:
    palace_path = root / ".mempalace" / "palace"
    palace_path.mkdir(parents=True, exist_ok=True)

    home = Path.home()
    mempalace_dir = home / ".mempalace"
    mempalace_dir.mkdir(parents=True, exist_ok=True)
    (mempalace_dir / "config.json").write_text(
        json.dumps(
            {
                "palace_path": str(palace_path),
                "collection_name": "mempalace_drawers",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    settings_path = claude_dir / "settings.json"
    if settings_path.exists():
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    else:
        settings = {}

    python_exe = sys.executable
    statusline = root / "tools" / "statusline.py"
    watchdog = root / "tools" / "context_watchdog.py"
    settings.setdefault("mcpServers", {})["mempalace"] = {
        "command": python_exe,
        "args": ["-m", "mempalace.mcp_server"],
        "env": {"MEMPALACE_PALACE_PATH": str(palace_path)},
    }
    settings["statusLine"] = {
        "type": "command",
        "command": f'"{python_exe}" "{statusline}"',
    }
    settings["hooks"] = {
        "SessionStart": [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": f'"{python_exe}" "{watchdog}" --sessionstart-json --brief',
                        "timeout": 10000,
                    }
                ],
            }
        ],
        "PostToolUse": [
            {
                "matcher": "Edit|Write|NotebookEdit",
                "hooks": [
                    {
                        "type": "command",
                        "command": f'"{python_exe}" "{watchdog}" --post-edit-json',
                    }
                ],
            }
        ],
        "Stop": [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": f'"{python_exe}" "{watchdog}" --stop-json',
                        "timeout": 30000,
                    }
                ],
            }
        ],
    }
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def install_repo_support(root: Path, platform: str) -> None:
    root_graph_link = root / "graphify-out"
    _ensure_graph_link(root, root_graph_link, platform)

    source_settings = root / ".claude" / "settings.json"
    source_skills = root / ".claude" / "skills"
    source_hook = root / "hooks" / "post-commit"

    for repo in REPOS:
        repo_dir = root / repo
        if not repo_dir.exists():
            continue

        claude_dir = repo_dir / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)

        if source_settings.exists():
            shutil.copy2(source_settings, claude_dir / "settings.json")
        if source_skills.exists():
            _copy_tree(source_skills, claude_dir / "skills")

        git_hook_dir = repo_dir / ".git" / "hooks"
        if git_hook_dir.exists() and source_hook.exists():
            shutil.copy2(source_hook, git_hook_dir / "post-commit")

        _ensure_graph_link(root, repo_dir / "graphify-out", platform)


def write_claude_md(root: Path) -> None:
    root_content = f"""# Configo — AI Context

## VIGTIGT: Brug altid Github-Configo root knowledge
Før du skriver ny kode skal du altid konsultere:
1. Arkitektur og docs i `{root / 'backend'}` og de øvrige repo-specifikke knowledge-mapper
2. Konventioner og repo-regler i de relevante lower-case knowledge-mapper
3. Knowledge graph i `{root / 'graphify' / 'GRAPH_REPORT.md'}`

## Knowledge Graph
- Full report: {root / 'graphify' / 'GRAPH_REPORT.md'}
- Interactive: {root / 'graphify' / 'graph.html'}

## Documentation
- Index: {root / 'index.md'}
- Backend: {root / 'backend'}
- Frontend: {root / 'frontend'}
- Web Frontend: {root / 'web-frontend'}
- Developer Frontend: {root / 'developer-frontend'}
- AI Worker: {root / 'ai-worker'}
- Deployment: {root / 'deployment'}
"""
    (root / "CLAUDE.md").write_text(root_content, encoding="utf-8")

    for repo, doc_key in REPO_DOCS.items():
        repo_dir = root / repo
        if not repo_dir.exists():
            continue
        content = f"""# {repo} — AI Context

## VIGTIGT: Brug altid Github-Configo root knowledge
Før du skriver ny kode skal du konsultere:
1. Konventioner: {root / doc_key / 'conventions'}
2. Kontekst og regler: {root / doc_key / 'context' / 'RULES.md'}
3. Knowledge graph: {root / 'graphify' / 'GRAPH_REPORT.md'}

## Dokumentation for dette repo
- {root / doc_key}
"""
        (repo_dir / "CLAUDE.md").write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("configure-home", "install-repo-support"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--root", required=True)
        sub.add_argument("--platform", choices=("windows", "unix"), required=True)

    write_parser = subparsers.add_parser("write-claude-md")
    write_parser.add_argument("--root", required=True)

    args = parser.parse_args()

    if args.command == "configure-home":
        configure_home(Path(args.root), args.platform)
    elif args.command == "install-repo-support":
        install_repo_support(Path(args.root), args.platform)
    elif args.command == "write-claude-md":
        write_claude_md(Path(args.root))


if __name__ == "__main__":
    main()
