"""Shared building block for stdio MCP middleware.

Both `tools/mcp_compactor.py` (description compactor) and
`tools/code_graph_router.py` (per-repo result filter) are MCP-over-stdio
proxies: spawn an upstream MCP server, read newline-delimited JSON-RPC
messages from this process's stdin/stdout, forward each message to/from
the upstream, optionally mutate request and/or response payloads.

This module owns the I/O machinery (subprocess + threads) so each proxy
only has to provide mutate-message callbacks. Thread-based I/O is used
deliberately — Python's asyncio.connect_read_pipe doesn't support stdin
on Windows ProactorEventLoop, and the proxy is the only thing on the
event loop, so threads cost nothing and work everywhere.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from collections.abc import Callable

# A mutator returns the (possibly modified) message dict, or None to drop
# the message. Implementations should be fast — they run on the hot path
# between the agent and the upstream MCP.
Mutator = Callable[[dict], "dict | None"]


def _read_message(stream) -> dict | None:
    """Read one newline-delimited JSON message from a binary stream.

    Returns None on EOF or unparseable input. Unparseable inputs are
    swallowed (caller may want to log) — the alternative is crashing the
    whole proxy on a single malformed line.
    """
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


def run_proxy(
    upstream_cmd: list[str],
    *,
    on_client_request: Mutator | None = None,
    on_upstream_response: Mutator | None = None,
) -> int:
    """Spawn `upstream_cmd`, proxy stdio between it and our parent.

    `on_client_request` runs for every message flowing client→upstream;
    `on_upstream_response` runs for every message in the other direction.
    Either may mutate the dict in place or return a replacement; both may
    return None to drop the message (rare — useful for stripping
    notifications you don't want forwarded).

    Returns the upstream process's exit code.
    """
    upstream = subprocess.Popen(
        upstream_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        bufsize=0,
    )
    if upstream.stdin is None or upstream.stdout is None:
        sys.stderr.write("mcp_proxy: failed to attach to upstream stdio\n")
        return 1

    # Raw byte buffers; text-mode line buffering can stall on Windows.
    client_in = sys.stdin.buffer
    client_out = sys.stdout.buffer

    def client_to_upstream() -> None:
        try:
            while True:
                msg = _read_message(client_in)
                if msg is None:
                    break
                if on_client_request is not None:
                    msg = on_client_request(msg)
                    if msg is None:
                        continue
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
                if on_upstream_response is not None:
                    msg = on_upstream_response(msg)
                    if msg is None:
                        continue
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

    # The upstream→client thread is the lifeline: when upstream closes its
    # stdout we wind down. The other thread is daemonized so it dies with
    # the process if it's still blocked on a read.
    t_u2c.join()
    return upstream.wait()
