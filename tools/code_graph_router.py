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

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from runtime_manifest import repo_specs  # noqa: E402

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


def _augment_tool_schemas(tools: list[dict], aliases: list[str]) -> None:
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


class JsonRpcStream:
    """Newline-delimited JSON-RPC reader/writer over asyncio streams."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.reader = reader
        self.writer = writer

    async def read(self) -> dict | None:
        line = await self.reader.readline()
        if not line:
            return None
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return None

    def write(self, payload: dict) -> None:
        line = (json.dumps(payload) + "\n").encode("utf-8")
        self.writer.write(line)


async def _stdio_reader(stream) -> asyncio.StreamReader:
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, stream)
    return reader


async def _stdio_writer(stream) -> asyncio.StreamWriter:
    loop = asyncio.get_event_loop()
    transport, protocol = await loop.connect_write_pipe(asyncio.streams.FlowControlMixin, stream)
    return asyncio.StreamWriter(transport, protocol, None, loop)


async def run(workspace_root: Path, upstream_cmd: list[str]) -> int:
    repo_index = RepoIndex(workspace_root)
    aliases = repo_index.known_aliases

    # Spawn upstream.
    upstream = await asyncio.create_subprocess_exec(
        *upstream_cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=sys.stderr,
    )
    if upstream.stdin is None or upstream.stdout is None:
        sys.stderr.write("code-graph-router: failed to attach to upstream stdio\n")
        return 1

    # Wire stdio for client side.
    client_reader = await _stdio_reader(sys.stdin)
    client_writer = await _stdio_writer(sys.stdout)
    upstream_stream = JsonRpcStream(upstream.stdout, upstream.stdin)
    client_stream = JsonRpcStream(client_reader, client_writer)

    # Track in-flight request ids → repo arg so we can filter the matching response.
    pending_repo: dict = {}

    async def client_to_upstream() -> None:
        while True:
            msg = await client_stream.read()
            if msg is None:
                break
            _trace("c->u", msg)
            method = msg.get("method")
            params = msg.get("params") or {}
            if method == "tools/call":
                args = params.get("arguments") or {}
                if isinstance(args, dict) and "repo" in args:
                    repo = args.pop("repo")
                    request_id = msg.get("id")
                    if request_id is not None:
                        prefix = repo_index.resolve(repo) if isinstance(repo, str) else None
                        if prefix:
                            pending_repo[request_id] = prefix
                    params["arguments"] = args
                    msg["params"] = params
            upstream_stream.write(msg)
            await upstream.stdin.drain()

    async def upstream_to_client() -> None:
        while True:
            msg = await upstream_stream.read()
            if msg is None:
                break
            _trace("u->c", msg)
            # tools/list response augmentation
            if "result" in msg and isinstance(msg["result"], dict) and "tools" in msg["result"]:
                tools = msg["result"]["tools"]
                if isinstance(tools, list):
                    _augment_tool_schemas(tools, aliases)
            # tools/call response filtering
            request_id = msg.get("id")
            if request_id is not None and request_id in pending_repo:
                prefix = pending_repo.pop(request_id)
                if "result" in msg and isinstance(msg["result"], dict):
                    msg["result"] = _filter_result_by_path(msg["result"], prefix)
            client_stream.write(msg)
            await client_writer.drain()

    await asyncio.gather(client_to_upstream(), upstream_to_client())
    return await upstream.wait()


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--upstream", nargs=argparse.REMAINDER, help="Upstream MCP server command (after --).")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    upstream_cmd = args.upstream or ["npx", "@er77/code-graph-rag-mcp", str(root)]
    if upstream_cmd and upstream_cmd[0] == "--":
        upstream_cmd = upstream_cmd[1:]
    try:
        return asyncio.run(run(root, upstream_cmd))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
