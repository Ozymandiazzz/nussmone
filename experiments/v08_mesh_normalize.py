"""Bring mesh resources from any exporter to the in-game PASS layout.

Rewrites each MLOD/MODL mesh's VBSI (vertex count and byte offset) to match
the mesh entry, and stores MLOD/MODL zlib-compressed like the donor and every
in-game PASS package. Used after the s4s_local exporter, whose output keeps
the donor VBSI count; the independent writers already emit this layout.
Standard library only.
"""
from __future__ import annotations

import argparse
import json
import struct
import zlib
from pathlib import Path

from independent_rcol import Rcol, u32
from v02_identity_clone import h, read_package, write_package

MLOD = 0x01D10F34
MODL = 0x01661233


def normalize(rcol: Rcol) -> tuple[Rcol, list[dict]]:
    base = next(i for i, chunk in enumerate(rcol.chunks) if chunk[:4] == b'MLOD')
    mlod = rcol.chunks[base]
    changes = []
    pos = 12
    for mesh in range(u32(mlod, 8)):
        size = u32(mlod, pos)
        entry = mlod[pos + 4:pos + 4 + size]
        pos += 4 + size
        vbuf = rcol.chunk_ref(u32(entry, 12), base)
        index = rcol.vbsi_index(vbuf, base)
        _, old_count, old_offset = struct.unpack_from('<3I', rcol.chunks[index], 4)
        count, offset = u32(entry, 40), u32(entry, 24)
        if (old_count, old_offset) != (count, offset):
            rcol = rcol.sync_vbsi(vbuf, count, offset)
            changes.append({'mesh': mesh, 'vbsi_chunk': index,
                            'old_vertex_count': old_count, 'vertex_count': count})
    rcol.inspect_mlod()  # full structural check, including VBSI
    return rcol, changes


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--report', type=Path, required=True)
    args = ap.parse_args()
    if args.input.resolve() == args.output.resolve():
        ap.error('Output must differ from input')
    header, entries = read_package(args.input)
    rows = []
    for entry in entries:
        if entry['type'] not in (MLOD, MODL):
            continue
        rcol, changes = normalize(Rcol.parse(entry['data']))
        data = rcol.to_bytes()
        recompressed = entry['comp'] != 0x5A42
        if changes or recompressed:
            entry['data'] = data
            entry['raw'] = zlib.compress(data, 9)
            entry['comp'] = 0x5A42
        rows.append({'type': f"{entry['type']:08X}", 'group': f"{entry['group']:08X}",
                     'vbsi_changes': changes, 'recompressed': recompressed})
    write_package(header, entries, args.output)
    _, reopened = read_package(args.output)
    if [e['data'] for e in reopened] != [e['data'] for e in entries]:
        raise ValueError('DBPF roundtrip mismatch')
    report = {'status': 'PROGRAMMATIC_PASS', 'input': str(args.input),
              'output': str(args.output), 'resources': rows,
              'output_sha256': h(args.output.read_bytes())}
    args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('MESH_NORMALIZE_PASS=' + json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
