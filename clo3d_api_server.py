"""
CLO3D API Server v5 — non-blocking main-thread loop.

Uses HTTPServer.timeout + time.sleep to handle HTTP requests without
freezing CLO3D UI. Health check responds instantly.

Render/extract will briefly freeze CLO3D during processing (CLO3D API
must run on main thread).

Run in CLO3D Script Editor.
"""

import json
import os
import time
import traceback
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

HOST = os.environ.get("CLO3D_API_HOST", "127.0.0.1")
PORT = int(os.environ.get("CLO3D_API_PORT", "9898"))
LOG_FILE = os.environ.get("CLO3D_API_LOG", str(Path(os.path.expanduser("~")) / "clo3d_api.log"))

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[CLO3D-API] {msg}", flush=True)
    try:
        Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception: pass

log("Loading CLO3D API...")
from import_api import ImportFile
from export_api import ExportRenderingImage
from fabric_api import AddFabric, AssignFabricToPattern
from pattern_api import GetPatternCount, GetPatternPieceName
from utility_api import Simulate
log("CLO3D API loaded")

def do_extract(prj_path, output_dir):
    if not os.path.exists(prj_path):
        return {"status":"error","error":f"File not found: {prj_path}"}
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    ImportFile(prj_path)
    count = GetPatternCount()
    log(f"Extracting {count} pieces")
    pieces = []
    for i in range(count):
        try: name = GetPatternPieceName(i)
        except Exception: name = f"piece_{i}"
        pieces.append({"name":name,"label":name,"index":i})
    layout = str(out / "layout.png")
    try: ExportRenderingImage(layout, False, 0)
    except Exception: layout = ""
    return {"status":"success","piece_count":count,"pieces":pieces,"layout_image":layout}

def do_render(prj_path, materials, views, output_dir):
    if not os.path.exists(prj_path):
        return {"status":"error","error":f"File not found: {prj_path}"}
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    log(f"Loading: {Path(prj_path).name}")
    ImportFile(prj_path)
    count = GetPatternCount()
    name_to_idx = {}
    for i in range(count):
        try: name_to_idx[GetPatternPieceName(i)] = i
        except Exception: name_to_idx[f"piece_{i}"] = i
    for piece_name, mat_path in materials.items():
        if not mat_path or not os.path.exists(mat_path): continue
        idx = name_to_idx.get(piece_name)
        if idx is None:
            for n,i in name_to_idx.items():
                if piece_name in n or n in piece_name: idx = i; break
        if idx is None: continue
        try:
            fab = AddFabric(mat_path)
            AssignFabricToPattern(fab, idx)
            log(f"  {piece_name}[{idx}] OK")
        except Exception as exc:
            log(f"  {piece_name}[{idx}] FAILED: {exc}")
    try:
        Simulate(100)
        log("Simulated 100 steps")
    except Exception as exc:
        log(f"Simulation: {exc}")
    images = {}
    for view in views:
        p = str(out / f"render_{view}.png")
        ExportRenderingImage(p, False, 0)
        images[view] = p
        log(f"{view}: {p}")
    return {"status":"success","images":images}

class Handler(BaseHTTPRequestHandler):
    def _send(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read(self):
        n = int(self.headers.get("Content-Length","0"))
        return json.loads(self.rfile.read(n)) if n else {}

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"status":"ok","inside_clo3d":True})

    def do_POST(self):
        try: data = self._read()
        except json.JSONDecodeError: self._send(400,{"error":"invalid JSON"}); return
        try:
            if self.path == "/extract":
                r = do_extract(data.get("prj_path",""), data.get("output_dir","./output"))
            elif self.path == "/render":
                r = do_render(data.get("prj_path",""), data.get("material_assignments",{}), data.get("views",["front","back"]), data.get("output_dir","./output"))
            else:
                self._send(404,{"error":f"unknown:{self.path}"}); return
            self._send(200 if r.get("status")=="success" else 500, r)
        except Exception as exc:
            traceback.print_exc()
            log(f"ERROR: {exc}")
            self._send(500,{"status":"error","error":str(exc)})

    def log_message(self, fmt, *args): pass

srv = HTTPServer((HOST, PORT), Handler)
srv.timeout = 0.1  # Non-blocking: returns after 0.1s if no connection
log(f"Server at http://{HOST}:{PORT}")
log("Health check should respond now. CLO3D stays responsive between requests.")

while True:
    srv.handle_request()      # Non-blocking (0.1s timeout)
    time.sleep(0.05)          # Yield to CLO3D event loop
