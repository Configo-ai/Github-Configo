from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import platform

import setup_opencode


def _cmd(name: str) -> str:
    return f"{name}.cmd" if platform.system() == "Windows" else name

OPENCODE_VERSION = "1.14.35"
MERIDIAN_URL = "http://127.0.0.1:3456"


@dataclass(frozen=True)
class RepoSpec:
    alias: str
    directory: str
    default_branch: str
    knowledge_dir: str


REPOS: tuple[RepoSpec, ...] = (
    RepoSpec("backend", "Configo-Backend", "main", "backend"),
    RepoSpec("ai-worker", "Configo-AI-Worker", "main", "ai-worker"),
    RepoSpec("frontend", "Configo-Frontend", "main", "frontend"),
    RepoSpec("web-frontend", "Configo-Web-Frontend", "main", "web-frontend"),
    RepoSpec("developer-frontend", "Configo-Developer-Frontend", "main", "developer-frontend"),
    RepoSpec("deployment", "Configo-Deployment", "main", "deployment"),
)

KNOWLEDGE_COLLECTIONS: tuple[tuple[str, str, str], ...] = (
    *(
        (f"knowledge-{spec.alias}", spec.directory, "**/*.md")
        for spec in REPOS
    ),
    ("knowledge-configo", ".", "**/*.md"),
)


def _supports_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("TERM", "").lower() != "dumb"


def _color(text: str, code: str) -> str:
    if not _supports_color():
        return text
    return f"\033[{code}m{text}\033[0m"


def _panel(title: str, lines: list[str]) -> None:
    width = max([len(title)] + [len(line) for line in lines] + [24])
    border = "+" + "-" * (width + 2) + "+"
    print(border)
    print(f"| {_color(title.ljust(width), '1;36')} |")
    print(border)
    for line in lines:
        print(f"| {line.ljust(width)} |")
    print(border)


def _run(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        capture_output=capture,
    )


def _command_status(name: str) -> str:
    return _color("found", "32") if shutil.which(name) else _color("missing", "31")


def _repo_dir(root: Path, spec: RepoSpec) -> Path:
    return root / spec.directory


def _repo_specs_for_args(items: list[str]) -> list[RepoSpec]:
    available = {spec.alias: spec for spec in REPOS}
    available.update({spec.directory: spec for spec in REPOS})
    result: list[RepoSpec] = []
    for item in items:
        spec = available.get(item)
        if not spec:
            known = ", ".join(repo.alias for repo in REPOS)
            raise SystemExit(f"Unknown repo '{item}'. Known aliases: {known}")
        if spec not in result:
            result.append(spec)
    return result


def _existing_repo_specs(root: Path) -> list[RepoSpec]:
    return [spec for spec in REPOS if _repo_dir(root, spec).exists()]


def _create_task_agents(root: Path, task_dir: Path, repos: list[RepoSpec]) -> None:
    content = [
        f"# Task Workspace: {task_dir.name}",
        "",
        "This folder contains linked git worktrees across multiple Configo repositories.",
        "",
        "## Repositories",
        "",
    ]
    content.extend([f"- `{repo.alias}` -> `{repo.directory}`" for repo in repos])
    content.extend(
        [
            "",
            "## Agent Instructions",
            "",
            "- Keep changes scoped to this task workspace unless explicitly asked otherwise.",
            "- Use `qmd` for workspace knowledge/conventions before reading large docs manually.",
            "- Use `auggie` for live code retrieval in the cloned code repos.",
            "- Check `git status` in each repo before finishing.",
            "- Each repo keeps its own branch, commits, and pull requests.",
            "",
            f"Workspace root: `{root}`",
        ]
    )
    (task_dir / "AGENTS.md").write_text("\n".join(content) + "\n", encoding="utf-8")


def configure_qmd(root: Path) -> list[str]:
    init = _run([_cmd("qmd"), "init"], check=False, capture=True)
    if init.returncode != 0:
        err = (init.stderr or init.stdout or "").strip()
        if err:
            print(f"  [WARN] qmd init: {err}")

    configured: list[str] = []
    for name, relative_path, mask in KNOWLEDGE_COLLECTIONS:
        target = (root / relative_path).resolve()
        if not target.exists():
            continue
        show = _run([_cmd("qmd"), "collection", "show", name], check=False, capture=True)
        if show.returncode != 0:
            result = _run(
                [
                    _cmd("qmd"),
                    "collection",
                    "add",
                    str(target),
                    "--name",
                    name,
                    "--mask",
                    mask,
                ],
                check=False,
                capture=True,
            )
            if result.returncode != 0:
                err = (result.stderr or result.stdout or "").strip()
                print(f"  [WARN] qmd collection add failed for {name}: {err}")
                continue
        configured.append(name)
    _run([_cmd("qmd"), "update"], check=False)
    return configured


