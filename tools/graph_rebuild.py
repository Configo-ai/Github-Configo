from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    is_windows = os.name == "nt"
    script = root / "scripts" / ("update-graph.bat" if is_windows else "update-graph.sh")
    command = [str(script)]
    if not is_windows:
        command.insert(0, "bash")
    command.extend(sys.argv[1:])
    completed = subprocess.run(command, cwd=root)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
