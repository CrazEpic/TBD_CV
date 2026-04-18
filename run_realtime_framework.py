from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    demo_dir = repo_root / "Demo"
    sys.path.insert(0, str(demo_dir))
    runpy.run_path(str(demo_dir / "run_realtime_framework.py"), run_name="__main__")


if __name__ == "__main__":
    main()