_POST_COMMIT_HOOK = """\
#!/bin/sh
# Re-index qmd knowledge when markdown files are committed
if git diff-tree --no-commit-id -r --name-only HEAD | grep -q '\\.md$'; then
  qmd update 2>/dev/null || true
fi
"""


def install_git_hooks(root: Path) -> list[str]:
    installed: list[str] = []
    for spec in REPOS:
        repo_dir = _repo_dir(root, spec)
        if not repo_dir.exists():
            continue
        hooks_dir = repo_dir / ".git" / "hooks"
        if not hooks_dir.exists():
            continue
        hook_path = hooks_dir / "post-commit"
        hook_path.write_text(_POST_COMMIT_HOOK, encoding="utf-8")
        hook_path.chmod(0o755)
        installed.append(spec.alias)
    return installed


def configure_meridian() -> bool:
    if not shutil.which("meridian"):
        return False
    _run([_cmd("meridian"), "setup"])
    return True


def doctor(root: Path) -> int:
    repo_lines = []
    for spec in REPOS:
        exists = _repo_dir(root, spec).exists()
        status = _color("present", "32") if exists else _color("missing", "33")
        repo_lines.append(f"{spec.alias:<20} {status}")

    _panel(
        "Configo Workspace Doctor",
        [
            f"OpenCode:  {_command_status('opencode')}",
            f"Auggie:   {_command_status('auggie')}",
            f"QMD:      {_command_status('qmd')}",
            f"Meridian: {_command_status('meridian')}",
            f"Claude:   {_command_status('claude')}",
            f"VS Code:  {_command_status('code')}",
            "",
            "Repositories:",
            *repo_lines,
        ],
    )
    return 0


def _ask_yes_no(prompt: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        raw = input(f"{prompt} {suffix} ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Please answer yes or no.")


def apply_setup(root: Path, *, configure_meridian_plugin: bool, configure_qmd_collections: bool, install_hooks: bool) -> None:
    setup_opencode.configure_opencode(root, use_meridian=configure_meridian_plugin)
    if configure_meridian_plugin:
        configure_meridian()
    collections: list[str] = []
    if configure_qmd_collections and shutil.which("qmd"):
        collections = configure_qmd(root)
    hooks: list[str] = []
    if install_hooks:
        hooks = install_git_hooks(root)

    lines = [
        "OpenCode config updated for:",
        "- local auggie on code repos only",
        "- qmd MCP for knowledge/docs",
        "- Meridian provider base URL",
        "",
        f"QMD collections: {', '.join(collections) if collections else 'none'}",
        f"Git hooks installed: {', '.join(hooks) if hooks else 'none'}",
        "",
        "Recommended launch flow:",
        "- Launch OpenCode via `claude-opencode`",
        "- Run /init-deep once to generate AGENTS.md across all repos",
        "- Use `scripts/ws` / `scripts\\ws.bat` for task worktrees",
    ]
    _panel("Setup Applied", lines)


def wizard(root: Path, *, yes: bool = False) -> int:
    existing_repos = _existing_repo_specs(root)
    repo_summary = [f"{repo.alias:<20} {_repo_dir(root, repo).name}" for repo in existing_repos]
    _panel(
        "Configo Setup Wizard",
        [
            f"Workspace root: {root}",
            "",
            "Code context: local auggie only",
            "Docs context: qmd only on knowledge paths",
            "External docs: context7",
            f"OpenCode target version: {OPENCODE_VERSION}",
            "",
            "Detected code repos:",
            *(repo_summary or ["No cloned repos detected yet."]),
        ],
    )

    if yes:
        print("  Running with --yes, applying all defaults.")
        apply_setup(root, configure_meridian_plugin=True, configure_qmd_collections=True, install_hooks=True)
        return 0

    do_config = _ask_yes_no("Configure OpenCode, QMD, Meridian, and worktree helpers now?", True)
    if not do_config:
        print("No changes applied.")
        return 0

    do_meridian = _ask_yes_no("Run `meridian setup` and wire OpenCode to local Meridian?", True)
    do_qmd = _ask_yes_no("Register or refresh QMD collections for the knowledge paths?", True)
    do_hooks = _ask_yes_no("Install post-commit git hook to auto-update QMD on .md changes?", True)

    apply_setup(root, configure_meridian_plugin=do_meridian, configure_qmd_collections=do_qmd, install_hooks=do_hooks)
    return 0


def worktree_new(root: Path, task: str, repo_args: list[str]) -> int:
    repos = _repo_specs_for_args(repo_args)
    task_dir = root / ".worktrees" / task
    task_dir.mkdir(parents=True, exist_ok=True)

    for spec in repos:
        repo_dir = _repo_dir(root, spec)
        if not (repo_dir / ".git").exists():
            raise SystemExit(f"Repo not found or not cloned: {repo_dir}")

        target = task_dir / spec.alias
        if target.exists():
            print(f"Already exists: {target}")
            continue

        _run(["git", "fetch", "--all", "--prune"], cwd=repo_dir)
        branch_check = _run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{task}"],
            cwd=repo_dir,
            check=False,
        )
        if branch_check.returncode == 0:
            _run(["git", "worktree", "add", str(target), task], cwd=repo_dir)
        else:
            _run(
                [
                    "git",
                    "worktree",
                    "add",
                    "-b",
                    task,
                    str(target),
                    f"origin/{spec.default_branch}",
                ],
                cwd=repo_dir,
            )
        print(f"Created worktree: {spec.alias} -> {target}")

    _create_task_agents(root, task_dir, repos)
    print(task_dir)
    return 0


