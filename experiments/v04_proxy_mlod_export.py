"""Blender-only experimental exporter for one position-only proxy MLOD.

No Sims 4 Studio import. Supports the observed decor-vase group 00010000.
Run Blender with --factory-startup to keep installed addons disabled.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import struct
import sys
import traceback
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(__file__))
from independent_rcol import Rcol, u32
from v02_identity_clone import h, read_package, write_package

MLOD = 0x01D10F34
GROUP_TARGETS = {0x00010000: 1500, 0x00010001: 800, 0x00010002: 750}


def arguments():
    argv = sys.argv
    argv = argv[argv.index('--') + 1:] if '--' in argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blend', required=True, type=Path)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--target-faces', type=int, default=1500)
    parser.add_argument('--all-proxies', action='store_true')
    return parser.parse_args(argv)


def geometry(blend: Path, target_faces: int):
    if any(name == 's4studio' or name.startswith('s4studio.') for name in sys.modules):
        raise RuntimeError('S4S addon is loaded; run Blender with --factory-startup')
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    source = bpy.data.objects.get('s4studio_mesh_1')
    if source is None or source.type != 'MESH':
        raise ValueError('Blend has no visual mesh')
    evaluated = source.evaluated_get(bpy.context.evaluated_depsgraph_get())
    copied = bpy.data.meshes.new_from_object(evaluated)
    temp = bpy.data.objects.new('CCStudio proxy export', copied)
    bpy.context.scene.collection.objects.link(temp)
    temp.matrix_world = source.matrix_world.copy()
    original_faces = len(copied.polygons)
    if original_faces > target_faces:
        modifier = temp.modifiers.new('Proxy decimation', 'DECIMATE')
        modifier.ratio = max(0.01, target_faces / original_faces)
        bpy.ops.object.select_all(action='DESELECT')
        temp.select_set(True)
        bpy.context.view_layer.objects.active = temp
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    bm = bmesh.new()
    bm.from_mesh(temp.data)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    unused = [vertex for vertex in bm.verts if not vertex.link_faces]
    if unused:
        bmesh.ops.delete(bm, geom=unused, context='VERTS')
    bm.to_mesh(temp.data)
    bm.free()
    temp.data.update()
    transform = Matrix.Rotation(-math.pi / 2, 4, 'X') @ temp.matrix_world
    positions = [tuple(transform @ vertex.co) for vertex in temp.data.vertices]
    triangles = [tuple(poly.vertices) for poly in temp.data.polygons]
    if not positions or not triangles or len(positions) >= 32767:
        raise ValueError('Proxy geometry outside supported limits')
    return original_faces, positions, triangles


def encode_proxy(rcol: Rcol, positions, triangles) -> Rcol:
    meshes = rcol.inspect_mlod()
    if len(meshes) != 1 or meshes[0]['vertex_stride'] != 8 or meshes[0]['refs']['vrtf'] is not None:
        raise ValueError('Expected one position-only proxy mesh')
    mesh = meshes[0]
    base = next(i for i, chunk in enumerate(rcol.chunks) if chunk[:4] == b'MLOD')
    mlod = bytearray(rcol.chunks[base])
    entry_start = 16
    entry_size = u32(mlod, 12)
    if entry_size < 72:
        raise ValueError('Proxy MLOD entry too short')
    vertex_count = len(positions)
    triangle_count = len(triangles)
    vertex_payload = bytearray()
    for position in positions:
        quantized = [max(-32767, min(32767, round(component * 32767)))
                     for component in position]
        vertex_payload.extend(struct.pack('<4h', *quantized, 32767))
    vbuf_index = mesh['refs']['vbuf']
    vbuf = rcol.chunks[vbuf_index][:16] + vertex_payload

    previous = 0
    index_payload = bytearray()
    for triangle in triangles:
        for index in triangle:
            delta = index - previous
            if not -32768 <= delta <= 32767:
                raise ValueError('Index delta exceeds int16')
            index_payload.extend(struct.pack('<h', delta))
            previous = index
    ibuf_index = mesh['refs']['ibuf']
    ibuf_header = rcol.chunks[ibuf_index][:16]
    if not u32(ibuf_header, 8) & 1:
        raise ValueError('Expected delta-encoded IBUF')
    ibuf = ibuf_header + index_payload

    struct.pack_into('<I', mlod, entry_start + 24, 0)  # stream offset
    struct.pack_into('<I', mlod, entry_start + 28, 0)  # start vertex
    struct.pack_into('<I', mlod, entry_start + 32, 0)  # start index
    struct.pack_into('<I', mlod, entry_start + 36, 0)  # min vertex index
    struct.pack_into('<II', mlod, entry_start + 40, vertex_count, triangle_count)
    mins = [min(vertex[axis] for vertex in positions) for axis in range(3)]
    maxs = [max(vertex[axis] for vertex in positions) for axis in range(3)]
    struct.pack_into('<6f', mlod, entry_start + 48, *mins, *maxs)
    result = rcol.replace(base, bytes(mlod)).replace(vbuf_index, bytes(vbuf))
    result = result.replace(ibuf_index, bytes(ibuf))
    parsed = Rcol.parse(result.to_bytes())
    check = parsed.inspect_mlod()[0]
    if check['vertex_count'] != vertex_count or check['triangle_count'] != triangle_count:
        raise ValueError('Independent proxy roundtrip count mismatch')
    return parsed


def main():
    args = arguments()
    if not args.blend.is_file() or not args.input.is_file():
        raise ValueError('Blend or input package missing')
    if args.input.resolve() == args.output.resolve():
        raise ValueError('Output must differ from input')
    if not 100 <= args.target_faces <= 10000:
        raise ValueError('Target faces outside supported range')
    header, entries = read_package(args.input)
    original_payloads = [entry['data'] for entry in entries]
    targets = GROUP_TARGETS if args.all_proxies else {0x00010000: args.target_faces}
    groups = []
    changed_indexes = []
    for group, target in targets.items():
        original_faces, positions, triangles = geometry(args.blend, target)
        matches = [e for e in entries if e['type'] == MLOD and e['group'] == group]
        if len(matches) != 1:
            raise ValueError(f'Expected one proxy MLOD {group:08X}')
        old_data = matches[0]['data']
        replacement = encode_proxy(Rcol.parse(old_data), positions, triangles).to_bytes()
        matches[0]['data'] = replacement
        matches[0]['raw'] = replacement
        matches[0]['comp'] = 0
        changed_indexes.append(next(i for i, entry in enumerate(entries) if entry is matches[0]))
        groups.append({'group': f'{group:08X}', 'target': target,
                       'source_faces': original_faces, 'exported_vertices': len(positions),
                       'exported_triangles': len(triangles),
                       'old_mlod_sha256': h(old_data), 'new_mlod_sha256': h(replacement)})
    write_package(header, entries, args.output)
    _, check_entries = read_package(args.output)
    if len(check_entries) != len(entries) or any(
            before['data'] != after['data'] for before, after in zip(entries, check_entries)):
        raise ValueError('DBPF roundtrip changed resource payloads')
    changed = [index for index, (old, after) in enumerate(zip(original_payloads, check_entries))
               if old != after['data']]
    if sorted(changed) != sorted(changed_indexes):
        raise ValueError(f'Unexpected resource changes: {changed}')
    report = {'status': 'PROGRAMMATIC_PASS', 'groups': groups,
              'changed_resource_count': len(changed),
              's4s_loaded': any(name.startswith('s4studio') for name in sys.modules),
              'input': str(args.input), 'output': str(args.output)}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('INDEPENDENT_PROXY_PASS=' + json.dumps(report), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
