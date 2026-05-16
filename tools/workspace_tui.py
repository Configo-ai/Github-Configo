"""Three-pane TUI to dispatch Claude / OpenCode / Kimi onto a workspace
conversation + worktree combination.

Layout:
  Conversations [c]    Worktrees [w]    Agent + Action [a]

Flow:
  - Pick a workspace_conversation_id (left pane). If it stores a preferred
    worktree, the middle pane auto-selects that worktree (override allowed).
  - Confirm or change the worktree (middle pane).
  - Pick an agent (right pane: claude / opencode / kimi).
  - Press Enter (or click Launch). If any sub-repo in the worktree is dirty,
    a modal lists per-repo status and offers per-repo actions
    (stash with ws-<id> label, commit message, discard, leave alone). Once
    the worktree is clean (or the user explicitly continues anyway), the
    TUI exits and `os.execvp`s into `python workspace_launcher.py <agent>
    --cwd <worktree> --conversation <id>` so the agent owns the terminal.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Force UTF-8 so Textual can render box-drawing on Windows consoles.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

# Local imports must come before Textual so we get fast-fail import errors
# if the workspace_runtime manifest is broken.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import session_runtime  # noqa: E402
import setup_workspace  # noqa: E402
from runtime_manifest import repo_specs  # noqa: E402

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.screen import ModalScreen
    from textual.widgets import Button, Checkbox, DataTable, Footer, Header, Input, Label, RadioButton, RadioSet, Static
except ImportError:
    sys.stderr.write(
        "workspace_tui requires Textual. Install with:\n"
        "  pip install textual\n"
    )
    sys.exit(1)


AGENTS = ("claude", "opencode", "kimi")


# --- Data loaders ----------------------------------------------------------


@dataclass
class WorktreeRow:
    task: str
    path: Path
    repos: list[str]
    dirty_repos: list[str]

    @property
    def status_glyph(self) -> str:
        return "dirty ⚠" if self.dirty_repos else "clean ✓"


def _load_conversations(root: Path) -> list[dict]:
    return session_runtime.list_conversations(root, root, same_scope_only=False)


def _load_worktrees(root: Path) -> list[WorktreeRow]:
    worktrees_dir = root / ".worktrees"
    if not worktrees_dir.exists():
        return []
    rows: list[WorktreeRow] = []
    for task_dir in sorted(worktrees_dir.iterdir()):
        if not task_dir.is_dir():
            continue
        repos: list[str] = []
        dirty: list[str] = []
        for repo_dir in sorted(task_dir.iterdir()):
            if not repo_dir.is_dir() or not (repo_dir / ".git").exists():
                continue
            repos.append(repo_dir.name)
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(repo_dir),
                capture_output=True,
                text=True,
                check=False,
            )
            if result.stdout.strip():
                dirty.append(repo_dir.name)
        rows.append(WorktreeRow(task=task_dir.name, path=task_dir, repos=repos, dirty_repos=dirty))
    return rows


def _repo_status_lines(repo_dir: Path) -> list[str]:
    result = subprocess.run(
        ["git", "status", "--short", "--branch"],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        check=False,
    )
    return [line for line in result.stdout.splitlines() if line]


# --- Dirty-tree modal -------------------------------------------------------


class DirtyTreeModal(ModalScreen[bool]):
    """Modal shown before launch when the chosen worktree has dirty sub-repos.

    Returns True to "continue with launch" (worktree may still be dirty if
    the user explicitly continued), False to cancel.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("c", "continue_anyway", "Continue"),
        Binding("s", "stash_all", "Stash all"),
    ]

    DEFAULT_CSS = """
    DirtyTreeModal {
        align: center middle;
    }
    DirtyTreeModal > Vertical {
        background: $surface;
        border: thick $warning;
        padding: 1 2;
        width: 80%;
        height: 80%;
    }
    DirtyTreeModal #header {
        color: $warning;
        text-style: bold;
    }
    DirtyTreeModal .repo-block {
        margin-top: 1;
    }
    DirtyTreeModal .repo-name {
        text-style: bold;
        color: $accent;
    }
    DirtyTreeModal .repo-status {
        color: $text-muted;
    }
    DirtyTreeModal #actions {
        height: auto;
        margin-top: 1;
        dock: bottom;
    }
    """

    def __init__(self, worktree: WorktreeRow, conversation_id: str) -> None:
        super().__init__()
        self.worktree = worktree
        self.conversation_id = conversation_id

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(
                f"⚠  Worktree '{self.worktree.task}' has uncommitted changes "
                f"in {len(self.worktree.dirty_repos)} repo(s).",
                id="header",
            )
            yield Static(
                "Review the changes below. Stash creates a stash labelled "
                f"`ws-{self.conversation_id[:8]}` so you can restore it later. "
                "Continue Anyway lets the agent see the dirty state.",
                classes="repo-status",
            )
            for repo_name in self.worktree.dirty_repos:
                repo_dir = self.worktree.path / repo_name
                lines = _repo_status_lines(repo_dir)
                with Vertical(classes="repo-block"):
                    yield Static(f"── {repo_name} ──", classes="repo-name")
                    for line in lines[:15]:
                        yield Static(f"  {line}", classes="repo-status")
                    if len(lines) > 15:
                        yield Static(f"  … +{len(lines) - 15} more", classes="repo-status")
                    yield Horizontal(
                        Button("Stash", id=f"stash-{repo_name}", variant="primary"),
                        Button("Discard", id=f"discard-{repo_name}", variant="error"),
                    )
            with Horizontal(id="actions"):
                yield Button("Continue anyway [c]", id="continue", variant="warning")
                yield Button("Cancel [Esc]", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "continue":
            self.dismiss(True)
        elif bid == "cancel":
            self.dismiss(False)
        elif bid.startswith("stash-"):
            self._stash_repo(bid[len("stash-"):])
        elif bid.startswith("discard-"):
            self._discard_repo(bid[len("discard-"):])

    def _stash_repo(self, repo_name: str) -> None:
        repo_dir = self.worktree.path / repo_name
        label = f"ws-{self.conversation_id[:8]}"
        subprocess.run(
            ["git", "stash", "push", "-u", "-m", label],
            cwd=str(repo_dir),
            check=False,
        )
        self._refresh_after_action(repo_name)

    def _discard_repo(self, repo_name: str) -> None:
        repo_dir = self.worktree.path / repo_name
        subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=str(repo_dir), check=False)
        subprocess.run(["git", "clean", "-fd"], cwd=str(repo_dir), check=False)
        self._refresh_after_action(repo_name)

    def _refresh_after_action(self, repo_name: str) -> None:
        # If repo is now clean, drop it from the modal's view. If all repos clean,
        # auto-dismiss with continue=True.
        repo_dir = self.worktree.path / repo_name
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            check=False,
        )
        if not result.stdout.strip():
            self.worktree.dirty_repos = [r for r in self.worktree.dirty_repos if r != repo_name]
        if not self.worktree.dirty_repos:
            self.dismiss(True)
        else:
            # Cheap "rerender": refresh the screen by popping + repushing isn't worth it;
            # we just mutate the status text to show the action took effect.
            self.notify(f"Cleaned {repo_name} — {len(self.worktree.dirty_repos)} repo(s) remaining")

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_continue_anyway(self) -> None:
        self.dismiss(True)

    def action_stash_all(self) -> None:
        for repo_name in list(self.worktree.dirty_repos):
            self._stash_repo(repo_name)


