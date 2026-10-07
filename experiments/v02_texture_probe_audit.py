"""Verify that the texture probe changes only the decorative vase's Diffuse DST."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from v02_identity_clone import ROOT, h, read_package, tgi

DST = 0x00B2D882
DIFFUSE = (DST, 0x80000000, 0xE85CC651F486CD25)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', type=Path, default=ROOT / 'output/v02_catalog_probe.package')
    ap.add_argument('--texture', type=Path, default=ROOT / 'output/texture_probe/v02_texture_probe.package')
    ap.add_argument('--report', type=Path,
                    default=ROOT / 'output/texture_probe/v02_texture_probe_audit.json')
    args = ap.parse_args()
    _, base = read_package(args.base)
    _, texture = read_package(args.texture)
    if [(e['type'], e['group'], e['instance']) for e in base] != [
        (e['type'], e['group'], e['instance']) for e in texture
    ]:
        raise ValueError('Resource TGIs or order changed')
    changed = [(a, b) for a, b in zip(base, texture) if a['data'] != b['data']]
    if len(changed) != 1 or tuple(changed[0][0][k] for k in ('type', 'group', 'instance')) != DIFFUSE:
        raise ValueError(f'Expected only Diffuse DST to change, got {[tgi(a) for a, _ in changed]}')
    if any(a['raw'] != b['raw'] for a, b in zip(base, texture) if a['data'] == b['data']):
        raise ValueError('Unchanged stored payload bytes were rewritten')
    before, after = changed[0]
    report = dict(status='PROGRAMMATIC_PASS', manual_game_test='PENDING',
                  base=str(args.base), texture=str(args.texture),
                  base_sha256=h(args.base.read_bytes()),
                  texture_sha256=h(args.texture.read_bytes()),
                  entry_count=len(texture), changed_resource_count=1,
                  changed_tgi=tgi(before), before_dst_bytes=len(before['data']),
                  after_dst_bytes=len(after['data']),
                  before_dst_sha256=h(before['data']), after_dst_sha256=h(after['data']),
                  other_resource_raw_bytes_unchanged=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"PROGRAMMATIC_PASS: only {tgi(before)} changed; "
          f"{len(before['data'])} -> {len(after['data'])} bytes")
    print(f"Report: {args.report}")


if __name__ == '__main__':
    main()
