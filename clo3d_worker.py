"""
CLO3D Worker — runs inside CLO3D Script Editor.

Checks for command files from the standalone HTTP bridge, processes
them using CLO3D API on the main thread, writes results back.

Usage: CLO3D → Script → Script Editor → Open → Run
        The script processes one batch of commands then exits.
        Re-run to process the next batch.
"""

import json
import os
import time
import traceback
from datetime import datetime
from pathlib import Path

IPC_DIR = Path(os.environ.get("CLO3D_IPC_DIR", os.path.join(os.environ.get("TEMP", "."), "clo3d_ipc")))
CMD_DIR = IPC_DIR / "commands"
RESULT_DIR = IPC_DIR / "results"

print(f"[CLO3D-Worker] IPC dir: {IPC_DIR}", flush=True)
print(f"[CLO3D-Worker] Loading CLO3D API...", flush=True)

from import_api import ImportFile
from export_api import ExportRenderingImage
from fabric_api import AddFabric, AssignFabricToPattern
from pattern_api import GetPatternCount, GetPatternPieceName
from utility_api import Simulate
print("[CLO3D-Worker] CLO3D API loaded", flush=True)


def do_extract(prj_path, output_dir):
    if not os.path.exists(prj_path):
        return {"status": "error", "error": f"File not found: {prj_path}"}
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    ImportFile(prj_path)
    count = GetPatternCount()
    print(f"  Extracting {count} pieces", flush=True)
    pieces = []
    for i in range(count):
        try: name = GetPatternPieceName(i)
        except Exception: name = f"piece_{i}"
        pieces.append({"name": name, "label": name, "index": i})
    layout = str(out / "layout.png")
    try: ExportRenderingImage(layout, False, 0)
    except Exception: layout = ""
    return {"status": "success", "piece_count": count, "pieces": pieces, "layout_image": layout}


def do_render(prj_path, materials, views, output_dir):
    if not os.path.exists(prj_path):
        return {"status": "error", "error": f"File not found: {prj_path}"}
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    print(f"  Loading: {Path(prj_path).name}", flush=True)
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
            for n, i in name_to_idx.items():
                if piece_name in n or n in piece_name: idx = i; break
        if idx is None: continue
        try:
            fab = AddFabric(mat_path)
            AssignFabricToPattern(fab, idx)
            print(f"    {piece_name}[{idx}] OK", flush=True)
        except Exception as exc:
            print(f"    {piece_name}[{idx}] FAILED: {exc}", flush=True)
    try:
        Simulate(100)
        print("  Simulated 100 steps", flush=True)
    except Exception as exc:
        print(f"  Simulation: {exc}", flush=True)
    images = {}
    for view in views:
        p = str(out / f"render_{view}.png")
        ExportRenderingImage(p, False, 0)
        images[view] = p
        print(f"  {view}: {p}", flush=True)
    return {"status": "success", "images": images}


# Process all pending commands
cmd_files = sorted(CMD_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)

if not cmd_files:
    print("[CLO3D-Worker] No pending commands.", flush=True)
else:
    print(f"[CLO3D-Worker] Processing {len(cmd_files)} command(s)...", flush=True)
    for cf in cmd_files:
        try:
            cmd = json.loads(cf.read_text())
            task_id = cmd["task_id"]
            action = cmd["action"]
            print(f"[CLO3D-Worker] Task {task_id}: {action}", flush=True)

            if action == "extract":
                r = do_extract(cmd.get("prj_path", ""), cmd.get("output_dir", "./output"))
            elif action == "render":
                r = do_render(cmd.get("prj_path", ""), cmd.get("material_assignments", {}),
                              cmd.get("views", ["front", "back"]), cmd.get("output_dir", "./output"))
            else:
                r = {"status": "error", "error": f"unknown action: {action}"}

            (RESULT_DIR / f"{task_id}.json").write_text(json.dumps(r))
            cf.unlink()
            print(f"[CLO3D-Worker] Task {task_id}: done", flush=True)
        except Exception as exc:
            traceback.print_exc()
            try:
                (RESULT_DIR / f"{cmd['task_id']}.error.json").write_text(str(exc))
                cf.unlink()
            except Exception:
                pass

print("[CLO3D-Worker] Done. Re-run to process next batch.", flush=True)
