from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from runtime_manifest import repo_specs, session_store


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _root_from(path: str | Path) -> Path:
    return Path(path).resolve()


def _session_dir(root: Path) -> Path:
    return root / session_store(root)["directory"]


def _index_path(root: Path) -> Path:
    return root / session_store(root)["index_file"]


def _active_path(root: Path) -> Path:
    return root / session_store(root)["active_file"]


def _conversation_dir(root: Path, conversation_id: str) -> Path:
    return _session_dir(root) / conversation_id


def _metadata_path(root: Path, conversation_id: str) -> Path:
    return _conversation_dir(root, conversation_id) / "metadata.json"


def _markdown_path(root: Path, conversation_id: str) -> Path:
    return _conversation_dir(root, conversation_id) / "session.md"


def _scope_key(root: Path, cwd: Path) -> str:
    try:
        relative = cwd.resolve().relative_to(root.resolve())
    except ValueError:
        return str(cwd.resolve())
    parts = relative.parts
    if len(parts) >= 2 and parts[0] == ".worktrees":
        return str(Path(*parts[:2]))
    return str(relative) if parts else "."


def _repos_in_scope(root: Path, cwd: Path) -> list[str]:
    names: list[str] = []
    for repo in repo_specs(root):
        repo_dir = (root / repo.directory).resolve()
        if cwd.resolve() == repo_dir or repo_dir in cwd.resolve().parents:
            names.append(repo.alias)
        worktree_prefix = (root / ".worktrees").resolve()
        if worktree_prefix in cwd.resolve().parents or cwd.resolve() == worktree_prefix:
            if repo.alias in cwd.parts:
                names.append(repo.alias)
    return sorted(set(names))


def _default_metadata(root: Path, conversation_id: str, cwd: Path) -> dict[str, Any]:
    return {
        "workspace_conversation_id": conversation_id,
        "title": None,
        "created_at": _now(),
        "updated_at": _now(),
        "scope_key": _scope_key(root, cwd),
        "worktree": _scope_key(root, cwd) if _scope_key(root, cwd).startswith(".worktrees") else None,
        "repos": _repos_in_scope(root, cwd),
        "tags": [],
        "claude_session_id": None,
        "claude_transcript_path": None,
        "opencode_session_id": None,
        "client_history": [],
        "prompts": [],
        "change_summaries": [],
        "final_summaries": [],
        "tool_context": [],
    }


def _truncate(text: str, limit: int = 72) -> str:
    compact = " ".join(text.split()).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


def _derive_title(metadata: dict[str, Any], conversation_id: str) -> str:
    existing = metadata.get("title")
    if isinstance(existing, str) and existing.strip():
        return existing.strip()
    prompts = metadata.get("prompts", [])
    if prompts:
        first_text = prompts[0].get("text")
        if isinstance(first_text, str) and first_text.strip():
            return _truncate(first_text)
    worktree = metadata.get("worktree")
    if isinstance(worktree, str) and worktree.strip():
        return worktree.strip().split("/")[-1]
    repos = metadata.get("repos", [])
    if repos:
        return f"{', '.join(repos[:3])}{' +' if len(repos) > 3 else ''}"
    return f"Conversation {conversation_id}"


def _refresh_metadata_fields(metadata: dict[str, Any], conversation_id: str) -> None:
    metadata["title"] = _derive_title(metadata, conversation_id)


def _ensure_conversation(root: Path, cwd: Path, conversation_id: str | None = None) -> tuple[str, dict[str, Any]]:
    active = _load_json(_active_path(root), {"scopes": {}})
    scope = _scope_key(root, cwd)
    conversation = conversation_id or active.get("scopes", {}).get(scope)
    if not conversation:
        conversation = uuid4().hex[:12]

    metadata_path = _metadata_path(root, conversation)
    metadata = _load_json(metadata_path, None)
    if metadata is None:
        metadata = _default_metadata(root, conversation, cwd)
    metadata["updated_at"] = _now()
    metadata["scope_key"] = scope
    metadata["repos"] = _repos_in_scope(root, cwd)
    if scope.startswith(".worktrees"):
        metadata["worktree"] = scope
    _refresh_metadata_fields(metadata, conversation)

    active.setdefault("scopes", {})[scope] = conversation
    _write_json(_active_path(root), active)
    _write_json(metadata_path, metadata)
    render_markdown(root, conversation, metadata)
    refresh_index(root)
    return conversation, metadata


