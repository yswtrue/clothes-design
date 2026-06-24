"""
CLO3D HTTP Bridge — run in terminal (not CLO3D).

python clo3d_api_server.py
"""
import json, os, time, uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

HOST = os.environ.get("CLO3D_API_HOST", "127.0.0.1")
PORT = int(os.environ.get("CLO3D_API_PORT", "9898"))
IPC = Path(os.environ.get("CLO3D_IPC_DIR", os.path.join(os.environ.get("TEMP","."),"clo3d_ipc")))
CMD, RES = IPC/"commands", IPC/"results"
for d in (CMD, RES): d.mkdir(parents=True, exist_ok=True)

class H(BaseHTTPRequestHandler):
    def _s(self, c, d):
        b = json.dumps(d, ensure_ascii=False).encode()
        self.send_response(c); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def _r(self):
        n = int(self.headers.get("Content-Length","0"))
        return json.loads(self.rfile.read(n)) if n else {}
    def do_GET(self):
        if self.path=="/health": self._s(200,{"status":"ok"})
    def do_POST(self):
        try: d=self._r()
        except: self._s(400,{"error":"invalid JSON"}); return
        tid=uuid.uuid4().hex[:12]; rf,ef=RES/f"{tid}.json",RES/f"{tid}.error.json"
        if self.path=="/extract": c={"action":"extract","task_id":tid,"prj_path":d.get("prj_path",""),"output_dir":d.get("output_dir","./output")}
        elif self.path=="/render": c={"action":"render","task_id":tid,"prj_path":d.get("prj_path",""),"material_assignments":d.get("material_assignments",{}),"views":d.get("views",["front","back"]),"output_dir":d.get("output_dir","./output")}
        else: self._s(404,{"error":f"unknown:{self.path}"}); return
        (CMD/f"{tid}.json").write_text(json.dumps(c))
        print(f"[Bridge] {self.path} task={tid}",flush=True)
        e=0
        while e<600:
            if rf.exists(): self._s(200,json.loads(rf.read_text())); rf.unlink(missing_ok=True); return
            if ef.exists(): self._s(500,{"status":"error","error":ef.read_text()}); ef.unlink(missing_ok=True); rf.unlink(missing_ok=True); return
            time.sleep(0.5); e+=0.5
        self._s(504,{"status":"error","error":"timeout"})
    def log_message(self,*a): pass

s=HTTPServer((HOST,PORT),H)
print(f"[Bridge] http://{HOST}:{PORT}",flush=True)
s.serve_forever()
