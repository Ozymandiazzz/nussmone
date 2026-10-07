"""Experimental lower-LOD generator for the decorative-vase donor layout.

Requires the user's locally installed S4S Blender addon. The known-good high
detail MLOD is preserved; only the four lower/detail-proxy MLODs are changed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
import zlib
from io import BytesIO

sys.path.insert(0, os.path.dirname(__file__))
from v02_headless_mesh_spike import (ADDONS_DEFAULT, MLOD_TYPE, enable_io_sims,
                                     ensure_cuts, install_headless_patches,
                                     read_dbpf_index, write_dbpf)

GROUP_TARGETS = {1: 3000, 0x10000: 1500, 0x10001: 800, 0x10002: 750}


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blend", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--addons", default=ADDONS_DEFAULT)
    return parser.parse_args(argv)


def decode_mlod(entry):
    raw = entry["raw"]
    if entry["comp_flag"] == 0x5A42:
        return zlib.decompress(raw)
    if entry["compressed"]:
        from s4studio.data.package import Package
        return Package.Compression.uncompress(
            BytesIO(raw), entry["file_size"], entry["mem_size"]).read()
    if entry["mem_size"] != entry["file_size"]:
        raise ValueError("Unknown MLOD compression")
    return raw


def prepare_scene(blend, group, target):
    import bpy
    bpy.ops.wm.open_mainfile(filepath=blend)
    enable_io_sims()
    install_headless_patches()
    ensure_cuts()
    visual = bpy.data.objects.get("s4studio_mesh_1")
    if visual is None or visual.type != "MESH":
        raise ValueError("Blend lacks s4studio_mesh_1")
    if group >= 0x10000:
        proxy = bpy.data.objects.get("s4studio_mesh_0")
        if proxy is None or proxy.type != "MESH":
            raise ValueError("Blend lacks s4studio_mesh_0 for proxy LOD")
        proxy.data = visual.data.copy()
        proxy.data.s4studio.cut = "0"
        proxy.matrix_world = visual.matrix_world.copy()
        selected = proxy
    else:
        selected = visual
    original_faces = len(selected.data.polygons)
    if original_faces < 4:
        raise ValueError(f"Source mesh has only {original_faces} faces")
    if original_faces > target:
        modifier = selected.modifiers.new(name="CCStudio LOD", type="DECIMATE")
        modifier.ratio = max(0.01, target / original_faces)
        bpy.ops.object.select_all(action="DESELECT")
        selected.select_set(True)
        bpy.context.view_layer.objects.active = selected
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    return original_faces, len(selected.data.polygons)


def main():
    args = parse_args()
    for label, path in (("blend", args.blend), ("input", args.input)):
        if not os.path.isfile(path):
            raise ValueError(f"{label} missing: {path}")
    if os.path.abspath(args.input) == os.path.abspath(args.output):
        raise ValueError("Output must differ from input")
    sys.path.insert(0, args.addons)
    import bpy
    from s4studio.buybuild.blender import save_lod
    from s4studio.buybuild.geometry import ModelLod

    header, entries, _, _ = read_dbpf_index(args.input)
    targets = {e["g"]: e for e in entries if e["t"] == MLOD_TYPE and e["g"] in GROUP_TARGETS}
    if set(targets) != set(GROUP_TARGETS):
        raise ValueError(f"Unexpected MLOD groups: {sorted(targets)}")
    report = {"status": "RUNNING", "input": os.path.abspath(args.input),
              "output": os.path.abspath(args.output), "groups": []}
    for group, target in GROUP_TARGETS.items():
        entry = targets[group]
        source = decode_mlod(entry)
        lod = ModelLod()
        lod.read(BytesIO(source))
        expected_meshes = 2 if group == 1 else 1
        if len(lod.meshes) != expected_meshes:
            raise ValueError(f"Group {group:08X} has {len(lod.meshes)} meshes; expected {expected_meshes}")
        original_faces, prepared_faces = prepare_scene(args.blend, group, target)
        save_lod(lod, "", 0.0)
        visual_index = 1 if group == 1 else 0
        exported_faces = len(lod.meshes[visual_index].get_triangles(None))
        if not 0 < exported_faces <= target + 100:
            raise ValueError(f"Invalid exported triangle count for {group:08X}: {exported_faces}")
        stream = BytesIO()
        lod.write(stream)
        data = stream.getvalue()
        if data == source:
            raise ValueError(f"MLOD {group:08X} did not change")
        entry["raw"] = data
        entry["mem_size"] = len(data)
        entry["compressed"] = False
        entry["comp_flag"] = 0
        report["groups"].append({"group": f"{group:08X}", "target": target,
                                 "source_faces": original_faces,
                                 "prepared_faces": prepared_faces,
                                 "exported_triangles": exported_faces,
                                 "bytes_before": len(source), "bytes_after": len(data)})
        print(f"[lod] {group:08X}: {original_faces} -> {exported_faces} triangles", flush=True)
    write_dbpf(header, entries, args.output)
    _, reopened, _, _ = read_dbpf_index(args.output)
    if len(reopened) != len(entries) or [e["raw"] for e in reopened] != [e["raw"] for e in entries]:
        raise ValueError("DBPF roundtrip failed")
    report["status"] = "PROGRAMMATIC_PASS"
    os.makedirs(os.path.dirname(os.path.abspath(args.report)), exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    print(f"[PASS] {args.output}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
