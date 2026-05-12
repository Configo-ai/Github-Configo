from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path


def _git_branch(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() or "detached"
    except Exception:
        return "no-git"


def main() -> None:
    root = Path(os.environ.get("CONFIGO_ROOT", Path.cwd()))
    branch = _git_branch(root)
    graph = root / "graphify" / "GRAPH_REPORT.md"
    graph_state = "graph-ready" if graph.exists() else "graph-missing"
    print(f"Configo | {branch} | {graph_state} | {datetime.now().strftime('%H:%M')}")


if __name__ == "__main__":
    main()
