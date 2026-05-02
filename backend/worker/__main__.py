#!/usr/bin/env python
import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

import subprocess

if __name__ == "__main__":
    subprocess.run(
        [
            sys.executable,
            "-m",
            "taskiq",
            "worker",
            "taskiq_app:broker",
            "--fs-discover",
            "--tasks-pattern",
            "worker/tasks.py",
            "--reload",
        ],
        cwd=backend_path,
    )
