"""Generic MCP middleware that compacts tool descriptions before they reach
the calling LLM.

Why: MCP tool descriptions are often verbose (multi-paragraph rationale,
examples, "when not to use" sections). The LLM has to ingest all of that
on every turn — for ~10 MCP servers across hundreds of tools, that's
10-25K tokens of redundant text per turn.

How: This script spawns an arbitrary upstream MCP server (passed after
`--upstream`), proxies all JSON-RPC traffic, and on `tools/list` responses
replaces each tool's `description` with a 1-2 sentence summary produced
by a small local Ollama model. Compactions are cached on disk by (tool
name + sha256 of original description + model name), so each tool
description is regenerated only when it actually changes.

Usage:
    python tools/mcp_compactor.py --upstream qmd.cmd mcp

The compactor is transparent to tool *calls* — only descriptions are
mutated. Input/output schemas and request/response semantics pass through
untouched.

Implementation note: I/O is thread-based (not asyncio) because Python's
asyncio.connect_read_pipe doesn't support stdin on Windows ProactorEventLoop.
Threads + blocking subprocess pipes work everywhere.

Env knobs:
    OLLAMA_HOST          - Override the default `http://127.0.0.1:11434`.
    CONFIGO_COMPACT_MODEL - Override `llama3.2:3b`.
    CONFIGO_COMPACT_TRACE=1 - Append each request/response to
                              tools/.mcp_compactor.log.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

_DEFAULT_MODEL = os.environ.get("CONFIGO_COMPACT_MODEL", "llama3.2:3b")
_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
_CACHE_PATH = Path(__file__).resolve().parent / ".mcp_descriptions.json"
_TRACE_PATH = Path(__file__).resolve().parent / ".mcp_compactor.log"

_COMPACT_PROMPT = (
    "You are an editor compressing MCP tool descriptions for an LLM agent. "
    "Rewrite the description below in ONE or TWO short sentences (under 25 words "
    "total). Keep all technical terms exact. Drop examples, warnings, motivations, "
    "and 'when to use' boilerplate. Output ONLY the rewritten description, no preamble, no quotes.\n\n"
    "TOOL NAME: {name}\n\nORIGINAL DESCRIPTION:\n{desc}\n\nREWRITTEN:"
)


def _trace(direction: str, payload: dict) -> None:
    if not os.environ.get("CONFIGO_COMPACT_TRACE"):
        return
    try:
        with _TRACE_PATH.open("a", encoding="utf-8") as f:
            f.write(f"{direction} {json.dumps(payload)[:2000]}\n")
    except OSError:
        pass


def _load_cache() -> dict:
    if not _CACHE_PATH.exists():
        return {}
    try:
        return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_cache(cache: dict) -> None:
    try:
        _CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except OSError:
        pass


def _desc_key(tool_name: str, description: str, model: str) -> str:
    h = hashlib.sha256()
    h.update(model.encode("utf-8"))
    h.update(b"\0")
    h.update(tool_name.encode("utf-8"))
    h.update(b"\0")
    h.update(description.encode("utf-8"))
    return h.hexdigest()


def _ollama_generate(prompt: str, model: str, timeout: float = 60.0) -> str | None:
    """Synchronous Ollama call. Returns None if Ollama is unreachable —
    the caller falls back to the original description so nothing breaks
    if the local model is offline."""
    body = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 80},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{_OLLAMA_HOST}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    text = payload.get("response")
    if not isinstance(text, str):
        return None
    text = text.strip().lstrip('"').rstrip('"').strip()
    for prefix in ("REWRITTEN:", "Rewritten:", "Compact:", "COMPACT:"):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
    return text or None


def _compact_descriptions(tools: list, cache: dict, model: str) -> bool:
    """Mutate tools in place. Returns True if any cache entries changed."""
    dirty = False
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        name = tool.get("name")
        original = tool.get("description")
        if not isinstance(name, str) or not isinstance(original, str) or not original.strip():
            continue
        key = _desc_key(name, original, model)
        entry = cache.get(key)
        if entry and isinstance(entry.get("compact"), str) and entry["compact"]:
            tool["description"] = entry["compact"]
            continue
        prompt = _COMPACT_PROMPT.format(name=name, desc=original)
        compact = _ollama_generate(prompt, model)
        if compact:
            cache[key] = {"name": name, "model": model, "compact": compact}
            tool["description"] = compact
            dirty = True
        # else: leave original description untouched.
    return dirty


def _read_message(stream) -> dict | None:
    """Read a newline-delimited JSON message from a binary stream."""
    line = stream.readline()
    if not line:
        return None
    try:
        return json.loads(line.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None


def _write_message(stream, payload: dict) -> None:
    stream.write((json.dumps(payload) + "\n").encode("utf-8"))
    stream.flush()


def run(upstream_cmd: list[str], model: str) -> int:
    upstream = subprocess.Popen(
        upstream_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        bufsize=0,
    )
    if upstream.stdin is None or upstream.stdout is None:
        sys.stderr.write("mcp_compactor: failed to attach to upstream stdio\n")
        return 1

    cache = _load_cache()
    cache_lock = threading.Lock()

    # Use the raw byte buffers so we don't get into trouble with Python's
    # text-mode line buffering (which can stall waiting for a newline on
    # Windows with conpty between us and the parent process).
    client_in = sys.stdin.buffer
    client_out = sys.stdout.buffer

    def client_to_upstream() -> None:
        try:
            while True:
                msg = _read_message(client_in)
                if msg is None:
                    break
                _trace("c->u", msg)
                _write_message(upstream.stdin, msg)
        finally:
            try:
                upstream.stdin.close()
            except OSError:
                pass

    def upstream_to_client() -> None:
        try:
            while True:
                msg = _read_message(upstream.stdout)
                if msg is None:
                    break
                _trace("u->c", msg)
                result = msg.get("result")
                if isinstance(result, dict) and isinstance(result.get("tools"), list):
                    with cache_lock:
                        if _compact_descriptions(result["tools"], cache, model):
                            _save_cache(cache)
                _write_message(client_out, msg)
        finally:
            try:
                client_out.flush()
            except OSError:
                pass

    t_c2u = threading.Thread(target=client_to_upstream, daemon=True)
    t_u2c = threading.Thread(target=upstream_to_client, daemon=True)
    t_c2u.start()
    t_u2c.start()

    # The upstream→client thread keeps the process alive while the agent is
    # running. When upstream closes its stdout we exit; the client→upstream
    # thread might still be blocked on a read, but daemon=True kills it.
    t_u2c.join()
    return upstream.wait()


def main() -> int:
    argv = sys.argv[1:]
    model = _DEFAULT_MODEL
    upstream_cmd: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--model" and i + 1 < len(argv):
            model = argv[i + 1]
            i += 2
            continue
        if arg.startswith("--model="):
            model = arg.split("=", 1)[1]
            i += 1
            continue
        if arg == "--upstream":
            upstream_cmd = argv[i + 1:]
            if upstream_cmd and upstream_cmd[0] == "--":
                upstream_cmd = upstream_cmd[1:]
            break
        if arg in ("-h", "--help"):
            sys.stderr.write(
                "usage: mcp_compactor.py [--model MODEL] --upstream <upstream cmd ...>\n"
            )
            return 0
        i += 1
    if not upstream_cmd:
        sys.stderr.write("mcp_compactor: pass the upstream command after `--upstream`\n")
        return 2
    try:
        return run(upstream_cmd, model)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
