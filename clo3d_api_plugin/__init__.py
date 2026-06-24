"""
CLO3D API Plugin — works as registered plugin or from Script Editor.

Copy to CLO3D plugins directory for auto-load, or run directly.

Environment:
    CLO3D_API_HOST=127.0.0.1   CLO3D_API_PORT=9898
    CLO3D_API_LOG=./clo3d_api.log
"""

import json
import os
import threading
import traceback
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────
HOST = os.environ.get("CLO3D_API_HOST", "127.0.0.1")
PORT = int(os.environ.get("CLO3D_API_PORT", "9898"))
LOG_FILE = os.environ.get("CLO3D_API_LOG", str(Path(__file__).parent / "clo3d_api.log"))
LOCK = threading.Lock()
LOG_LOCK = threading.Lock()
STOP_FLAG = threading.Event()

_server = None
_server_thread = None


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[CLO3D-Plugin] {msg}"
    print(line, flush=True)
    try:
        with LOG_LOCK:
            Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


# ── CLO3D API ──────────────────────────────────────────────────────────────
try:
    from import_api import ImportFile
    from export_api import ExportRenderingImage, Export2DPatternImage
    from fabric_api import AddFabric, AssignFabricToPattern, ApplyTextureToPatternFace
    from pattern_api import GetPatternCount, GetPatternName
    from utility_api import Simulate, SetFrontView, SetBackView, RotateCamera
    log("CLO3D Python API ready")
except ImportError as e:
    log(f"WARNING: CLO3D API not available: {e}")


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
    name_to_idx = {}
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
        images["front"] = str(out / "render_front.png")
        ExportRenderingImage(images["front"], False, 0)
    if "back" in views:
        try:
            SetBackView()
        except Exception:
            try:
                RotateCamera(0, 180)
            except Exception:
                pass
        images["back"] = str(out / "render_back.png")
        ExportRenderingImage(images["back"], False, 0)
    return {"status": "success", "images": images}


# ── HTTP ────────────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def _send(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read(self):
        n = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(n)) if n else {}

    def do_GET(self):
        if self.path == "/health":
            with LOCK:
                count = GetPatternCount()
            self._send(200, {"status": "ok", "pieces": count})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
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
                log(f"ERROR: {exc}")
                self._send(500, {"status": "error", "error": str(exc)})

    def log_message(self, fmt, *args):
        pass


# ── Server ──────────────────────────────────────────────────────────────────
def _run():
    global _server
    _server = HTTPServer((HOST, PORT), Handler)
    log(f"Listening at http://{HOST}:{PORT}")
    while not STOP_FLAG.is_set():
        _server.handle_request()
    _server.server_close()
    log("Server stopped")


def on_load():
    global _server_thread
    log("Plugin loaded — starting server...")
    _server_thread = threading.Thread(target=_run, daemon=True, name="clo3d-api")
    _server_thread.start()
    log("Ready. GET /health | POST /extract | POST /render")


def on_unload():
    log("Plugin unloading...")
    STOP_FLAG.set()
    log("Stopped")


# ── Direct run (Script Editor) ─────────────────────────────────────────────
if __name__ == "__main__":
    on_load()
    # Script Editor stays responsive — server runs in background
    log("Script Editor is free. Use STOP_FLAG.set() to stop server.")
