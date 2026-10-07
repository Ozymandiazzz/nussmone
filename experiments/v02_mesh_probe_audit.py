"""Verify that the mesh probe differs from the passing catalog package only in hi MLOD."""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from v02_identity_clone import COBJ, ROOT, cobj_refs, h, read_package, tgi

MLOD = 0x01D10F34


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', type=Path, default=ROOT / 'output/v02_catalog_probe.package')
    ap.add_argument('--mesh', type=Path, default=ROOT / 'output/mesh_probe/v02_mesh_probe.package')
    ap.add_argument('--identity-report', type=Path,
                    default=ROOT / 'output/v02_identity_clone_report.json')
    ap.add_argument('--report', type=Path,
                    default=ROOT / 'output/mesh_probe/v02_mesh_probe_audit.json')
    args = ap.parse_args()
    _, base = read_package(args.base)
    _, mesh = read_package(args.mesh)
    old_tgis = [(e['type'], e['group'], e['instance']) for e in base]
    new_tgis = [(e['type'], e['group'], e['instance']) for e in mesh]
    if old_tgis != new_tgis:
        raise ValueError('Resource TGIs or order changed')
    changed = [(a, b) for a, b in zip(base, mesh) if a['data'] != b['data']]
    if len(changed) != 1 or changed[0][0]['type'] != MLOD or changed[0][0]['group'] != 0:
        raise ValueError(f'Expected only hi MLOD to change, got {[tgi(a) for a, _ in changed]}')
    if any(a['raw'] != b['raw'] for a, b in zip(base, mesh) if a['data'] == b['data']):
        raise ValueError('Unchanged resource raw bytes were rewritten')
    tgi_set = set(new_tgis)
    unresolved = [f"{tgi(e)} -> {r['type']:08X}:{r['group']:08X}:{r['instance']:016X}"
                  for e in mesh if e['type'] == COBJ for r in cobj_refs(e['data'])
                  if r['instance'] and (r['type'], r['group'], r['instance']) not in tgi_set]
    if unresolved:
        raise ValueError(f'Unresolved COBJ refs: {unresolved}')
    identity = json.loads(args.identity_report.read_text(encoding='utf-8'))
    old_ids = [int(x, 16) for x in identity['old_to_new']]
    old_patterns = [p for x in old_ids for p in
                    (x.to_bytes(8, 'little'), struct.pack('<II', x >> 32, x & 0xFFFFFFFF))]
    donor_orphans = [tgi(e) for e in mesh if any(p in e['data'] for p in old_patterns)]
    if donor_orphans:
        raise ValueError(f'Donor IDs reappeared: {donor_orphans}')
    before, after = changed[0]
    report = dict(status='PROGRAMMATIC_PASS', manual_game_test='PENDING',
                  base=str(args.base), mesh=str(args.mesh),
                  base_sha256=h(args.base.read_bytes()), mesh_sha256=h(args.mesh.read_bytes()),
                  entry_count=len(mesh), changed_resource_count=1,
                  changed_tgi=tgi(before), before_mlod_bytes=len(before['data']),
                  after_mlod_bytes=len(after['data']),
                  before_mlod_sha256=h(before['data']), after_mlod_sha256=h(after['data']),
                  other_resource_raw_bytes_unchanged=True,
                  unresolved_cobj_reference_count=0, donor_orphan_count=0)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"PROGRAMMATIC_PASS: only {tgi(before)} changed; "
          f"{len(before['data'])} -> {len(after['data'])} bytes")
    print(f"Report: {args.report}")


if __name__ == '__main__':
    main()
