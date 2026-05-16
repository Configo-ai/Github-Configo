from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# Force UTF-8 on stdout/stderr so progress bars and panels render correctly
# on Windows consoles (default cp1252 can't encode block-drawing characters).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

# qmd's prebuilt CUDA binary is built against CUDA 12; on Windows machines
# with only CUDA 13 installed it crashes at first kernel launch. Force the
# Vulkan backend for the qmd subprocess so embedding/rerank runs on GPU.
# (`setx` persists this across sessions, but inline-set guards the current run.)
if platform.system() == "Windows":
    os.environ.setdefault("QMD_LLAMA_GPU", "vulkan")

import setup_agents
from runtime_manifest import (
    opencode_version,
    qmd_conversation_collections,
    qmd_knowledge_collections,
    repo_specs,
    session_store,
)
from session_runtime import refresh_index


def _cmd(name: str) -> str:
    return f"{name}.cmd" if platform.system() == "Windows" else name


def _supports_color() -> bool:
    return sys.stdout.isatty()


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


class _Phases:
    """Lightweight phase tracker with an ASCII progress bar.

    Prints `[i/N] [▓▓▓░░░] 50%  label` to stderr at each step. Rendered on
    stderr so phases that stream their own output to stdout (e.g. qmd's
    per-step progress bar) don't interleave with the top-level indicator.
    """

    def __init__(self, total: int) -> None:
        self.total = max(1, total)
        self.idx = 0

    def step(self, label: str) -> None:
        self.idx += 1
        width = 30
        filled = int(width * self.idx / self.total)
        bar = "█" * filled + "░" * (width - filled)
        pct = int(100 * self.idx / self.total)
        prefix = _color(f"[{self.idx}/{self.total}]", "1;36")
        bar_colored = _color(bar, "32" if self.idx == self.total else "33")
        print(f"\n{prefix} {bar_colored} {pct}%  {label}", file=sys.stderr, flush=True)


def _command_status(name: str) -> str:
    return _color("found", "32") if shutil.which(name) else _color("missing", "31")


def _repo_dir(root: Path, alias_or_dir: str) -> Path:
    for repo in repo_specs(root):
        if alias_or_dir in {repo.alias, repo.directory}:
            return root / repo.directory
    raise SystemExit(f"Unknown repo '{alias_or_dir}'")


def _repo_specs_for_args(root: Path, items: list[str]):
    result = []
    seen = set()
    for item in items:
        for repo in repo_specs(root):
            if item in {repo.alias, repo.directory} and repo.alias not in seen:
                result.append(repo)
                seen.add(repo.alias)
                break
        else:
            known = ", ".join(repo.alias for repo in repo_specs(root))
            raise SystemExit(f"Unknown repo '{item}'. Known aliases: {known}")
    return result


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


def _load_qmd_collections() -> dict[str, dict[str, str]]:
    result = _run([_cmd("qmd"), "collection", "list", "--format", "json"], check=False, capture=True)
    if result.returncode != 0 or not result.stdout.strip():
        return {}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    if isinstance(payload, dict):
        payload = payload.get("collections", payload.get("items", []))
    collections: dict[str, dict[str, str]] = {}
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict) and item.get("name"):
                collections[item["name"]] = item
    return collections


def _ensure_qmd_collection(root: Path, collection: dict[str, str], *, include_by_default: bool) -> str:
    name = collection["name"]
    target = (root / collection["path"]).resolve()
    mask = collection["mask"]
    if not target.exists():
        return f"skip:{name}"

    current = _load_qmd_collections().get(name)
    target_str = str(target)
    needs_reset = False
    if current is None:
        needs_reset = True
    else:
        current_path = current.get("path") or current.get("directory") or ""
        current_mask = current.get("pattern") or current.get("mask") or ""
        if current_path != target_str or current_mask != mask:
            _run([_cmd("qmd"), "collection", "remove", name], check=False)
            needs_reset = True

    if needs_reset:
        _run([_cmd("qmd"), "collection", "add", target_str, "--name", name, "--mask", mask], check=False)

    if include_by_default:
        _run([_cmd("qmd"), "collection", "include", name], check=False)
    else:
        _run([_cmd("qmd"), "collection", "exclude", name], check=False)
    return f"ok:{name}"


def configure_qmd(root: Path, phases: "_Phases | None" = None) -> dict[str, list[str]]:
    if phases:
        phases.step("Registering QMD collections")
    knowledge = []
    for collection in qmd_knowledge_collections(root):
        result = _ensure_qmd_collection(root, collection, include_by_default=True)
        if result.startswith("ok:"):
            knowledge.append(collection["name"])
    # Session bodies are local-only now (see workspace_runtime.yaml conversation_collections);
    # iterate so a future manifest entry would still be honored, but expect an empty list today.
    conversations = []
    for collection in qmd_conversation_collections(root):
        result = _ensure_qmd_collection(root, collection, include_by_default=False)
        if result.startswith("ok:"):
            conversations.append(collection["name"])
    if phases:
        phases.step("Updating QMD index")
    _run([_cmd("qmd"), "update"], check=False)
    if phases:
        phases.step("Generating embeddings (first run downloads ~330MB model)")
    # Generate vector embeddings so semantic (vec/hyde) search works.
    _run([_cmd("qmd"), "embed"], check=False)
    if phases:
        phases.step("Refreshing session index")
    refresh_index(root)
    return {"knowledge": knowledge, "conversations": conversations}


