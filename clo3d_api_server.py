"""
CLO3D API Server — background handle_request loop.

Run once in CLO3D Script Editor. Script returns immediately.
Server runs in background thread with handle_request() loop.
"""
import json, os, threading, time, traceback
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

HOST = os.environ.get("CLO3D_API_HOST", "127.0.0.1")
PORT = int(os.environ.get("CLO3D_API_PORT", "9898"))
LOG_FILE = os.environ.get("CLO3D_API_LOG", str(Path(os.path.expanduser("~")) / "clo3d_api.log"))
LOCK = threading.Lock(); STOP = threading.Event()

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[CLO3D] {msg}", flush=True)
    try:
        Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except: pass

log("Loading CLO3D API...")
from import_api import ImportFile
from export_api import ExportRenderingImage
from fabric_api import AddFabric, AssignFabricToPattern
from pattern_api import GetPatternCount, GetPatternPieceName
from utility_api import Simulate
log("CLO3D API loaded")

def do_extract(p, o):
    if not os.path.exists(p): return {"status":"error","error":"File not found"}
    o = Path(o); o.mkdir(parents=True, exist_ok=True)
    ImportFile(p); n = GetPatternCount()
    log(f"Extracting {n} pieces")
    ps = []
    for i in range(n):
        try: nm = GetPatternPieceName(i)
        except: nm = f"piece_{i}"
        ps.append({"name":nm,"label":nm,"index":i})
    ly = str(o / "layout.png")
    try: ExportRenderingImage(ly, False, 0)
    except: ly = ""
    return {"status":"success","piece_count":n,"pieces":ps,"layout_image":ly}

def do_render(p, m, v, o):
    if not os.path.exists(p): return {"status":"error","error":"File not found"}
    o = Path(o); o.mkdir(parents=True, exist_ok=True)
    log(f"Loading: {Path(p).name}")
    ImportFile(p); n = GetPatternCount()
    ni = {}
    for i in range(n):
        try: ni[GetPatternPieceName(i)] = i
        except: ni[f"piece_{i}"] = i
    for pn, mp in m.items():
        if not mp or not os.path.exists(mp): continue
        idx = ni.get(pn)
        if idx is None:
            for nn,ii in ni.items():
                if pn in nn or nn in pn: idx = ii; break
        if idx is None: continue
        try:
            f = AddFabric(mp); AssignFabricToPattern(f, idx)
            log(f"  {pn}[{idx}] OK")
        except Exception as ex: log(f"  {pn}[{idx}] FAILED: {ex}")
    try: Simulate(100); log("Simulated")
    except Exception as ex: log(f"Sim: {ex}")
    im = {}
    for vw in v:
        pth = str(o / f"render_{vw}.png")
        ExportRenderingImage(pth, False, 0)
        im[vw] = pth; log(f"{vw}: {pth}")
    return {"status":"success","images":im}

class Handler(BaseHTTPRequestHandler):
    def _send(self, s, d):
        b = json.dumps(d, ensure_ascii=False).encode()
        self.send_response(s)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def _read(self):
        n = int(self.headers.get("Content-Length","0"))
        return json.loads(self.rfile.read(n)) if n else {}

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"status":"ok","inside_clo3d":True})

    def do_POST(self):
        try: d = self._read()
        except: self._send(400,{"error":"invalid JSON"}); return
        with LOCK:
            try:
                if self.path == "/extract":
                    r = do_extract(d.get("prj_path",""), d.get("output_dir","./output"))
                elif self.path == "/render":
                    r = do_render(d.get("prj_path",""), d.get("material_assignments",{}),
                                  d.get("views",["front","back"]), d.get("output_dir","./output"))
                else:
                    self._send(404,{"error":f"unknown:{self.path}"}); return
                self._send(200 if r.get("status")=="success" else 500, r)
            except Exception as ex:
                traceback.print_exc(); log(f"ERROR: {ex}")
                self._send(500,{"status":"error","error":str(ex)})

    def log_message(self, fmt, *args): pass

def _run():
    srv = HTTPServer((HOST, PORT), Handler)
    log(f"Server at http://{HOST}:{PORT}")
    while not STOP.is_set():
        srv.handle_request()
    srv.server_close()

t = threading.Thread(target=_run, name="clo3d-http")
t.start()

log("Ready. Script done — server running in background.")
log("Health: curl http://127.0.0.1:9898/health")
