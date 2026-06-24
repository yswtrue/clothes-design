"""
CLO3D API Plugin — registered CLO3D plugin that auto-starts an HTTP server.

Install: copy this entire folder into CLO3D's plugin directory.
CLO3D will auto-load it on startup and show it in the Plugins panel.

API endpoints (port 9898):
    GET  /health       → {"status":"ok","pieces":N}
    POST /extract      → Extract piece metadata from .zprj
    POST /render       → Render with material assignments
"""

from __future__ import annotations

import json
import os
import sys
import threading
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

# ── Config ──────────────────────────────────────────────────────────────────

HOST = os.environ.get("CLO3D_API_HOST", "127.0.0.1")
PORT = int(os.environ.get("CLO3D_API_PORT", "9898"))
LOCK = threading.Lock()  # Serialize CLO3D API calls (not thread-safe)

_server: HTTPServer | None = None
_server_thread: threading.Thread | None = None


def log(msg: str) -> None:
    print(f"[CLO3D-Plugin] {msg}", flush=True)


# ── Detect Environment ──────────────────────────────────────────────────────

def _import_clo3d() -> tuple[bool, str]:
    modules = ["import_api", "export_api", "fabric_api", "pattern_api", "utility_api"]
    missing: list[str] = []
    for mod in modules:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    return (len(missing) == 0, ", ".join(missing) if missing else "")


INSIDE_CLO3D, _missing_mods = _import_clo3d()

if not INSIDE_CLO3D:
    log(f"WARNING: Not inside CLO3D — missing: {_missing_mods}")
else:
    from import_api import ImportFile  # type: ignore
    from export_api import ExportRenderingImage, Export2DPatternImage  # type: ignore
    from fabric_api import AddFabric, AssignFabricToPattern, ApplyTextureToPatternFace  # type: ignore
    from pattern_api import GetPatternCount, GetPatternName  # type: ignore
    from utility_api import Simulate, SetFrontView, SetBackView, RotateCamera  # type: ignore
    log(f"CLO3D Python API ready — v{_version() if '_version' in dir() else 'unknown'}")


# ── Core Logic ──────────────────────────────────────────────────────────────

def do_extract(prj_path: str, output_dir: str) -> dict[str, Any]:
    if not os.path.exists(prj_path):
        return {"status": "error", "error": f"File not found: {prj_path}"}

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    ImportFile(prj_path)
    count = GetPatternCount()
    log(f"Extracting {count} pieces")

    pieces: list[dict[str, Any]] = []
    for i in range(count):
        try:
            name = GetPatternName(i)
        except Exception:
            name = f"piece_{i}"
        pieces.append({"name": name, "label": name, "index": i})

    layout = str(out / "layout.png")
    try:
        ExportRenderingImage(layout, False, 0)
    except Exception:
        try:
            Export2DPatternImage(layout)
        except Exception:
            layout = ""

    return {"status": "success", "piece_count": count, "pieces": pieces, "layout_image": layout}