def doctor(root: Path) -> int:
    repo_lines = []
    for repo in repo_specs(root):
        exists = (root / repo.directory).exists()
        status = _color("present", "32") if exists else _color("missing", "33")
        repo_lines.append(f"{repo.alias:<20} {status}")

    _panel(
        "Configo Workspace Doctor",
        [
            f"OpenCode:  {_command_status('opencode')}",
            f"Auggie:   {_command_status('auggie')}",
            f"QMD:      {_command_status('qmd')}",
            f"Claude:   {_command_status('claude')}",
            f"VS Code:  {_command_status('code')}",
            "",
            f"OpenCode target: {opencode_version(root)}",
            f"Session log dir: {session_store(root)['directory']}",
            "",
            "Repositories:",
            *repo_lines,
        ],
    )
    return 0


def apply_setup(root: Path, *, configure_qmd_collections: bool) -> None:
    do_qmd = configure_qmd_collections and shutil.which("qmd") is not None
    # 1 phase for agent-client configuration, plus 4 qmd sub-phases when enabled.
    phases = _Phases(total=1 + (4 if do_qmd else 0))
    phases.step("Configuring Claude Code, OpenCode, Kimi")
    setup_agents.configure_all(root)
    collection_state = {"knowledge": [], "conversations": []}
    if do_qmd:
        collection_state = configure_qmd(root, phases)
    lines = [
        "Shared runtime configured for:",
        "- local auggie on code repos only",
        "- qmd-knowledge indexes workspace docs (sessions/ kept local-only)",
        "- shared Claude/OpenCode tool names",
        "",
        f"Knowledge collections: {', '.join(collection_state['knowledge']) or 'none'}",
        "",
        "Recommended launch flow:",
        "- Launch Claude with `claude-workspace`",
        "- Launch OpenCode with `opencode-workspace`",
        "- Use `scripts/ws` / `scripts\\ws.bat` for task worktrees",
    ]
    _panel("Setup Applied", lines)


def wizard(root: Path, *, yes: bool = False) -> int:
    repo_summary = [f"{repo.alias:<20} {(root / repo.directory).name}" for repo in repo_specs(root) if (root / repo.directory).exists()]
    _panel(
        "Configo Setup Wizard",
        [
            f"Workspace root: {root}",
            "",
            "Code context: auggie",
            "Docs + session context: qmd-knowledge (scope per-call via `collections`)",
            "External docs: context7",
            f"OpenCode target version: {opencode_version(root)}",
            "",
            "Detected code repos:",
            *(repo_summary or ["No cloned repos detected yet."]),
        ],
    )

    if yes:
        print("  Running with --yes, applying all defaults.")
        apply_setup(root, configure_qmd_collections=True)
        return 0

    do_config = _ask_yes_no("Configure the shared Claude/OpenCode runtime now?", True)
    if not do_config:
        print("No changes applied.")
        return 0
    do_qmd = _ask_yes_no("Register or refresh QMD collections for knowledge and conversations?", True)
    apply_setup(root, configure_qmd_collections=do_qmd)
    return 0


def _create_task_agents(root: Path, task_dir: Path, repos) -> None:
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
            "- Use `qmd-knowledge` with `collections: [\"knowledge-*\"]` for repo docs/conventions.",
            "- Use `auggie` for live code retrieval in the cloned code repos.",
            "- Check `git status` in each repo before finishing.",
            "",
            f"Workspace root: `{root}`",
        ]
    )
    (task_dir / "AGENTS.md").write_text("\n".join(content) + "\n", encoding="utf-8")


def worktree_new(root: Path, task: str, repo_args: list[str]) -> int:
    repos = _repo_specs_for_args(root, repo_args)
    task_dir = root / ".worktrees" / task
    task_dir.mkdir(parents=True, exist_ok=True)

    for repo in repos:
        repo_dir = root / repo.directory
        if not (repo_dir / ".git").exists():
            raise SystemExit(f"Repo not found or not cloned: {repo_dir}")
        target = task_dir / repo.alias
        if target.exists():
            print(f"Already exists: {target}")
            continue
        _run(["git", "fetch", "--all", "--prune"], cwd=repo_dir)
        branch_check = _run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{task}"], cwd=repo_dir, check=False)
        if branch_check.returncode == 0:
            _run(["git", "worktree", "add", str(target), task], cwd=repo_dir)
        else:
            _run(["git", "worktree", "add", "-b", task, str(target), f"origin/{repo.default_branch}"], cwd=repo_dir)
        print(f"Created worktree: {repo.alias} -> {target}")
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
        repo_dir_name = repo_dir.name
        main_repo = _repo_dir(root, repo_dir_name)
        if not (main_repo / ".git").exists():
            print(f"Skipping {repo_dir_name}: source repo missing")
            continue
        _run(["git", "worktree", "remove", str(repo_dir)], cwd=main_repo)
        print(f"Removed worktree: {repo_dir_name}")
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
    apply_parser.add_argument("--skip-qmd", action="store_true")

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
        apply_setup(root, configure_qmd_collections=not args.skip_qmd)
        return 0
    if args.command == "worktree":
        if args.worktree_command == "new":
            return worktree_new(root, args.task, args.repos)
        if args.worktree_command == "status":
            return worktree_status(root, args.task)
        if args.worktree_command == "remove":
            return worktree_remove(root, args.task)
        if args.worktree_command == "list":
            return worktree_list(root)
        if args.worktree_command == "open":
            return worktree_open(root, args.task)
    parser.error("Unknown command")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
