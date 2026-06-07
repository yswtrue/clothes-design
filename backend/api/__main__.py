#!/usr/bin/env python
"""FastAPI application entrypoint.

Usage:
    python -m api
    python -m api --host 0.0.0.0 --port 8000
    python -m api --reload

Or from backend directory:
    cd backend && python -m api
"""

import sys
from pathlib import Path

# Ensure backend is in path
backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

if __name__ == "__main__":
    import uvicorn

    # Default configuration
    config = {
        "app": "api.main:app",
        "host": "0.0.0.0",
        "port": 8000,
        "reload": False,
        "forwarded_allow_ips": "*",
    }

    # Parse simple command-line arguments
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--reload":
            config["reload"] = True
        elif arg == "--host" and i + 1 < len(args):
            config["host"] = args[i + 1]
        elif arg == "--port" and i + 1 < len(args):
            config["port"] = int(args[i + 1])

    uvicorn.run(**config)
