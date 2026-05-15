from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.fastmcp import FastMCP
import setup_workspace as ws

_mcp = FastMCP("configo-ws")
_root: Path = Path(__file__).resolve().parents[1]


@_mcp.tool()
def worktree_new(task: str, repos: list[str]) -> str:
    """Create cross-repo git worktrees for a task. repos is a list of aliases e.g. ['backend', 'frontend']."""
    try:
        specs = ws._repo_specs_for_args(repos)
    except SystemExit as e:
        return f"Error: {e}"

    task_dir = _root / ".worktrees" / task
    task_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    errors: list[str] = []

    for spec in specs:
        repo_dir = ws._repo_dir(_root, spec)
        if not (repo_dir / ".git").exists():
            errors.append(f"{spec.alias}: repo not found at {repo_dir}")
            continue
        target = task_dir / spec.alias
        if target.exists():
            created.append(f"{spec.alias} (already exists)")
            continue
        try:
            ws._run(["git", "fetch", "--all", "--prune"], cwd=repo_dir)
            branch_check = ws._run(
                ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{task}"],
                cwd=repo_dir,
                check=False,
            )
            if branch_check.returncode == 0:
                ws._run(["git", "worktree", "add", str(target), task], cwd=repo_dir)
            else:
                ws._run(
                    ["git", "worktree", "add", "-b", task, str(target), f"origin/{spec.default_branch}"],
                    cwd=repo_dir,
                )
            created.append(spec.alias)
        except Exception as e:
            errors.append(f"{spec.alias}: {e}")

    ws._create_task_agents(_root, task_dir, specs)

    parts: list[str] = []
    if created:
        parts.append(f"Worktree '{task}' ready: {', '.join(created)}")
    if errors:
        parts.append(f"Errors: {'; '.join(errors)}")
    parts.append(f"Path: {task_dir}")
    return "\n".join(parts)


@_mcp.tool()
def worktree_list() -> str:
    """List all active task worktrees."""
    worktrees_dir = _root / ".worktrees"
    if not worktrees_dir.exists():
        return "No worktrees found."
    tasks = [d.name for d in sorted(worktrees_dir.iterdir()) if d.is_dir()]
    return "\n".join(tasks) if tasks else "No worktrees found."


@_mcp.tool()
def worktree_status(task: str) -> str:
    """Show git status across all repos in a task worktree."""
    task_dir = _root / ".worktrees" / task
    if not task_dir.exists():
        return f"Task workspace not found: {task_dir}"
    lines: list[str] = []
    for repo_dir in sorted(task_dir.iterdir()):
        if not repo_dir.is_dir():
            continue
        result = ws._run(
            ["git", "status", "--short", "--branch"],
            cwd=repo_dir,
            check=False,
            capture=True,
        )
        lines.append(f"== {repo_dir.name} ==")
        lines.append(result.stdout.strip())
    return "\n".join(lines)


@_mcp.tool()
def worktree_remove(task: str) -> str:
    """Remove a task worktree and its linked branches."""
    task_dir = _root / ".worktrees" / task
    if not task_dir.exists():
        return f"Task workspace not found: {task_dir}"
    removed: list[str] = []
    errors: list[str] = []
    for repo_dir in sorted(task_dir.iterdir()):
        if not repo_dir.is_dir():
            continue
        try:
            specs = ws._repo_specs_for_args([repo_dir.name])
            main_repo = ws._repo_dir(_root, specs[0])
            if (main_repo / ".git").exists():
                ws._run(["git", "worktree", "remove", str(repo_dir)], cwd=main_repo)
                removed.append(repo_dir.name)
        except Exception as e:
            errors.append(f"{repo_dir.name}: {e}")
    agents = task_dir / "AGENTS.md"
    if agents.exists():
        agents.unlink()
    try:
        task_dir.rmdir()
    except OSError:
        pass
    parts: list[str] = []
    if removed:
        parts.append(f"Removed: {', '.join(removed)}")
    if errors:
        parts.append(f"Errors: {'; '.join(errors)}")
    return "\n".join(parts) or f"Removed worktree '{task}'"


def main() -> None:
    global _root
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    _root = Path(args.root).resolve()
    _mcp.run()


if __name__ == "__main__":
    main()
