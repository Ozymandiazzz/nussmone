"""Read-only inventory of donor MLOD groups using the locally installed S4S addon."""
from __future__ import annotations

import json
import os
import shutil
import sys
import zlib
from io import BytesIO

if not hasattr(shutil, "abspath"):
    shutil.abspath = os.path.abspath

sys.path.insert(0, os.path.dirname(__file__))
from v02_headless_mesh_spike import ADDONS_DEFAULT, MLOD_TYPE, read_dbpf_index


def main() -> None:
    if "--" not in sys.argv or len(sys.argv) < sys.argv.index("--") + 2:
        raise SystemExit("usage: blender --background --python v03_lod_inventory.py -- donor.package")
    donor = sys.argv[sys.argv.index("--") + 1]
    sys.path.insert(0, ADDONS_DEFAULT)
    from s4studio.buybuild.geometry import ModelLod

    _, entries, _, _ = read_dbpf_index(donor)
    result = []
    for entry in entries:
        if entry["t"] != MLOD_TYPE:
            continue
        raw = entry["raw"]
        if entry["comp_flag"] == 0x5A42:
            raw = zlib.decompress(raw)
        elif entry["compressed"]:
            from s4studio.data.package import Package
            raw = Package.Compression.uncompress(
                BytesIO(raw), entry["file_size"], entry["mem_size"]).read()
        lod = ModelLod()
        lod.read(BytesIO(raw))
        meshes = []
        for index, mesh in enumerate(lod.meshes):
            meshes.append({"cut": index, "vertices": len(mesh.get_vertices(None)),
                           "triangles": len(mesh.get_triangles(None)),
                           "shadow": mesh.is_dropshadow()})
        result.append({"group": f"{entry['g']:08X}",
                       "instance": f"{entry['i']:016X}", "meshes": meshes})
    print("LOD_INVENTORY_JSON=" + json.dumps(result))


if __name__ == "__main__":
    main()
