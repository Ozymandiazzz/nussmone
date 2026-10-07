"""Blender-only visual MLOD writer for the observed decorative-vase layout.

Replaces visual cut 1 in groups 00000000 and 00000001. Run with
--factory-startup; this script imports no Sims 4 Studio code.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import struct
import sys
import traceback
import zlib
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix

sys.path.insert(0, os.path.dirname(__file__))
from independent_rcol import Rcol, u32
from v02_identity_clone import h, read_package, write_package

MLOD = 0x01D10F34
MODL = 0x01661233
GROUP_TARGETS = {0: None, 1: 3000}
MODL_TARGET = 240
EXPECTED_VRTF = bytes.fromhex(
    '5652544602000000200000000700000000000000'
    '00000700010008080200060c0300041004000814050008180201061c')


def arguments():
    argv = sys.argv
    argv = argv[argv.index('--') + 1:] if '--' in argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blend', type=Path, required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    return parser.parse_args(argv)


def mesh_from_blend(blend: Path, target_faces: int | None):
    if any(name == 's4studio' or name.startswith('s4studio.') for name in sys.modules):
        raise RuntimeError('S4S addon loaded; use Blender --factory-startup')
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    source = bpy.data.objects.get('s4studio_mesh_1')
    if source is None or source.type != 'MESH':
        raise ValueError('Blend has no s4studio_mesh_1')
    evaluated = source.evaluated_get(bpy.context.evaluated_depsgraph_get())
    copied = bpy.data.meshes.new_from_object(evaluated)
    temp = bpy.data.objects.new('CCStudio visual export', copied)
    bpy.context.scene.collection.objects.link(temp)
    temp.matrix_world = source.matrix_world.copy()
    source_faces = len(copied.polygons)
    if target_faces and source_faces > target_faces:
        modifier = temp.modifiers.new('Visual LOD decimation', 'DECIMATE')
        modifier.ratio = max(0.01, target_faces / source_faces)
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
    mesh = temp.data
    mesh.update()
    if 'uv_0' not in mesh.uv_layers:
        raise ValueError('Visual mesh lacks uv_0')
    mesh.calc_tangents(uvmap='uv_0')
    transform = Matrix.Rotation(-math.pi / 2, 4, 'X') @ temp.matrix_world
    normal_transform = transform.to_3x3().inverted().transposed()
    positions = [tuple(transform @ vertex.co) for vertex in mesh.vertices]
    corners = []
    uv_layer = mesh.uv_layers['uv_0']
    for polygon in mesh.polygons:
        if len(polygon.loop_indices) != 3:
            raise ValueError('Triangulation failed')
        face = []
        for loop_index in polygon.loop_indices:
            loop = mesh.loops[loop_index]
            normal = (normal_transform @ mesh.corner_normals[loop_index].vector).normalized()
            tangent = (normal_transform @ loop.tangent).normalized()
            uv = uv_layer.data[loop_index].uv
            face.append((positions[loop.vertex_index], tuple(normal), tuple(tangent),
                         tuple(uv), loop.bitangent_sign))
        corners.append(face)
    return source_faces, corners


def packed_color(vector, alpha: int) -> bytes:
    channels = [max(0, min(255, round(component * 127 + 128))) for component in vector]
    return bytes((*channels, alpha))


def pack_mesh(corners):
    all_corners = [corner for face in corners for corner in face]
    u_values = [corner[3][0] for corner in all_corners]
    v_values = [1.0 - corner[3][1] for corner in all_corners]
    uv_scale_u = max(max(abs(value) for value in u_values), 1e-6) / 32767.0
    uv_scale_v = max(max(abs(value) for value in v_values), 1e-6) / 32767.0
    packed_vertices = []
    lookup = {}
    indices = []
    mins = [float('inf')] * 3
    maxs = [float('-inf')] * 3
    for corner in all_corners:
        position, normal, tangent, uv, sign = corner
        for axis, value in enumerate(position):
            mins[axis] = min(mins[axis], value)
            maxs[axis] = max(maxs[axis], value)
        p = [round(value * 32766) for value in position]
        if any(not -32768 <= value <= 32767 for value in p):
            raise ValueError('Position outside donor quantization range')
        uv0 = (round(uv[0] / uv_scale_u), round((1.0 - uv[1]) / uv_scale_v))
        if any(not -32768 <= value <= 32767 for value in uv0):
            raise ValueError('UV outside signed-short range')
        n_alpha = 128 if normal[2] >= 0 else 255
        t_alpha = 255 if sign >= 0 else 1
        packed = (struct.pack('<4h', *p, 32766) + packed_color(normal, n_alpha) +
                  struct.pack('<2h', *uv0) + b'\x00\x00\x00\x00' +
                  b'\xff\x00\x00\x00' + packed_color(tangent, t_alpha) +
                  struct.pack('<2h', 0, 32767))
        if len(packed) != 32:
            raise AssertionError('Visual vertex stride changed')
        index = lookup.get(packed)
        if index is None:
            index = len(packed_vertices)
            lookup[packed] = index
            packed_vertices.append(packed)
        indices.append(index)
    if not packed_vertices or len(packed_vertices) > 32767:
        raise ValueError('Vertex count outside signed-16 index range')
    previous = 0
    encoded_indices = bytearray()
    for index in indices:
        delta = index - previous
        if not -32768 <= delta <= 32767:
            raise ValueError('Index delta outside signed-16 range')
        encoded_indices.extend(struct.pack('<h', delta))
        previous = index
    return (b''.join(packed_vertices), bytes(encoded_indices),
            len(packed_vertices), len(corners), (*mins, *maxs),
            (uv_scale_u, uv_scale_v))


def patch_uv_materials(rcol: Rcol, uv_scales) -> Rcol:
    result = rcol
    changed = 0
    for index, chunk in enumerate(rcol.chunks):
        if chunk[:4] != b'MATD' or len(chunk) not in (704, 736):
            continue
        at = 648 if len(chunk) == 704 else 680
        patched = bytearray(chunk)
        struct.pack_into('<4f', patched, at, uv_scales[0], uv_scales[1],
                         1.0 / 32767.0, 1.0 / 32767.0)
        result = result.replace(index, bytes(patched))
        changed += 1
    if changed != 4:
        raise ValueError(f'Expected four material states, got {changed}')
    return result


def encode_visual(rcol: Rcol, packed):
    vertices, indices, vertex_count, triangles, bounds, uv_scales = packed
    meshes = rcol.inspect_mlod()
    if len(meshes) != 2 or meshes[1]['vertex_stride'] != 32:
        raise ValueError('Expected two-cut decorative visual MLOD')
    mesh = meshes[1]
    if rcol.chunks[mesh['refs']['vrtf']] != EXPECTED_VRTF:
        raise ValueError('Donor VRTF differs from supported 32-byte layout')
    base = next(index for index, chunk in enumerate(rcol.chunks) if chunk[:4] == b'MLOD')
    mlod = bytearray(rcol.chunks[base])
    entry_at = 12 + 4 + u32(mlod, 12) + 4
    if u32(mlod, entry_at - 4) < 72:
        raise ValueError('Visual MLOD entry truncated')
    struct.pack_into('<4I', mlod, entry_at + 24, 0, 0, 0, 0)
    struct.pack_into('<2I', mlod, entry_at + 40, vertex_count, triangles)
    struct.pack_into('<6f', mlod, entry_at + 48, *bounds)
    vbuf_index, ibuf_index = mesh['refs']['vbuf'], mesh['refs']['ibuf']
    vbuf = rcol.chunks[vbuf_index][:16] + vertices
    ibuf_header = rcol.chunks[ibuf_index][:16]
    if not u32(ibuf_header, 8) & 1:
        raise ValueError('Visual IBUF is not delta encoded')
    result = rcol.replace(base, bytes(mlod)).replace(vbuf_index, vbuf)
    result = result.replace(ibuf_index, ibuf_header + indices)
    result = result.sync_vbsi(vbuf_index, vertex_count)
    result = patch_uv_materials(result, uv_scales)
    reopened = Rcol.parse(result.to_bytes())
    check = reopened.inspect_mlod()[1]
    if check['vertex_count'] != vertex_count or check['triangle_count'] != triangles:
        raise ValueError('Visual MLOD roundtrip count mismatch')
    return reopened


def main():
    args = arguments()
    if not args.blend.is_file() or not args.input.is_file():
        raise ValueError('Blend or input package missing')
    if args.input.resolve() == args.output.resolve():
        raise ValueError('Output must differ from input')
    header, entries = read_package(args.input)
    original = [entry['data'] for entry in entries]
    group_stats = []
    all_bounds = []
    for group, target in GROUP_TARGETS.items():
        source_faces, corners = mesh_from_blend(args.blend, target)
        packed = pack_mesh(corners)
        all_bounds.append(packed[4])
        matches = [entry for entry in entries if entry['type'] == MLOD and entry['group'] == group]
        if len(matches) != 1:
            raise ValueError(f'Expected one MLOD group {group:08X}')
        matches[0]['data'] = encode_visual(Rcol.parse(matches[0]['data']), packed).to_bytes()
        # Every in-game PASS package stores its MLODs zlib-compressed.
        matches[0]['raw'] = zlib.compress(matches[0]['data'], 9)
        matches[0]['comp'] = 0x5A42
        group_stats.append({'group': f'{group:08X}', 'source_faces': source_faces,
                            'vertices': packed[2], 'triangles': packed[3],
                            'bounds': packed[4], 'uv_scales': packed[5]})
    modls = [entry for entry in entries if entry['type'] == MODL]
    if len(modls) != 1:
        raise ValueError('Expected one MODL with embedded low-detail MLOD')
    source_faces, corners = mesh_from_blend(args.blend, MODL_TARGET)
    packed = pack_mesh(corners)
    all_bounds.append(packed[4])
    modl = Rcol.parse(modls[0]['data'])
    modl = encode_visual(modl, packed)
    modl_index = next(i for i, chunk in enumerate(modl.chunks) if chunk[:4] == b'MODL')
    modl_chunk = bytearray(modl.chunks[modl_index])
    old_bounds = struct.unpack_from('<6f', modl_chunk, 12)
    mins = [min([old_bounds[i]] + [bounds[i] for bounds in all_bounds]) for i in range(3)]
    maxs = [max([old_bounds[i + 3]] + [bounds[i + 3] for bounds in all_bounds])
            for i in range(3)]
    new_bounds = (*mins, *maxs)
    struct.pack_into('<6f', modl_chunk, 12, *new_bounds)
    modl_data = modl.replace(modl_index, bytes(modl_chunk)).to_bytes()
    modls[0]['data'] = modl_data
    if modls[0]['comp'] == 0x5A42:
        prefix = b'ZB' if modls[0]['raw'].startswith(b'ZB') else b''
        modls[0]['raw'] = prefix + zlib.compress(modl_data, 9)
    elif modls[0]['comp'] == 0:
        modls[0]['raw'] = modl_data
    else:
        raise ValueError('Unsupported MODL compression')
    group_stats.append({'group': 'MODL_EMBEDDED', 'source_faces': source_faces,
                        'vertices': packed[2], 'triangles': packed[3],
                        'bounds': packed[4], 'modl_bounds': new_bounds,
                        'uv_scales': packed[5]})
    write_package(header, entries, args.output)
    _, reopened = read_package(args.output)
    if len(reopened) != len(entries) or any(a['data'] != b['data'] for a, b in zip(entries, reopened)):
        raise ValueError('DBPF roundtrip mismatch')
    changed = [index for index, (old, new) in enumerate(zip(original, reopened))
               if old != new['data']]
    changed_types = [(reopened[index]['type'], reopened[index]['group']) for index in changed]
    if len(changed) != 3 or set(changed_types) != {(MLOD, 0), (MLOD, 1),
                                                  (MODL, modls[0]['group'])}:
        raise ValueError(f'Unexpected resource changes: {changed}')
    report = {'status': 'PROGRAMMATIC_PASS', 'input': str(args.input),
              'output': str(args.output), 'groups': group_stats,
              'changed_resource_count': len(changed),
              's4s_loaded': any(name.startswith('s4studio') for name in sys.modules),
              'output_sha256': h(args.output.read_bytes())}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('INDEPENDENT_VISUAL_PASS=' + json.dumps(report), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
