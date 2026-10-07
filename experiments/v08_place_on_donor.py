"""Anchor the engine's s4studio_mesh_1 on the donor object's own geometry.

The v0.1 engine fits the GLB into the blend template's target mesh. The
recipe template (templates/decor_vase/template.blend, the validated v0.1
object) is not the NovoVasoTeste2 donor: its target sits off-centre and 6 cm
above the floor, so every package built from it placed the new mesh off the
donor's footprint. This stage translates (never scales or rotates) the mesh so
its game-space bounds are centred on the donor's visual LOD0 in X/Z and rest on
the donor's floor in Y. Run with Blender --factory-startup; imports no Sims 4
Studio code.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import traceback
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(__file__))
from independent_rcol import Rcol
from v02_identity_clone import h, read_package

MLOD = 0x01D10F34
# Blender Z-up -> game Y-up, as in both independent MLOD writers.
TO_GAME = Matrix.Rotation(-math.pi / 2, 4, 'X')


def arguments():
    argv = sys.argv
    argv = argv[argv.index('--') + 1:] if '--' in argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blend', type=Path, required=True)
    parser.add_argument('--donor', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    return parser.parse_args(argv)


def donor_anchor(donor: Path) -> tuple[float, ...]:
    _, entries = read_package(donor)
    lod0 = [e for e in entries if e['type'] == MLOD and e['group'] == 0]
    if len(lod0) != 1:
        raise ValueError('Donor has no single visual LOD0 MLOD')
    meshes = Rcol.parse(lod0[0]['data']).inspect_mlod()
    visual = max(meshes, key=lambda mesh: mesh['vertex_count'])
    return visual['bounds']


def game_bounds(obj) -> tuple[float, ...]:
    transform = TO_GAME @ obj.matrix_world
    points = [transform @ vertex.co for vertex in obj.data.vertices]
    if not points:
        raise ValueError('s4studio_mesh_1 is empty')
    return (*(min(p[i] for p in points) for i in range(3)),
            *(max(p[i] for p in points) for i in range(3)))


def main():
    args = arguments()
    if any(name == 's4studio' or name.startswith('s4studio.') for name in sys.modules):
        raise RuntimeError('S4S addon loaded; use Blender --factory-startup')
    if args.blend.resolve() == args.output.resolve():
        raise ValueError('Output must differ from input blend')
    anchor = donor_anchor(args.donor)
    bpy.ops.wm.open_mainfile(filepath=str(args.blend))
    obj = bpy.data.objects.get('s4studio_mesh_1')
    if obj is None or obj.type != 'MESH':
        raise ValueError('Blend has no s4studio_mesh_1')
    before = game_bounds(obj)
    target_x = (anchor[0] + anchor[3]) / 2
    target_z = (anchor[2] + anchor[5]) / 2
    game_delta = Vector((target_x - (before[0] + before[3]) / 2,
                         anchor[1] - before[1],
                         target_z - (before[2] + before[5]) / 2))
    blender_delta = TO_GAME.to_3x3().inverted() @ game_delta
    obj.matrix_world = Matrix.Translation(blender_delta) @ obj.matrix_world
    bpy.context.view_layer.update()
    after = game_bounds(obj)
    centre_error = max(abs((after[0] + after[3]) / 2 - target_x),
                       abs((after[2] + after[5]) / 2 - target_z),
                       abs(after[1] - anchor[1]))
    if centre_error > 1e-4:
        raise ValueError(f'Placement missed donor anchor by {centre_error:.6f}')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output), copy=True)
    report = {'status': 'PROGRAMMATIC_PASS', 'blend': str(args.blend),
              'output': str(args.output), 'donor': str(args.donor),
              'donor_lod0_bounds': list(anchor),
              'game_bounds_before': list(before), 'game_bounds_after': list(after),
              'game_translation': list(game_delta),
              'dimensions': [after[i + 3] - after[i] for i in range(3)],
              'donor_dimensions': [anchor[i + 3] - anchor[i] for i in range(3)],
              's4s_loaded': any(name.startswith('s4studio') for name in sys.modules),
              'output_sha256': h(args.output.read_bytes())}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('PLACE_ON_DONOR_PASS=' + json.dumps(report), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
