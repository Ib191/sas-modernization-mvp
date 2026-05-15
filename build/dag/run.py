"""Run the modernized pipeline in topological order from pipeline.json."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent
TARGET_DIR = PROJECT_ROOT / "build" / "target"


def main() -> None:
    pipeline = json.loads((HERE / "pipeline.json").read_text(encoding="utf-8"))
    order = pipeline["topological_order"]
    print(f"running {len(order)} programs in topological order:")
    for stem in order:
        script = TARGET_DIR / f"{stem}.py"
        print(f"\n=== {stem} ===")
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(PROJECT_ROOT),
            capture_output=False,
        )
        if result.returncode != 0:
            print(f"FAIL: {stem} exited with {result.returncode}")
            sys.exit(result.returncode)


if __name__ == "__main__":
    main()