def worktree_status(root: Path, task: str) -> int:
    task_dir = root / ".worktrees" / task
    if not task_dir.exists():
        raise SystemExit(f"Task workspace not found: {task_dir}")

    for repo_dir in sorted(task_dir.iterdir()):
        if not repo_dir.is_dir():
            continue
        print()
        print(f"== {repo_dir.name} ==")
        _run(["git", "status", "--short", "--branch"], cwd=repo_dir, check=False)
    return 0


def worktree_remove(root: Path, task: str) -> int:
    task_dir = root / ".worktrees" / task
    if not task_dir.exists():
        raise SystemExit(f"Task workspace not found: {task_dir}")

    for repo_dir in sorted(task_dir.iterdir()):
        if not repo_dir.is_dir():
            continue
        spec = _repo_specs_for_args([repo_dir.name])[0]
        main_repo = _repo_dir(root, spec)
        if not (main_repo / ".git").exists():
            print(f"Skipping {repo_dir.name}: source repo missing")
            continue
        _run(["git", "worktree", "remove", str(repo_dir)], cwd=main_repo)
        print(f"Removed worktree: {repo_dir.name}")

    agents = task_dir / "AGENTS.md"
    if agents.exists():
        agents.unlink()
    try:
        task_dir.rmdir()
    except OSError:
        pass
    return 0


def worktree_list(root: Path) -> int:
    worktrees_dir = root / ".worktrees"
    if not worktrees_dir.exists():
        return 0
    for task_dir in sorted(worktrees_dir.iterdir()):
        if task_dir.is_dir():
            print(task_dir.name)
    return 0


def worktree_open(root: Path, task: str) -> int:
    task_dir = root / ".worktrees" / task
    if not task_dir.exists():
        raise SystemExit(f"Task workspace not found: {task_dir}")

    if shutil.which("code"):
        _run(["code", str(task_dir)], check=False)
    else:
        print(task_dir)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    subparsers = parser.add_subparsers(dest="command", required=True)

    wizard_parser = subparsers.add_parser("wizard")
    wizard_parser.add_argument("--yes", action="store_true")
    subparsers.add_parser("doctor")

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--skip-meridian", action="store_true")
    apply_parser.add_argument("--skip-qmd", action="store_true")
    apply_parser.add_argument("--skip-hooks", action="store_true")

    worktree = subparsers.add_parser("worktree")
    worktree_sub = worktree.add_subparsers(dest="worktree_command", required=True)

    wt_new = worktree_sub.add_parser("new")
    wt_new.add_argument("task")
    wt_new.add_argument("repos", nargs="+")

    wt_status = worktree_sub.add_parser("status")
    wt_status.add_argument("task")

    wt_remove = worktree_sub.add_parser("remove")
    wt_remove.add_argument("task")

    worktree_sub.add_parser("list")

    wt_open = worktree_sub.add_parser("open")
    wt_open.add_argument("task")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    root = Path(args.root).resolve()

    if args.command == "wizard":
        return wizard(root, yes=getattr(args, "yes", False))
    if args.command == "doctor":
        return doctor(root)
    if args.command == "apply":
        apply_setup(
            root,
            configure_meridian_plugin=not args.skip_meridian,
            configure_qmd_collections=not args.skip_qmd,
            install_hooks=not args.skip_hooks,
        )
        return 0
    if args.command == "worktree":
        command = args.worktree_command
        if command == "new":
            return worktree_new(root, args.task, args.repos)
        if command == "status":
            return worktree_status(root, args.task)
        if command == "remove":
            return worktree_remove(root, args.task)
        if command == "list":
            return worktree_list(root)
        if command == "open":
            return worktree_open(root, args.task)
    parser.error("Unknown command")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
