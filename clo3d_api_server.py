"""
CLO3D API Bridge — standalone HTTP server (run OUTSIDE CLO3D from terminal).

Acts as HTTP-to-file bridge. CLO3D worker processes command files.
Usage: python clo3d_api_server.py
"""

import json
import os
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

HOST = os.environ.get("CLO3D_API_HOST", "127.0.0.1")
PORT = int(os.environ.get("CLO3D_API_PORT", "9898"))
IPC_DIR = Path(os.environ.get("CLO3D_IPC_DIR", os.path.join(os.environ.get("TEMP", "."), "clo3d_ipc")))

CMD_DIR = IPC_DIR / "commands"
RESULT_DIR = IPC_DIR / "results"
for d in (CMD_DIR, RESULT_DIR):
    d.mkdir(parents=True, exist_ok=True)

print(f"[CLO3D-Bridge] IPC dir: {IPC_DIR}", flush=True)


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
            self._send(200, {"status": "ok"})

    def do_POST(self):
        try: data = self._read()
        except json.JSONDecodeError: self._send(400, {"error": "invalid JSON"}); return

        task_id = uuid.uuid4().hex[:12]
        rf = RESULT_DIR / f"{task_id}.json"
        ef = RESULT_DIR / f"{task_id}.error.json"

        if self.path == "/extract":
            cmd = {"action": "extract", "task_id": task_id,
                   "prj_path": data.get("prj_path", ""),
                   "output_dir": data.get("output_dir", "./output")}
        elif self.path == "/render":
            cmd = {"action": "render", "task_id": task_id,
                   "prj_path": data.get("prj_path", ""),
                   "material_assignments": data.get("material_assignments", {}),
                   "views": data.get("views", ["front", "back"]),
                   "output_dir": data.get("output_dir", "./output")}
        else:
            self._send(404, {"error": f"unknown: {self.path}"}); return

        (CMD_DIR / f"{task_id}.json").write_text(json.dumps(cmd, ensure_ascii=False))
        print(f"[CLO3D-Bridge] Queued {self.path} task={task_id}", flush=True)

        elapsed = 0
        while elapsed < 600:
            if rf.exists():
                self._send(200, json.loads(rf.read_text()))
                rf.unlink(missing_ok=True); return
            if ef.exists():
                self._send(500, {"status": "error", "error": ef.read_text()})
                ef.unlink(missing_ok=True); rf.unlink(missing_ok=True); return
            time.sleep(0.5); elapsed += 0.5
        self._send(504, {"status": "error", "error": "timeout"})


if __name__ == "__main__":
    srv = HTTPServer((HOST, PORT), Handler)
    print(f"[CLO3D-Bridge] Listening at http://{HOST}:{PORT}", flush=True)
    srv.serve_forever()