def do_render(
    prj_path: str,
    material_assignments: dict[str, str],
    views: list[str],
    output_dir: str,
) -> dict[str, Any]:
    if not os.path.exists(prj_path):
        return {"status": "error", "error": f"File not found: {prj_path}"}

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 1. Load
    log(f"Loading: {prj_path}")
    ImportFile(prj_path)

    # 2. Map pieces
    count = GetPatternCount()
    name_to_idx: dict[str, int] = {}
    for i in range(count):
        try:
            name_to_idx[GetPatternName(i)] = i
        except Exception:
            name_to_idx[f"piece_{i}"] = i

    # 3. Assign materials
    for piece_name, mat_path in material_assignments.items():
        if not mat_path or not os.path.exists(mat_path):
            log(f"  Skip {piece_name}: material missing")
            continue

        idx = name_to_idx.get(piece_name)
        if idx is None:
            for n, i in name_to_idx.items():
                if piece_name in n or n in piece_name:
                    idx = i
                    break

        if idx is None:
            log(f"  Skip {piece_name}: not in project")
            continue

        try:
            fab = AddFabric(mat_path)
            AssignFabricToPattern(fab, idx)
            log(f"  {piece_name}[{idx}] fabric assigned")
        except Exception:
            try:
                ApplyTextureToPatternFace(idx, 0, mat_path)
                log(f"  {piece_name}[{idx}] texture applied")
            except Exception as exc:
                log(f"  {piece_name}[{idx}] FAILED: {exc}")

    # 4. Simulate
    log("Simulating 100 steps...")
    try:
        Simulate(100)
    except Exception as exc:
        log(f"Simulation warning: {exc}")

    # 5. Render
    images: dict[str, str] = {}
    if "front" in views:
        try:
            SetFrontView()
        except Exception:
            pass
        path = str(out / "render_front.png")
        ExportRenderingImage(path, False, 0)
        images["front"] = path
        log(f"Front: {path}")

    if "back" in views:
        try:
            SetBackView()
        except Exception:
            try:
                RotateCamera(0, 180)
            except Exception:
                pass
        path = str(out / "render_back.png")
        ExportRenderingImage(path, False, 0)
        images["back"] = path
        log(f"Back: {path}")

    return {"status": "success", "images": images}


# ── HTTP Handler ────────────────────────────────────────────────────────────

class _Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, data: dict[str, Any]) -> None:
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read(self) -> dict[str, Any]:
        n = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(n)) if n else {}

    def do_GET(self) -> None:
        if self.path == "/health":
            count = GetPatternCount() if INSIDE_CLO3D else 0
            self._send(200, {"status": "ok", "pieces": count, "inside_clo3d": INSIDE_CLO3D})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        if not INSIDE_CLO3D:
            self._send(503, {"error": "CLO3D API not available"})
            return

        try:
            data = self._read()
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid JSON"})
            return

        with LOCK:
            try:
                if self.path == "/extract":
                    result = do_extract(
                        data.get("prj_path", ""),
                        data.get("output_dir", "./output"),
                    )
                elif self.path == "/render":
                    result = do_render(
                        data.get("prj_path", ""),
                        data.get("material_assignments", {}),
                        data.get("views", ["front", "back"]),
                        data.get("output_dir", "./output"),
                    )
                else:
                    self._send(404, {"error": f"unknown endpoint: {self.path}"})
                    return

                if result.get("status") == "error":
                    self._send(500, result)
                else:
                    self._send(200, result)

            except Exception as exc:
                traceback.print_exc()
                self._send(500, {"status": "error", "error": str(exc)})

    def log_message(self, fmt: str, *args: Any) -> None:
        log(f"HTTP {args[0]}" if args else fmt)


# ── Plugin Lifecycle (called by CLO3D) ──────────────────────────────────────

def on_load() -> None:
    """Called by CLO3D when the plugin is loaded at startup."""
    global _server, _server_thread

    log(f"Plugin loading — starting HTTP server on {HOST}:{PORT}")

    _server = HTTPServer((HOST, PORT), _Handler)

    def _run() -> None:
        log(f"Server listening at http://{HOST}:{PORT}")
        _server.serve_forever()  # type: ignore[union-attr]

    _server_thread = threading.Thread(target=_run, daemon=True, name="clo3d-api")
    _server_thread.start()

    log("Plugin ready — GET /health | POST /extract | POST /render")


def on_unload() -> None:
    """Called by CLO3D when the plugin is unloaded / CLO3D closes."""
    global _server

    log("Plugin unloading...")
    if _server:
        _server.shutdown()
        _server.server_close()
        _server = None
    log("Plugin stopped")


# ── Standalone fallback (run via Script Editor) ─────────────────────────────

if __name__ == "__main__":
    on_load()
    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        on_unload()
