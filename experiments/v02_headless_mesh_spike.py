"""
PRIVATE technical spike — not product code.

Calls the LOCAL Sims 4 Studio Blender addon in-process (sys.path to the
user install). Does not vendor, copy, or redistribute that addon.

Mesh-only: clone template.package, replace the largest MLOD, leave DST/OBJD/etc.

Run with Blender 4.4.3:

  blender.exe --background --python experiments/v02_headless_mesh_spike.py -- ^
    --blend fixtures\\v0.1-vase\\sims_ready.blend ^
    --template "C:\\Users\\Cliente-TechNew\\Desktop\\TheSims4Tool\\Vaso.package" ^
    --output output\\v02_mesh_spike.package
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import struct
import sys
import traceback
import zlib
from io import BytesIO
from mathutils import Matrix

# Vendor Package.__init__ calls shutil.abspath, which does not exist.
# Patch in our process only; do not edit the installed addon.
if not hasattr(shutil, "abspath"):
    shutil.abspath = os.path.abspath

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ADDONS_DEFAULT = os.path.join(
    os.environ.get("APPDATA", ""),
    "Blender Foundation", "Blender", "4.4", "scripts", "addons",
)
MLOD_TYPE = 0x01D10F34
HEADER_SIZE = 96


def log(msg):
    print(msg, flush=True)


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser(prog="v02_headless_mesh_spike")
    p.add_argument("--blend", required=True)
    p.add_argument("--template", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--addons", default=ADDONS_DEFAULT)
    return p.parse_args(argv)


def rotate_obj_headless(amount, axis):
    """Math equivalent of s4studio.blender.rotate_obj on Blender 4.4, no VIEW_3D.

    collect_mesh_data calls rotate_obj(-pi/2, 'X') then transform_apply(rotation=True).

    Original on 4.4: bpy.ops.transform.rotate(value=-amount, orient_axis=axis)
    Verified equivalent: matrix_world = Rotation(amount, 4, axis) @ matrix_world
    (NOT Rotation(-amount) — the operator sign convention differs from the value arg.)
    """
    import bpy
    obj = bpy.context.view_layer.objects.active
    if obj is None:
        log("[spike] rotate_obj_headless: no active object")
        return
    if axis[0] == "-":
        axis = axis[1]
        amount = amount * -1
    if bpy.app.version >= (5, 0, 0):
        amount *= -1
    R = Matrix.Rotation(amount, 4, axis)
    obj.matrix_world = R @ obj.matrix_world
    bpy.context.view_layer.update()
    log("[spike] rotate_obj headless amount=%.4f axis=%s" % (amount, axis))


def install_headless_patches():
    import s4studio.blender as s4b
    s4b.rotate_obj = rotate_obj_headless
    import s4studio.buybuild.blender as bb
    if getattr(bb, "rotate_obj", None) is not None:
        bb.rotate_obj = rotate_obj_headless
    log("[spike] monkeypatched rotate_obj (matrix equivalent, no VIEW_3D)")


def ensure_cuts():
    import bpy
    n = 0
    for obj in bpy.data.objects:
        if obj.type != "MESH" or not obj.name.startswith("s4studio_mesh_"):
            continue
        suffix = obj.name.split("_")[-1]
        current = ""
        try:
            current = str(obj.data.s4studio.cut or "").strip()
        except Exception as e:
            log("[spike] mesh %s has no s4studio.cut (%s)" % (obj.name, e))
            continue
        if not current:
            obj.data.s4studio.cut = suffix
            log("[spike] set %s cut=%s" % (obj.name, suffix))
        else:
            log("[spike] %s cut already=%s" % (obj.name, current))
        n += 1
    if n == 0:
        raise RuntimeError("no s4studio_mesh_* objects in blend")


def enable_io_sims():
    import addon_utils
    addon_utils.enable("io_sims")
    log("[spike] enabled addon io_sims")


def read_dbpf_index(path):
    """Public DBPF v2 index (observed on local packages). Not a copy of vendor code."""
    with open(path, "rb") as f:
        blob = f.read()
    if blob[:4] != b"DBPF":
        raise RuntimeError("not a DBPF: %s" % path)
    count = struct.unpack_from("<I", blob, 36)[0]
    index_size = struct.unpack_from("<I", blob, 44)[0]
    index_offset = struct.unpack_from("<I", blob, 64)[0]
    flags = struct.unpack_from("<I", blob, index_offset)[0]
    if flags != 0:
        raise RuntimeError("spike only handles index flags=0 (got 0x%X)" % flags)
    pos = index_offset + 4
    entries = []
    for _ in range(count):
        t, g, i_hi, i_lo, offset, file_size, mem_size, comp, unk = struct.unpack_from(
            "<IIIIIIIHH", blob, pos)
        pos += 32
        entries.append({
            "t": t,
            "g": g,
            "i": (i_hi << 32) | i_lo,
            "offset": offset,
            "file_size": file_size & 0x0FFFFFFF,
            "mem_size": mem_size,
            "comp_flag": comp,
            "compressed": comp == 0xFFFF,
            "unknown": unk,
            "raw": blob[offset:offset + (file_size & 0x0FFFFFFF)],
        })
    return blob[:HEADER_SIZE], entries, index_offset, index_size


def write_dbpf(header96, entries, out_path):
    payload = bytearray()
    payload += header96
    new_entries = []
    for e in entries:
        offset = len(payload)
        payload += e["raw"]
        ne = dict(e)
        ne["offset"] = offset
        ne["file_size"] = len(e["raw"])
        ne["comp_flag"] = 0xFFFF if e.get("compressed") else e.get("comp_flag", 0)
        new_entries.append(ne)
    index_offset = len(payload)
    payload += struct.pack("<I", 0)  # flags
    for e in new_entries:
        i_hi = e["i"] >> 32
        i_lo = e["i"] & 0xFFFFFFFF
        comp = e.get("comp_flag", 0)
        if e.get("compressed"):
            comp = 0xFFFF
        payload += struct.pack(
            "<IIIIIIIHH",
            e["t"], e["g"], i_hi, i_lo,
            e["offset"], e["file_size"] | 0x80000000, e["mem_size"],
            comp, e["unknown"],
        )
    index_size = len(payload) - index_offset
    struct.pack_into("<I", payload, 36, len(new_entries))
    struct.pack_into("<I", payload, 44, index_size)
    struct.pack_into("<I", payload, 64, index_offset)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(payload)
    return new_entries


def analyze_mlod(mlod, label):
    from s4studio.buybuild.geometry import ObjectMesh
    stats = {"label": label, "meshes": []}
    for i, m in enumerate(mlod.meshes):
        assert isinstance(m, ObjectMesh)
        verts = m.get_vertices(None)
        tris = m.get_triangles(None)
        mn = [1e9, 1e9, 1e9]
        mx = [-1e9, -1e9, -1e9]
        for v in verts:
            for j in range(3):
                mn[j] = min(mn[j], v.position[j])
                mx[j] = max(mx[j], v.position[j])
        stats["meshes"].append({
            "index": i,
            "vertices": len(verts),
            "triangles": len(tris),
            "bbox_min": mn,
            "bbox_max": mx,
        })
    return stats


def main():
    args = parse_args()
    blend = os.path.abspath(args.blend)
    template = os.path.abspath(args.template)
    output = os.path.abspath(args.output)
    addons = os.path.abspath(args.addons)

    if not os.path.isfile(blend):
        raise SystemExit("blend not found: %s" % blend)
    if not os.path.isfile(template):
        raise SystemExit("template package not found: %s" % template)
    if not os.path.isdir(addons):
        raise SystemExit("addons dir not found: %s" % addons)

    sys.path.insert(0, addons)

    import bpy
    from s4studio.buybuild.blender import save_lod
    from s4studio.buybuild.geometry import ModelLod
    from s4studio.data.package import Package

    log("[spike] blend=%s" % blend)
    log("[spike] template=%s" % template)
    log("[spike] output=%s" % output)
    log("[spike] addons=%s (import only, not copied)" % addons)

    bpy.ops.wm.open_mainfile(filepath=blend)
    enable_io_sims()
    install_headless_patches()
    ensure_cuts()

    header, raw_entries, _, _ = read_dbpf_index(template)
    mlod_raws = [e for e in raw_entries if e["t"] == MLOD_TYPE]
    if not mlod_raws:
        raise RuntimeError("template has no MLOD")
    chosen = max(mlod_raws, key=lambda e: e["mem_size"])
    log("[spike] MLOD candidates:")
    for e in mlod_raws:
        mark = " <=" if e is chosen else ""
        log("  t=%08X g=%08X i=%016X mem=%d file=%d comp_flag=%04X%s" % (
            e["t"], e["g"], e["i"], e["mem_size"], e["file_size"], e.get("comp_flag", 0), mark))
    replaced_key = {
        "t": "%08X" % chosen["t"],
        "g": "%08X" % chosen["g"],
        "i": "%016X" % chosen["i"],
        "mem_before": chosen["mem_size"],
        "file_before": chosen["file_size"],
        "compressed_before": chosen["compressed"],
        "comp_flag_before": "%04X" % chosen.get("comp_flag", 0),
    }

    blob = chosen["raw"]
    flag = chosen.get("comp_flag", 0)
    if flag == 0x5A42 or blob[:2] in (b"\x78\xda", b"\x78\x9c", b"\x78\x01"):
        log("[spike] zlib-decompressing MLOD (comp_flag=0x%04X)" % flag)
        blob = zlib.decompress(blob)
    elif chosen["compressed"] or chosen["mem_size"] > chosen["file_size"]:
        log("[spike] uncompressing MLOD with local Package.Compression")
        blob = Package.Compression.uncompress(
            BytesIO(blob), chosen["file_size"], chosen["mem_size"]).read()
    log("[spike] MLOD uncompressed bytes=%d" % len(blob))
    mlod = ModelLod()
    mlod.read(BytesIO(blob))
    stats_before = analyze_mlod(mlod, "template_mlod")
    log("[spike] MLOD before: %s" % json.dumps(stats_before, indent=2))
    log("[spike] save_lod (geometry_state='', static_pos_scale=0)")
    save_lod(mlod, "", 0.0)
    stats_after = analyze_mlod(mlod, "exported_mlod")
    log("[spike] MLOD after: %s" % json.dumps(stats_after, indent=2))

    buf = BytesIO()
    mlod.write(buf)
    mlod_bytes = buf.getvalue()
    log("[spike] new MLOD bytes=%d" % len(mlod_bytes))
    replaced_key["mem_after"] = len(mlod_bytes)

    found = False
    for e in raw_entries:
        if e["t"] == chosen["t"] and e["g"] == chosen["g"] and e["i"] == chosen["i"]:
            e["raw"] = mlod_bytes
            e["mem_size"] = len(mlod_bytes)
            e["compressed"] = False
            e["comp_flag"] = 0
            found = True
            break
    if not found:
        raise RuntimeError("failed to match MLOD TGI in raw DBPF index")

    write_dbpf(header, raw_entries, output)
    report = {
        "status": "wrote_package",
        "blend": blend,
        "template": template,
        "output": output,
        "replaced": replaced_key,
        "mlod_before": stats_before,
        "mlod_after": stats_after,
        "note": "mesh-only; DST/OBJD/catalog/other MLODs unchanged",
    }
    report_path = os.path.join(os.path.dirname(output), "v02_mesh_spike_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    log("[spike] wrote %s (%d bytes)" % (output, os.path.getsize(output)))
    log("[spike] report %s" % report_path)
    log("[spike] REPLACED TGI %s:%s:%s" % (
        replaced_key["t"], replaced_key["g"], replaced_key["i"]))
    log("[PASS] mesh-only package written (open in S4S to confirm geometry)")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