# --- New-worktree modal -----------------------------------------------------


class NewWorktreeModal(ModalScreen[str | None]):
    """Modal to create a new cross-repo worktree.

    Returns the new task name on success, or None on cancel.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    NewWorktreeModal {
        align: center middle;
    }
    NewWorktreeModal > Vertical {
        background: $surface;
        border: thick $accent;
        padding: 1 2;
        width: 60%;
        height: auto;
    }
    NewWorktreeModal #title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    NewWorktreeModal Input {
        margin-bottom: 1;
    }
    NewWorktreeModal .repos-label {
        margin-top: 1;
        text-style: bold;
    }
    NewWorktreeModal #actions {
        height: auto;
        margin-top: 1;
    }
    """

    def __init__(self, root: Path) -> None:
        super().__init__()
        self.root = root
        self.specs = repo_specs(root)

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("New Worktree", id="title")
            yield Input(placeholder="task name (e.g. feature-login)", id="task-name")
            yield Static("Repos to include:", classes="repos-label")
            for spec in self.specs:
                exists = (self.root / spec.directory).exists()
                cb = Checkbox(spec.alias, id=f"repo-{spec.alias}", value=False)
                cb.disabled = not exists
                yield cb
            with Horizontal(id="actions"):
                yield Button("Create", id="create-btn", variant="primary")
                yield Button("Cancel [Esc]", id="cancel-btn")

    def on_mount(self) -> None:
        self.query_one("#task-name", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
        elif event.button.id == "create-btn":
            self._create()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _create(self) -> None:
        task = self.query_one("#task-name", Input).value.strip()
        if not task:
            self.notify("Task name is required.", severity="warning")
            return
        # Sanity: task should be a safe path/branch name.
        if any(ch in task for ch in (" ", "/", "\\", "..", ":")):
            self.notify("Task name must be a single path-safe token.", severity="warning")
            return
        chosen = [
            spec.alias
            for spec in self.specs
            if self.query_one(f"#repo-{spec.alias}", Checkbox).value
        ]
        if not chosen:
            self.notify("Pick at least one repo.", severity="warning")
            return
        try:
            rc = setup_workspace.worktree_new(self.root, task, chosen)
        except SystemExit as exc:  # repo arg parsing errors raise SystemExit
            self.notify(f"Worktree creation failed: {exc}", severity="error")
            return
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Worktree creation failed: {exc}", severity="error")
            return
        if rc != 0:
            self.notify(f"worktree_new exited with code {rc}", severity="error")
            return
        self.dismiss(task)


# --- Main app ---------------------------------------------------------------


@dataclass
class LaunchSpec:
    agent: str
    conversation_id: str
    worktree_dir: Path


class WorkspaceTUI(App[LaunchSpec | None]):
    CSS = """
    Horizontal#panes { height: 1fr; }
    #conversations, #worktrees, #agent { width: 1fr; height: 100%; border: round $surface; padding: 1; }
    .pane-title { text-style: bold; color: $accent; }
    #launch-row { dock: bottom; height: 3; padding: 1; }
    DataTable { height: 1fr; }
    """

    BINDINGS = [
        Binding("c", "focus_pane('conversations')", "Convs"),
        Binding("w", "focus_pane('worktrees')", "Worktrees"),
        Binding("a", "focus_pane('agent')", "Agent"),
        Binding("n", "new_worktree", "New worktree"),
        Binding("r", "refresh", "Refresh"),
        Binding("enter", "launch", "Launch"),
        Binding("q", "quit", "Quit"),
    ]

    # How often to poll filesystem mtimes for auto-refresh.
    AUTO_REFRESH_SECONDS: float = 2.0

    def __init__(self, root: Path) -> None:
        super().__init__()
        self.root = root
        self.conversations: list[dict] = []
        self.worktrees: list[WorktreeRow] = []
        self.selected_conversation: dict | None = None
        self.selected_worktree: WorktreeRow | None = None
        self.selected_agent: str = "claude"
        self.launch_spec: LaunchSpec | None = None
        # Tracks filesystem signatures so we only repopulate when something
        # observable has actually changed (cheaper than re-running git status).
        self._last_signature: tuple = ()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="panes"):
            with Vertical(id="conversations"):
                yield Label("Conversations [c]", classes="pane-title")
                yield DataTable(id="conv-table", cursor_type="row", zebra_stripes=True)
            with Vertical(id="worktrees"):
                yield Label("Worktrees [w]", classes="pane-title")
                yield DataTable(id="wt-table", cursor_type="row", zebra_stripes=True)
            with Vertical(id="agent"):
                yield Label("Agent + Action [a]", classes="pane-title")
                yield RadioSet(*[RadioButton(a, id=f"agent-{a}", value=(a == "claude")) for a in AGENTS], id="agent-set")
                yield Static("", id="launch-hint")
        with Horizontal(id="launch-row"):
            yield Button("Launch (Enter)", id="launch-btn", variant="primary")
            yield Button("+ New worktree (n)", id="new-wt-btn")
            yield Button("Quit (q)", id="quit-btn")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_data()
        self._populate_tables()
        self.query_one("#conv-table", DataTable).focus()
        # Cheap mtime poll — refreshes only when sessions/ or .worktrees/
        # actually change, so the panel reflects external edits without the
        # user having to hit `r`.
        self.set_interval(self.AUTO_REFRESH_SECONDS, self._auto_refresh)

    # --- Data flow ---

    def _refresh_data(self) -> None:
        self.conversations = _load_conversations(self.root)
        self.worktrees = _load_worktrees(self.root)

    def _fs_signature(self) -> tuple:
        """Cheap fingerprint of sessions/ + .worktrees/ contents.

        Used by the auto-refresh poller to skip work when nothing changed.
        Only looks at top-level mtimes + child names — does NOT scan inside
        repos for dirty state (that's expensive and not worth polling).
        """
        sig: list = []
        sessions_dir = self.root / "sessions"
        if sessions_dir.exists():
            sig.append(("sessions", sessions_dir.stat().st_mtime_ns))
            for child in sorted(sessions_dir.iterdir()):
                if child.is_dir():
                    meta = child / "metadata.json"
                    if meta.exists():
                        sig.append((child.name, meta.stat().st_mtime_ns))
        worktrees_dir = self.root / ".worktrees"
        if worktrees_dir.exists():
            sig.append((".worktrees", worktrees_dir.stat().st_mtime_ns))
            for child in sorted(worktrees_dir.iterdir()):
                if child.is_dir():
                    sig.append((child.name, child.stat().st_mtime_ns))
        return tuple(sig)

    def _auto_refresh(self) -> None:
        sig = self._fs_signature()
        if sig == self._last_signature:
            return
        self._last_signature = sig
        prev_conv = self.selected_conversation["workspace_conversation_id"] if self.selected_conversation else None
        prev_wt = self.selected_worktree.task if self.selected_worktree else None
        self._refresh_data()
        self._populate_tables()
        self._restore_selection(prev_conv, prev_wt)

    def _restore_selection(self, conv_id: str | None, wt_task: str | None) -> None:
        if conv_id:
            conv_table = self.query_one("#conv-table", DataTable)
            for i, c in enumerate(self.conversations):
                if c["workspace_conversation_id"] == conv_id and i < conv_table.row_count:
                    conv_table.move_cursor(row=i)
                    self.selected_conversation = c
                    break
        if wt_task:
            wt_table = self.query_one("#wt-table", DataTable)
            for i, w in enumerate(self.worktrees):
                if w.task == wt_task and i < wt_table.row_count:
                    wt_table.move_cursor(row=i)
                    self.selected_worktree = w
                    break

    def _populate_tables(self) -> None:
        conv_table = self.query_one("#conv-table", DataTable)
        conv_table.clear(columns=True)
        conv_table.add_columns("id", "title", "repos", "updated")
        for c in self.conversations:
            conv_table.add_row(
                c["workspace_conversation_id"][:8],
                c.get("title", "")[:28],
                ", ".join(c.get("repos", []))[:22] or "-",
                c.get("updated_at", "")[:19],
                key=c["workspace_conversation_id"],
            )

        wt_table = self.query_one("#wt-table", DataTable)
        wt_table.clear(columns=True)
        wt_table.add_columns("task", "repos", "status")
        for w in self.worktrees:
            wt_table.add_row(
                w.task,
                ", ".join(w.repos)[:24] or "-",
                w.status_glyph,
                key=w.task,
            )

    # --- Selection events ---

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        table_id = event.data_table.id
        if table_id == "conv-table":
            self._select_conversation_by_key(event.row_key.value)
        elif table_id == "wt-table":
            self._select_worktree_by_key(event.row_key.value)

    def _select_conversation_by_key(self, key: str | None) -> None:
        if not key:
            return
        match = next((c for c in self.conversations if c["workspace_conversation_id"] == key), None)
        if not match:
            return
        self.selected_conversation = match
        # Auto-suggest worktree from conversation metadata if present.
        preferred = match.get("worktree")
        if preferred:
            for index, w in enumerate(self.worktrees):
                if w.task == preferred:
                    table = self.query_one("#wt-table", DataTable)
                    if 0 <= index < table.row_count:
                        table.move_cursor(row=index)
                    self.selected_worktree = w
                    break
        self._update_hint()

    def _select_worktree_by_key(self, key: str | None) -> None:
        if not key:
            return
        match = next((w for w in self.worktrees if w.task == key), None)
        if not match:
            return
        self.selected_worktree = match
        self._update_hint()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        button = event.pressed
        if button and button.id and button.id.startswith("agent-"):
            self.selected_agent = button.id[len("agent-"):]
            self._update_hint()

    def _update_hint(self) -> None:
        hint = self.query_one("#launch-hint", Static)
        if not self.selected_conversation or not self.selected_worktree:
            hint.update("Pick a conversation and a worktree.")
            return
        wt = self.selected_worktree
        conv = self.selected_conversation
        hint.update(
            f"Launch [{self.selected_agent}] in {wt.task}\n"
            f"  conv: {conv['workspace_conversation_id'][:12]} ({conv.get('title', '')[:30]})\n"
            f"  status: {wt.status_glyph}"
        )

    # --- Actions ---

    def action_focus_pane(self, name: str) -> None:
        targets = {"conversations": "#conv-table", "worktrees": "#wt-table", "agent": "#agent-set"}
        selector = targets.get(name)
        if selector:
            self.query_one(selector).focus()

    def action_refresh(self) -> None:
        self._refresh_data()
        self._populate_tables()
        self.notify("Refreshed")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "launch-btn":
            self.action_launch()
        elif event.button.id == "new-wt-btn":
            self.action_new_worktree()
        elif event.button.id == "quit-btn":
            self.exit(None)

    def action_new_worktree(self) -> None:
        self.push_screen(NewWorktreeModal(self.root), self._after_new_worktree)

    def _after_new_worktree(self, task: str | None) -> None:
        if not task:
            return
        # Force a refresh + select the freshly-created worktree.
        self._last_signature = ()  # invalidate so _auto_refresh would also fire
        self._refresh_data()
        self._populate_tables()
        for i, w in enumerate(self.worktrees):
            if w.task == task:
                wt_table = self.query_one("#wt-table", DataTable)
                wt_table.move_cursor(row=i)
                self.selected_worktree = w
                self._update_hint()
                break
        self.notify(f"Created worktree '{task}'")

    def action_launch(self) -> None:
        if not self.selected_conversation or not self.selected_worktree:
            self.notify("Pick a conversation and a worktree first.", severity="warning")
            return
        wt = self.selected_worktree
        if wt.dirty_repos:
            self.push_screen(
                DirtyTreeModal(wt, self.selected_conversation["workspace_conversation_id"]),
                self._after_dirty_check,
            )
        else:
            self._do_launch()

    def _after_dirty_check(self, proceed: bool | None) -> None:
        if proceed:
            self._do_launch()

    def _do_launch(self) -> None:
        assert self.selected_conversation and self.selected_worktree
        self.launch_spec = LaunchSpec(
            agent=self.selected_agent,
            conversation_id=self.selected_conversation["workspace_conversation_id"],
            worktree_dir=self.selected_worktree.path,
        )
        self.exit(self.launch_spec)


# --- Entry point -----------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    root = Path(args.root).resolve()

    spec = WorkspaceTUI(root).run()
    if spec is None:
        return 0

    # The TUI has exited; replace this process with the agent CLI so the
    # interactive terminal handoff is clean. The launcher script handles
    # workspace_conversation_id correlation + native-session resume.
    launcher = str(root / "tools" / "workspace_launcher.py")
    python = sys.executable
    argv = [
        python,
        launcher,
        spec.agent,
        "--root",
        str(root),
        "--cwd",
        str(spec.worktree_dir),
        "--conversation",
        spec.conversation_id,
    ]
    if os.name == "nt":
        # Windows: os.execv replaces the process but the parent shell sees
        # the prompt return as if the child finished — same UX as Unix.
        os.execv(python, argv)
    else:
        os.execvp(python, argv)
    return 0  # unreachable


if __name__ == "__main__":
    sys.exit(main())
