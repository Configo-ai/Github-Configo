"""MCP router that fronts a single upstream code-graph-rag-mcp instance and
adds a `repo` parameter to every tool, scoping query results to a sub-repo.

The upstream tool surface assumes one indexed codebase per server process,
so the only way to scope queries today is to spawn one upstream instance
per sub-repo (6 in our case). That bloats the MCP system-prompt overhead
by ~40-65K tokens per turn. This router collapses that to one upstream
process indexed over the whole workspace, with per-call filtering done
here.

How it works:
- Spawns `npx @er77/code-graph-rag-mcp <workspace-root>` once at startup.
- Speaks newline-delimited JSON-RPC on stdin/stdout (the standard MCP stdio
  transport).
- Forwards every client→upstream message untouched EXCEPT:
    * `tools/list` responses: augment each tool's inputSchema with an
      optional `repo` parameter ("backend" / "frontend" / ...).
    * `tools/call` requests: pop the `repo` argument, remember it for the
      corresponding response.
    * `tools/call` responses: if a `repo` was set on the request, drop any
      content block whose text doesn't reference the repo's directory path.
      Best-effort — works on text results, falls back to keep-all on
      structured-only responses.

Tracing: set `CONFIGO_CGRAG_TRACE=1` to log every request/response pair to
`tools/.code_graph_router.log` for debugging or observability.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcp_proxy import run_proxy
from runtime_manifest import repo_specs

# Where to write trace logs when enabled.
_TRACE_PATH = Path(__file__).resolve().parent / ".code_graph_router.log"


def _trace(direction: str, payload: dict) -> None:
    if not os.environ.get("CONFIGO_CGRAG_TRACE"):
        return
    try:
        with _TRACE_PATH.open("a", encoding="utf-8") as f:
            f.write(f"{direction} {json.dumps(payload)[:2000]}\n")
    except OSError:
        pass


class RepoIndex:
    """Maps repo aliases to absolute prefix paths for response filtering."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.by_alias: dict[str, str] = {}
        for spec in repo_specs(root):
            self.by_alias[spec.alias.lower()] = str((root / spec.directory).resolve())
        # Also accept directory-name match (e.g. "Configo-Backend" alongside "backend").
        for spec in repo_specs(root):
            self.by_alias[spec.directory.lower()] = str((root / spec.directory).resolve())

    @property
    def known_aliases(self) -> list[str]:
        # Returns a stable, dedup'd list (preserve insertion order).
        seen: set[str] = set()
        out: list[str] = []
        for alias in self.by_alias:
            if alias not in seen:
                seen.add(alias)
                out.append(alias)
        return out

    def resolve(self, repo: str | None) -> str | None:
        if not repo:
            return None
        return self.by_alias.get(repo.lower())


def _augment_tool_schemas(tools: list, aliases: list[str]) -> None:
    """Mutate the list in place — add an optional `repo` property to each
    tool's inputSchema so the MCP client surfaces it as a callable arg."""
    enum_values = sorted(aliases)
    repo_property = {
        "type": "string",
        "description": (
            "Optional sub-repo scope for the query. When set, results are "
            "filtered to files under that repo's directory. Recognized values: "
            + ", ".join(enum_values) + "."
        ),
    }
    for tool in tools:
        schema = tool.setdefault("inputSchema", {"type": "object", "properties": {}})
        props = schema.setdefault("properties", {})
        # Don't clobber an existing repo param (in case upstream adds one later).
        props.setdefault("repo", repo_property)


def _filter_result_by_path(result: dict, repo_prefix: str) -> dict:
    """Drop text content blocks that don't contain the repo prefix.

    Conservative: if a block looks structured (no `text`) we keep it — the
    caller decided to query graph data, and we'd rather over-include than
    silently strip an unknown shape. Only text blocks get path-checked.
    """
    if "content" not in result or not isinstance(result["content"], list):
        return result
    kept: list[dict] = []
    for block in result["content"]:
        if not isinstance(block, dict):
            kept.append(block)
            continue
        text = block.get("text")
        if not isinstance(text, str):
            kept.append(block)
            continue
        if repo_prefix in text or repo_prefix.replace("\\", "/") in text:
            kept.append(block)
    # If filtering removed everything, return an explanatory block instead of
    # an empty result so the agent knows why.
    if not kept:
        kept = [
            {
                "type": "text",
                "text": (
                    f"(code-graph-router) no results matched repo prefix "
                    f"{repo_prefix!r}. Either the indexed graph has no nodes "
                    f"under that path, or the upstream tool returned results "
                    f"without recognizable file paths to filter on."
                ),
            }
        ]
    result["content"] = kept
    return result


def run(workspace_root: Path, upstream_cmd: list[str]) -> int:
    repo_index = RepoIndex(workspace_root)
    aliases = repo_index.known_aliases

    # Track in-flight tools/call request ids → repo prefix so we know which
    # responses to filter. Notifications and other methods pass through.
    pending_repo: dict = {}

    def on_request(msg: dict) -> dict:
        _trace("c->u", msg)
        if msg.get("method") == "tools/call":
            params = msg.get("params") or {}
            args = params.get("arguments") or {}
            if isinstance(args, dict) and "repo" in args:
                repo = args.pop("repo")
                request_id = msg.get("id")
                if request_id is not None and isinstance(repo, str):
                    prefix = repo_index.resolve(repo)
                    if prefix:
                        pending_repo[request_id] = prefix
                params["arguments"] = args
                msg["params"] = params
        return msg

    def on_response(msg: dict) -> dict:
        _trace("u->c", msg)
        # tools/list response augmentation
        if "result" in msg and isinstance(msg["result"], dict) and isinstance(msg["result"].get("tools"), list):
            _augment_tool_schemas(msg["result"]["tools"], aliases)
        # tools/call response filtering
        request_id = msg.get("id")
        if request_id is not None and request_id in pending_repo:
            prefix = pending_repo.pop(request_id)
            if "result" in msg and isinstance(msg["result"], dict):
                msg["result"] = _filter_result_by_path(msg["result"], prefix)
        return msg

    return run_proxy(upstream_cmd, on_client_request=on_request, on_upstream_response=on_response)


def main() -> int:
    # Hand-rolled arg parse so argparse doesn't intercept `--` or short
    # flags that belong to the upstream command.
    argv = sys.argv[1:]
    root_str: str | None = None
    upstream_cmd: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--root" and i + 1 < len(argv):
            root_str = argv[i + 1]
            i += 2
            continue
        if arg.startswith("--root="):
            root_str = arg.split("=", 1)[1]
            i += 1
            continue
        if arg == "--upstream":
            upstream_cmd = argv[i + 1:]
            if upstream_cmd and upstream_cmd[0] == "--":
                upstream_cmd = upstream_cmd[1:]
            break
        if arg in ("-h", "--help"):
            sys.stderr.write(
                "usage: code_graph_router.py --root ROOT --upstream <upstream cmd ...>\n"
            )
            return 0
        i += 1
    if not root_str:
        sys.stderr.write("code_graph_router: --root is required\n")
        return 2
    root = Path(root_str).resolve()
    if not upstream_cmd:
        upstream_cmd = ["npx", "@er77/code-graph-rag-mcp", str(root)]
    try:
        return run(root, upstream_cmd)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
