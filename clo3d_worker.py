"""
CLO3D Worker — run once in CLO3D Script Editor per render batch.
Processes all pending command files, then exits. Re-run for next batch.
"""
import json, os, traceback
from pathlib import Path

IPC = Path(os.environ.get("CLO3D_IPC_DIR", os.path.join(os.environ.get("TEMP","."),"clo3d_ipc")))
CMD, RES = IPC / "commands", IPC / "results"

print("[Worker] Loading CLO3D API...", flush=True)
from import_api import ImportFile
from export_api import ExportRenderingImage
from fabric_api import AddFabric, AssignFabricToPattern
from pattern_api import GetPatternCount, GetPatternPieceName
from utility_api import Simulate
print("[Worker] Ready.", flush=True)


def do_extract(prj_path, output_dir):
    if not os.path.exists(prj_path):
        return {"status":"error","error":"File not found"}
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    ImportFile(prj_path)
    n = GetPatternCount()
    print(f"  {n} pieces", flush=True)
    pieces = []
    for i in range(n):
        try: nm = GetPatternPieceName(i)
        except: nm = f"piece_{i}"
        pieces.append({"name": nm, "label": nm, "index": i})
    ly = str(out / "layout.png")
    try: ExportRenderingImage(ly, False, 0)
    except: ly = ""
    return {"status":"success","piece_count":n,"pieces":pieces,"layout_image":ly}


def do_render(prj_path, materials, views, output_dir):
    if not os.path.exists(prj_path):
        return {"status":"error","error":"File not found"}
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    print(f"  Loading: {Path(prj_path).name}", flush=True)
    ImportFile(prj_path)
    n = GetPatternCount()
    ni = {}
    for i in range(n):
        try: ni[GetPatternPieceName(i)] = i
        except: ni[f"piece_{i}"] = i
    for pn, mp in materials.items():
        if not mp or not os.path.exists(mp): continue
        idx = ni.get(pn)
        if idx is None:
            for nn, ii in ni.items():
                if pn in nn or nn in pn: idx = ii; break
        if idx is None: continue
        try:
            f = AddFabric(mp); AssignFabricToPattern(f, idx)
            print(f"    {pn}[{idx}] OK", flush=True)
        except Exception as ex:
            print(f"    {pn}[{idx}] FAILED: {ex}", flush=True)
    try: Simulate(100); print("  Simulated 100 steps", flush=True)
    except Exception as ex: print(f"  Sim: {ex}", flush=True)
    im = {}
    for vw in views:
        p = str(out / f"render_{vw}.png")
        ExportRenderingImage(p, False, 0)
        im[vw] = p; print(f"  {vw}: {p}", flush=True)
    return {"status":"success","images":im}


cmds = sorted(CMD.glob("*.json"), key=lambda f: f.stat().st_mtime)
if not cmds:
    print("[Worker] No pending commands.", flush=True)
else:
    print(f"[Worker] Processing {len(cmds)} command(s)...", flush=True)
    for cf in cmds:
        try:
            c = json.loads(cf.read_text()); tid = c["task_id"]; a = c["action"]
            print(f"[Worker] {tid}: {a}", flush=True)
            if a == "extract":
                r = do_extract(c.get("prj_path",""), c.get("output_dir","./output"))
            elif a == "render":
                r = do_render(c.get("prj_path",""), c.get("material_assignments",{}),
                              c.get("views",["front","back"]), c.get("output_dir","./output"))
            else:
                r = {"status":"error","error":f"unknown:{a}"}
            (RES / f"{tid}.json").write_text(json.dumps(r))
            cf.unlink()
            print(f"[Worker] {tid}: done", flush=True)
        except Exception as ex:
            traceback.print_exc()
            try: (RES / f"{c['task_id']}.error.json").write_text(str(ex)); cf.unlink()
            except: pass
print("[Worker] Done. Re-run for next batch.", flush=True)