def _append_unique(entries: list[dict[str, str]], item: dict[str, str], key: str = "text") -> None:
    if not item.get(key):
        return
    if entries and entries[-1].get(key) == item.get(key):
        entries[-1]["timestamp"] = item["timestamp"]
        return
    entries.append(item)


def render_markdown(root: Path, conversation_id: str, metadata: dict[str, Any]) -> None:
    lines = [
        "---",
        f"workspace_conversation_id: {metadata['workspace_conversation_id']}",
        f"title: {json.dumps(metadata.get('title') or '')}",
        f"claude_session_id: {metadata.get('claude_session_id') or ''}",
        f"opencode_session_id: {metadata.get('opencode_session_id') or ''}",
        f"created_at: {metadata['created_at']}",
        f"updated_at: {metadata['updated_at']}",
        f"repos: {json.dumps(metadata.get('repos', []))}",
        f"worktree: {metadata.get('worktree') or ''}",
        f"tags: {json.dumps(metadata.get('tags', []))}",
        "---",
        "",
        f"# {metadata.get('title') or f'Conversation {conversation_id}'}",
        "",
        "## Prompts",
        "",
    ]
    prompts = metadata.get("prompts", [])
    if prompts:
        for item in prompts:
            lines.append(f"- `{item['timestamp']}` `{item['client']}`: {item['text']}")
    else:
        lines.append("- None yet.")
    lines.extend(["", "## Change Summary", ""])
    changes = metadata.get("change_summaries", [])
    if changes:
        for item in changes:
            lines.append(f"- `{item['timestamp']}` `{item['client']}`: {item['text']}")
    else:
        lines.append("- None yet.")
    lines.extend(["", "## Final Summary", ""])
    finals = metadata.get("final_summaries", [])
    if finals:
        for item in finals:
            lines.append(f"- `{item['timestamp']}` `{item['client']}`: {item['text']}")
    else:
        lines.append("- None yet.")
    lines.extend(["", "## Tool Context", ""])
    contexts = metadata.get("tool_context", [])
    if contexts:
        for item in contexts:
            lines.append(f"- `{item['timestamp']}` `{item['client']}`: {item['text']}")
    else:
        lines.append("- None yet.")
    path = _markdown_path(root, conversation_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def prune_old_sessions(root: Path) -> dict[str, int]:
    """Archive conversation directories that haven't been updated in N days.

    Reads `retention_days` and `archive_directory` from the session_store
    manifest. `retention_days` ≤ 0 disables pruning. Archived directories
    are moved into the configured archive_directory (default: sessions/.archive).
    Active conversations (referenced by sessions/active.json) are never pruned.
    """
    store = session_store(root)
    retention_days = int(store.get("retention_days", 0) or 0)
    if retention_days <= 0:
        return {"archived": 0, "skipped_active": 0, "scanned": 0}
    archive_root = root / store.get("archive_directory", "sessions/.archive")
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    active = _load_json(_active_path(root), {})
    active_ids: set[str] = set()
    if isinstance(active, dict):
        for value in active.values():
            if isinstance(value, str):
                active_ids.add(value)
            elif isinstance(value, dict) and isinstance(value.get("workspace_conversation_id"), str):
                active_ids.add(value["workspace_conversation_id"])

    archived = 0
    skipped_active = 0
    scanned = 0
    for meta_file in sorted(_session_dir(root).glob("*/metadata.json")):
        scanned += 1
        conversation_dir = meta_file.parent
        conversation_id = conversation_dir.name
        if conversation_id in active_ids:
            skipped_active += 1
            continue
        metadata = _load_json(meta_file, {})
        updated = _parse_iso(metadata.get("updated_at", "")) or _parse_iso(metadata.get("created_at", ""))
        if updated is None:
            # Fall back to directory mtime so dirs without metadata still age out.
            updated = datetime.fromtimestamp(conversation_dir.stat().st_mtime, tz=timezone.utc)
        if updated >= cutoff:
            continue
        archive_root.mkdir(parents=True, exist_ok=True)
        target = archive_root / conversation_id
        if target.exists():
            shutil.rmtree(target)
        shutil.move(str(conversation_dir), str(target))
        archived += 1
    return {"archived": archived, "skipped_active": skipped_active, "scanned": scanned}


def refresh_index(root: Path) -> None:
    prune_old_sessions(root)
    session_root = _session_dir(root)
    session_root.mkdir(parents=True, exist_ok=True)
    rows = ["# Conversations", ""]
    for meta_file in sorted(session_root.glob("*/metadata.json")):
        metadata = _load_json(meta_file, {})
        conversation_id = metadata.get("workspace_conversation_id", meta_file.parent.name)
        rel = _markdown_path(root, conversation_id).relative_to(root)
        _refresh_metadata_fields(metadata, conversation_id)
        title = metadata.get("title") or conversation_id
        repos = ", ".join(metadata.get("repos", [])) or "none"
        updated = metadata.get("updated_at", "")
        rows.append(f"- [{title}]({rel.as_posix()}) (`{conversation_id}`) - repos: {repos} - updated: {updated}")
    if len(rows) == 2:
        rows.append("- No conversations yet.")
    _index_path(root).parent.mkdir(parents=True, exist_ok=True)
    _index_path(root).write_text("\n".join(rows) + "\n", encoding="utf-8")


def prepare(root: Path, cwd: Path, client: str, prompt: str | None, conversation_id: str | None, native_session_id: str | None) -> dict[str, Any]:
    conversation, metadata = _ensure_conversation(root, cwd, conversation_id)
    metadata["client_history"].append(
        {
            "timestamp": _now(),
            "client": client,
            "event": "launch",
            "cwd": str(cwd),
        }
    )
    if native_session_id:
        metadata[f"{client}_session_id"] = native_session_id
    if prompt:
        _append_unique(
            metadata["prompts"],
            {"timestamp": _now(), "client": client, "text": prompt},
        )
    _refresh_metadata_fields(metadata, conversation)
    _write_json(_metadata_path(root, conversation), metadata)
    render_markdown(root, conversation, metadata)
    refresh_index(root)
    return {
        "workspace_conversation_id": conversation,
        "markdown_path": str(_markdown_path(root, conversation)),
        "metadata_path": str(_metadata_path(root, conversation)),
        "native_session_id": metadata.get(f"{client}_session_id"),
    }


def _extract_text(value: Any) -> list[str]:
    texts: list[str] = []
    if isinstance(value, str):
        texts.append(value.strip())
    elif isinstance(value, list):
        for item in value:
            texts.extend(_extract_text(item))
    elif isinstance(value, dict):
        if value.get("type") == "text" and isinstance(value.get("text"), str):
            texts.append(value["text"].strip())
        elif "message" in value:
            texts.extend(_extract_text(value["message"]))
        elif "content" in value:
            texts.extend(_extract_text(value["content"]))
        elif "parts" in value:
            texts.extend(_extract_text(value["parts"]))
        elif "text" in value and isinstance(value["text"], str):
            texts.append(value["text"].strip())
    return [item for item in texts if item]


def _latest_claude_texts(transcript_path: Path) -> tuple[str | None, str | None]:
    last_user = None
    last_assistant = None
    if not transcript_path.exists():
        return None, None
    for line in transcript_path.read_text(encoding="utf-8").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        entry_type = payload.get("type")
        texts = _extract_text(payload)
        if not texts:
            continue
        merged = " ".join(texts).strip()
        if entry_type == "user":
            last_user = merged
        if entry_type == "assistant":
            last_assistant = merged
    return last_user, last_assistant


def claude_hook(root: Path) -> int:
    payload = json.load(sys.stdin)
    cwd = Path(payload.get("cwd") or root).resolve()
    conversation, metadata = _ensure_conversation(root, cwd)
    metadata["claude_session_id"] = payload.get("session_id") or metadata.get("claude_session_id")
    transcript_path = payload.get("transcript_path")
    if transcript_path:
        metadata["claude_transcript_path"] = transcript_path
    metadata["client_history"].append(
        {
            "timestamp": _now(),
            "client": "claude",
            "event": payload.get("hook_event_name"),
            "details": payload.get("reason") or payload.get("source") or "",
        }
    )
    if transcript_path:
        last_user, last_assistant = _latest_claude_texts(Path(transcript_path).expanduser())
        if last_user:
            _append_unique(metadata["prompts"], {"timestamp": _now(), "client": "claude", "text": last_user})
        if last_assistant:
            _append_unique(metadata["final_summaries"], {"timestamp": _now(), "client": "claude", "text": last_assistant})
    _refresh_metadata_fields(metadata, conversation)
    _write_json(_metadata_path(root, conversation), metadata)
    render_markdown(root, conversation, metadata)
    refresh_index(root)
    return 0


def _run_capture(args: list[str], cwd: Path | None = None) -> str:
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
    result = subprocess.run(args, cwd=str(cwd) if cwd else None, env=env, capture_output=True, text=True, check=False)
    return result.stdout if result.returncode == 0 else ""


def _resolve_tool(name: str) -> str:
    direct = shutil.which(name)
    if direct:
        return direct
    home = Path.home()
    candidates: dict[str, list[Path]] = {
        "opencode": [
            home / "AppData" / "Roaming" / "npm" / "opencode.cmd",
            home / "AppData" / "Roaming" / "npm" / "opencode",
        ]
    }
    for candidate in candidates.get(name, []):
        if candidate.exists():
            return str(candidate)
    return name


def _extract_id(entry: dict[str, Any]) -> str | None:
    for key in ("id", "sessionID", "sessionId"):
        value = entry.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _parse_time(entry: dict[str, Any]) -> str:
    for key in ("updatedAt", "updated_at", "createdAt", "created_at"):
        value = entry.get(key)
        if isinstance(value, str):
            return value
    return ""


def _select_latest_opencode_session(entries: list[dict[str, Any]], before_ids: set[str]) -> str | None:
    candidates = [entry for entry in entries if _extract_id(entry)]
    if not candidates:
        return None
    new_entries = [entry for entry in candidates if _extract_id(entry) not in before_ids]
    ordered = sorted(new_entries or candidates, key=_parse_time, reverse=True)
    return _extract_id(ordered[0]) if ordered else None


def _latest_opencode_texts(session_id: str) -> tuple[str | None, str | None]:
    raw = _run_capture([_resolve_tool("opencode"), "export", session_id])
    if not raw:
        return None, None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None, None
    items = payload if isinstance(payload, list) else payload.get("messages", [])
    last_user = None
    last_assistant = None
    if not isinstance(items, list):
        return None, None
    for item in items:
        if not isinstance(item, dict):
            continue
        role = item.get("role") or item.get("type")
        texts = _extract_text(item)
        if not texts:
            continue
        merged = " ".join(texts).strip()
        if role == "user":
            last_user = merged
        if role == "assistant":
            last_assistant = merged
    return last_user, last_assistant


def opencode_finalize(root: Path, cwd: Path, conversation_id: str, before_ids: list[str], explicit_session_id: str | None = None) -> int:
    metadata = _load_json(_metadata_path(root, conversation_id), _default_metadata(root, conversation_id, cwd))
    opencode_tool = _resolve_tool("opencode")
    raw = _run_capture([opencode_tool, "session", "list", "--format", "json", "--max-count", "20"])
    try:
        entries = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        entries = []
    if isinstance(entries, dict):
        entries = entries.get("items", [])
    session_id = explicit_session_id or _select_latest_opencode_session(entries if isinstance(entries, list) else [], set(before_ids))
    if session_id:
        metadata["opencode_session_id"] = session_id
        last_user, last_assistant = _latest_opencode_texts(session_id)
        if last_user:
            _append_unique(metadata["prompts"], {"timestamp": _now(), "client": "opencode", "text": last_user})
        if last_assistant:
            _append_unique(metadata["final_summaries"], {"timestamp": _now(), "client": "opencode", "text": last_assistant})
    metadata["client_history"].append(
        {
            "timestamp": _now(),
            "client": "opencode",
            "event": "exit",
            "cwd": str(cwd),
        }
    )
    _refresh_metadata_fields(metadata, conversation_id)
    _write_json(_metadata_path(root, conversation_id), metadata)
    render_markdown(root, conversation_id, metadata)
    refresh_index(root)
    return 0


def list_conversations(root: Path, cwd: Path | None = None, same_scope_only: bool = False) -> list[dict[str, Any]]:
    session_root = _session_dir(root)
    items: list[dict[str, Any]] = []
    scope = _scope_key(root, cwd) if cwd else None
    for meta_file in sorted(session_root.glob("*/metadata.json")):
        metadata = _load_json(meta_file, {})
        conversation_id = metadata.get("workspace_conversation_id", meta_file.parent.name)
        _refresh_metadata_fields(metadata, conversation_id)
        if same_scope_only and scope and metadata.get("scope_key") != scope:
            continue
        items.append(
            {
                "workspace_conversation_id": conversation_id,
                "title": metadata.get("title") or conversation_id,
                "updated_at": metadata.get("updated_at") or "",
                "repos": metadata.get("repos", []),
                "worktree": metadata.get("worktree"),
                "scope_key": metadata.get("scope_key"),
                "claude_session_id": metadata.get("claude_session_id"),
                "opencode_session_id": metadata.get("opencode_session_id"),
            }
        )
    items.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    return items


def activate(root: Path, cwd: Path, conversation_id: str) -> dict[str, Any]:
    metadata = _load_json(_metadata_path(root, conversation_id), None)
    if metadata is None:
        raise SystemExit(f"Unknown workspace conversation: {conversation_id}")
    active = _load_json(_active_path(root), {"scopes": {}})
    scope = _scope_key(root, cwd)
    active.setdefault("scopes", {})[scope] = conversation_id
    metadata["updated_at"] = _now()
    metadata["scope_key"] = scope
    metadata["repos"] = _repos_in_scope(root, cwd) or metadata.get("repos", [])
    if scope.startswith(".worktrees"):
        metadata["worktree"] = scope
    _refresh_metadata_fields(metadata, conversation_id)
    _write_json(_active_path(root), active)
    _write_json(_metadata_path(root, conversation_id), metadata)
    render_markdown(root, conversation_id, metadata)
    refresh_index(root)
    return {
        "workspace_conversation_id": conversation_id,
        "title": metadata.get("title") or conversation_id,
        "scope_key": scope,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "claude-hook", "opencode-finalize", "refresh-index", "list", "activate"))
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--cwd", default=os.getcwd())
    parser.add_argument("--client")
    parser.add_argument("--prompt")
    parser.add_argument("--conversation")
    parser.add_argument("--native-session-id")
    parser.add_argument("--before-ids", default="[]")
    parser.add_argument("--scope-only", action="store_true")
    parser.add_argument("--format", choices=("json", "text"), default="text")
    args = parser.parse_args()

    root = _root_from(args.root)
    cwd = _root_from(args.cwd)
    if args.command == "prepare":
        payload = prepare(root, cwd, args.client or "unknown", args.prompt, args.conversation, args.native_session_id)
        print(json.dumps(payload))
        return 0
    if args.command == "claude-hook":
        return claude_hook(root)
    if args.command == "opencode-finalize":
        before_ids = json.loads(args.before_ids)
        return opencode_finalize(root, cwd, args.conversation or "", before_ids, args.native_session_id)
    if args.command == "refresh-index":
        refresh_index(root)
        return 0
    if args.command == "list":
        items = list_conversations(root, cwd, args.scope_only)
        if args.format == "json":
            print(json.dumps(items))
            return 0
        if not items:
            print("No conversations found.")
            return 0
        for item in items:
            repos = ", ".join(item.get("repos", [])) or "none"
            worktree = item.get("worktree") or "-"
            print(f"{item['workspace_conversation_id']} | {item['title']} | repos: {repos} | worktree: {worktree} | updated: {item['updated_at']}")
        return 0
    if args.command == "activate":
        payload = activate(root, cwd, args.conversation or "")
        print(json.dumps(payload) if args.format == "json" else f"Active conversation for {payload['scope_key']}: {payload['title']} ({payload['workspace_conversation_id']})")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
