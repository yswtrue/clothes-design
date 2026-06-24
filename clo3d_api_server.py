"""
CLO3D API Server — standalone script (run directly from Script Editor).

For plugin installation, use the clo3d_api_plugin/ folder instead.
This standalone version is identical but self-contained for simplicity.

Run: CLO3D → Script → Script Editor → Open this file → Run
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

HOST = os.environ.get("CLO3D_API_HOST", "127.0.0.1")
PORT = int(os.environ.get("CLO3D_API_PORT", "9898"))
LOCK = threading.Lock()


def log(msg: str) -> None:
    print(f"[CLO3D-API] {msg}", flush=True)


# ── Detect ──────────────────────────────────────────────────────────────────

def _import_clo3d() -> bool:
    for mod in ("import_api", "export_api", "fabric_api", "pattern_api", "utility_api"):
        try:
            __import__(mod)
        except ImportError:
            return False
    return True


INSIDE = _import_clo3d()

if INSIDE:
    from import_api import ImportFile  # type: ignore
    from export_api import ExportRenderingImage, Export2DPatternImage  # type: ignore
    from fabric_api import AddFabric, AssignFabricToPattern, ApplyTextureToPatternFace  # type: ignore
    from pattern_api import GetPatternCount, GetPatternName  # type: ignore
    from utility_api import Simulate, SetFrontView, SetBackView, RotateCamera  # type: ignore
    log("CLO3D Python API loaded")
else:
    log("WARNING: Running outside CLO3D — API will return errors")

# ── Logic ───────────────────────────────────────────────────────────────────

def do_extract(prj_path: str, output_dir: str) -> dict:
    if not os.path.exists(prj_path):
        return {"status": "error", "error": f"File not found: {prj_path}"}
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    ImportFile(prj_path)
    count = GetPatternCount()
    pieces = []
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


def do_render(prj_path: str, materials: dict, views: list, output_dir: str) -> dict:
    if not os.path.exists(prj_path):
        return {"status": "error", "error": f"File not found: {prj_path}"}
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    ImportFile(prj_path)
    count = GetPatternCount()
    name_to_idx: dict[str, int] = {}
    for i in range(count):
        try:
            name_to_idx[GetPatternName(i)] = i
        except Exception:
            name_to_idx[f"piece_{i}"] = i

    for piece_name, mat_path in materials.items():
        if not mat_path or not os.path.exists(mat_path):
            continue
        idx = name_to_idx.get(piece_name)
        if idx is None:
            for n, i in name_to_idx.items():
                if piece_name in n or n in piece_name:
                    idx = i
                    break
        if idx is None:
            continue
        try:
            fab = AddFabric(mat_path)
            AssignFabricToPattern(fab, idx)
        except Exception:
            try:
                ApplyTextureToPatternFace(idx, 0, mat_path)
            except Exception:
                pass

    try:
        Simulate(100)
    except Exception:
        pass

    images = {}
    if "front" in views:
        try:
            SetFrontView()
        except Exception:
            pass
        p = str(out / "render_front.png")
        ExportRenderingImage(p, False, 0)
        images["front"] = p
    if "back" in views:
        try:
            SetBackView()
        except Exception:
            try:
                RotateCamera(0, 180)
            except Exception:
                pass
        p = str(out / "render_back.png")
        ExportRenderingImage(p, False, 0)
        images["back"] = p
    return {"status": "success", "images": images}


# ── HTTP ────────────────────────────────────────────────────────────────────

class _Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read(self) -> dict:
        n = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(n)) if n else {}

    def do_GET(self) -> None:
        if self.path == "/health":
            count = GetPatternCount() if INSIDE else 0
            self._send(200, {"status": "ok", "pieces": count, "inside_clo3d": INSIDE})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        if not INSIDE:
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
                    r = do_extract(data.get("prj_path", ""), data.get("output_dir", "./output"))
                elif self.path == "/render":
                    r = do_render(
                        data.get("prj_path", ""),
                        data.get("material_assignments", {}),
                        data.get("views", ["front", "back"]),
                        data.get("output_dir", "./output"),
                    )
                else:
                    self._send(404, {"error": f"unknown: {self.path}"})
                    return
                self._send(200 if r.get("status") == "success" else 500, r)
            except Exception as exc:
                traceback.print_exc()
                self._send(500, {"status": "error", "error": str(exc)})

    def log_message(self, fmt: str, *args: Any) -> None:
        log(f"HTTP {args[0]}" if args else fmt)


if __name__ == "__main__":
    srv = HTTPServer((HOST, PORT), _Handler)
    log(f"Listening at http://{HOST}:{PORT}")
    log("GET /health | POST /extract | POST /render")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.server_close()
        log("Stopped")
