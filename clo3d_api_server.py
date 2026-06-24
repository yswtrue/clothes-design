"""
CLO3D API Server v4 — main-thread safe via file queue.

HTTP server (background thread) writes command files.
Main thread (CLO3D poll loop) executes CLO3D API calls.
HTTP handler polls for result, returns to client.

Run in CLO3D Script Editor.
"""

import json
import os
import threading
import time
import traceback
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

HOST = os.environ.get("CLO3D_API_HOST", "127.0.0.1")
PORT = int(os.environ.get("CLO3D_API_PORT", "9898"))
IPC_DIR = Path(os.environ.get("CLO3D_IPC_DIR", str(Path(__file__).parent / "clo3d_ipc")))
LOG_FILE = os.environ.get("CLO3D_API_LOG", str(Path(__file__).parent / "clo3d_api.log"))

CMD_DIR = IPC_DIR / "commands"
RESULT_DIR = IPC_DIR / "results"
for d in (CMD_DIR, RESULT_DIR):
    d.mkdir(parents=True, exist_ok=True)

STOP_FLAG = threading.Event()
LOG_LOCK = threading.Lock()

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[CLO3D-API] {msg}", flush=True)
    try:
        with LOG_LOCK:
            Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {msg}\n")
    except Exception: pass

# ── CLO3D API (main thread only!) ─────────────────────────────────────────
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

# ── HTTP Handler (background thread, only file I/O, no CLO3D API) ─────────
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

    def _wait_result(self, task_id, timeout=600):
        result_file = RESULT_DIR / f"{task_id}.json"
        error_file = RESULT_DIR / f"{task_id}.error.json"
        elapsed = 0
        while elapsed < timeout:
            if result_file.exists():
                return json.loads(result_file.read_text())
            if error_file.exists():
                return {"status":"error","error":error_file.read_text()}
            time.sleep(0.5)
            elapsed += 0.5
        return {"status":"error","error":"timeout"}

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"status":"ok","inside_clo3d":True})

    def do_POST(self):
        try: data = self._read()
        except json.JSONDecodeError: self._send(400,{"error":"invalid JSON"}); return

        import uuid
        task_id = uuid.uuid4().hex[:12]

        if self.path == "/extract":
            cmd = {"action":"extract","task_id":task_id,"prj_path":data.get("prj_path",""),"output_dir":data.get("output_dir","./output")}
        elif self.path == "/render":
            cmd = {"action":"render","task_id":task_id,"prj_path":data.get("prj_path",""),"material_assignments":data.get("material_assignments",{}),"views":data.get("views",["front","back"]),"output_dir":data.get("output_dir","./output")}
        else:
            self._send(404,{"error":f"unknown:{self.path}"}); return

        (CMD_DIR / f"{task_id}.json").write_text(json.dumps(cmd))
        log(f"Queued {self.path} task={task_id}")
        result = self._wait_result(task_id)
        self._send(200 if result.get("status")=="success" else 500, result)

    def log_message(self, fmt, *args): pass

# ── Main-thread poll loop ──────────────────────────────────────────────────
def process_commands():
    cmd_files = sorted(CMD_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
    for cf in cmd_files:
        try:
            cmd = json.loads(cf.read_text())
            task_id = cmd["task_id"]
            action = cmd["action"]
            log(f"Processing {action} task={task_id}")
            if action == "extract":
                r = do_extract(cmd.get("prj_path",""), cmd.get("output_dir","./output"))
            elif action == "render":
                r = do_render(cmd.get("prj_path",""), cmd.get("material_assignments",{}), cmd.get("views",["front","back"]), cmd.get("output_dir","./output"))
            else:
                r = {"status":"error","error":f"unknown action:{action}"}
            (RESULT_DIR / f"{task_id}.json").write_text(json.dumps(r))
            cf.unlink()
            log(f"Completed {action} task={task_id}")
        except Exception as exc:
            traceback.print_exc()
            log(f"Command error: {exc}")
            try:
                (RESULT_DIR / f"{cmd['task_id']}.error.json").write_text(str(exc))
                cf.unlink()
            except Exception: pass

# ── Start ──────────────────────────────────────────────────────────────────
def _run_http():
    srv = HTTPServer((HOST, PORT), Handler)
    log(f"HTTP at http://{HOST}:{PORT}")
    while not STOP_FLAG.is_set():
        srv.handle_request()
    srv.server_close()

log("Starting HTTP server (background)...")
threading.Thread(target=_run_http, daemon=True, name="clo3d-http").start()

log("Starting command poll loop (main thread)...")
log("Ready. health check should respond now.")

while not STOP_FLAG.is_set():
    process_commands()
    time.sleep(1)
