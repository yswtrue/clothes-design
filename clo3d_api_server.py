"""
CLO3D API Server v2 — tested with CLO3D 2026.

Run directly in Script Editor. Starts HTTP server in background thread,
monitors for stop signal so Script Editor doesn't freeze.

Usage:
    1. CLO3D → Script → Script Editor → Open this file → Run
    2. Verify: curl.exe http://127.0.0.1:9898/health

To stop: set STOP_FLAG = True in the "stop" section at the bottom.
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

# ── Logging ─────────────────────────────────────────────────────────────────
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[CLO3D-API] {msg}"
    print(line, flush=True)
    try:
        with LOG_LOCK:
            Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


# ── CLO3D API ──────────────────────────────────────────────────────────────
log("Loading CLO3D modules...")

try:
    from import_api import ImportFile
    from export_api import ExportRenderingImage
    from fabric_api import AddFabric, AssignFabricToPattern, ApplyTextureToPatternFace
    from pattern_api import GetPatternCount, GetPatternName
    from utility_api import Simulate, SetFrontView, SetBackView, RotateCamera
    log("CLO3D Python API loaded successfully")
except ImportError as e:
    log(f"CLO3D API load FAILED: {e}")
    raise SystemExit(f"Not inside CLO3D or API unavailable: {e}")


def do_extract(prj_path: str, output_dir: str) -> dict:
    if not os.path.exists(prj_path):
        return {"status": "error", "error": f"File not found: {prj_path}"}
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    ImportFile(prj_path)
    count = GetPatternCount()
    log(f"Extracting {count} pieces from {Path(prj_path).name}")

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
        layout = ""

    return {"status": "success", "piece_count": count, "pieces": pieces, "layout_image": layout}


def do_render(prj_path: str, materials: dict, views: list, output_dir: str) -> dict:
    if not os.path.exists(prj_path):
        return {"status": "error", "error": f"File not found: {prj_path}"}
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    log(f"Loading: {Path(prj_path).name}")
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

    log("Simulating 100 steps...")
    try:
        Simulate(100)
    except Exception as exc:
        log(f"Simulation warning: {exc}")

    images = {}
    if "front" in views:
        try:
            SetFrontView()
        except Exception:
            pass
        p = str(out / "render_front.png")
        ExportRenderingImage(p, False, 0)
        images["front"] = p
        log(f"Front: {p}")
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
        log(f"Back: {p}")

    return {"status": "success", "images": images}


# ── HTTP Handler ────────────────────────────────────────────────────────────
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
        log(f"POST {self.path}")
        try:
            data = self._read()
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid JSON"})
            return

        with LOCK:
            try:
                if self.path == "/extract":
                    r = do_extract(
                        data.get("prj_path", ""),
                        data.get("output_dir", "./output"),
                    )
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
        pass  # suppress default HTTP log noise


# ── Server thread ──────────────────────────────────────────────────────────
_server = None

def _run():
    global _server
    _server = HTTPServer((HOST, PORT), Handler)
    log(f"Server started at http://{HOST}:{PORT}")
    log("Endpoints: GET /health  |  POST /extract  |  POST /render")
    while not STOP_FLAG.is_set():
        _server.handle_request()  # process one request at a time, allows checking STOP_FLAG

    _server.server_close()
    log("Server stopped")


# ── Start ──────────────────────────────────────────────────────────────────
log("Starting CLO3D API server in background thread...")
t = threading.Thread(target=_run, daemon=True, name="clo3d-api")
t.start()
log("Server running in background. Script Editor is free to use.")

# ── Stop (run this section when you want to shut down) ─────────────────────
# STOP_FLAG.set()
# print("Stop signal sent. Server will close after current request.", flush=True)
