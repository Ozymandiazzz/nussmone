"""Build four independently reminted, distinguishable packages for one game launch.

Each variant keeps its source payloads, then receives new resource instances and
catalog strings. No COBJ internal-name edit or asset replacement happens here.
"""
from __future__ import annotations

import argparse
import json
import struct
import subprocess
import sys
from pathlib import Path

from v02_catalog_probe import parse_stbl
from v02_identity_clone import COBJ, OBJD, ROOT, STBL, cobj_refs, h, read_package


VARIANTS = (
    ('control', 'CCStudio 01 Control', 'Passed price package; no new payload change',
     'output/v02_price_probe.package', 10),
    ('field90', 'CCStudio 02 Field90', 'Only legacy OBJD float at offset 90 differs from control',
     'output/v02_objd90_probe.package', 10),
    ('mesh', 'CCStudio 03 Mesh', 'Only high-detail mug MLOD differs from catalog control',
     'output/mesh_probe/v02_mesh_probe.package', 1300),
    ('texture', 'CCStudio 04 Texture', 'Only mug Diffuse differs from catalog control',
     'output/texture_probe/v02_texture_probe.package', 1300),
)


def run(script: str, *args: object) -> None:
    subprocess.run([sys.executable, str(ROOT / 'experiments' / script),
                    *(str(x) for x in args)], check=True, cwd=ROOT)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', type=Path, default=ROOT / 'output/v02_batch_probes')
    args = ap.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    report_rows = []
    all_tgis: set[tuple[int, int, int]] = set()
    names: set[str] = set()
    for tag, name, description, source_rel, expected_price in VARIANTS:
        source = ROOT / source_rel
        if not source.is_file():
            raise FileNotFoundError(source)
        reminted = out / f'{tag}_reminted.package'
        final = out / f'{tag}.package'
        remint_report = out / f'{tag}_remint_report.json'
        catalog_report = out / f'{tag}_catalog_report.json'
        run('v02_identity_clone.py', '--donor', source, '--output', reminted,
            '--report', remint_report, '--salt', f'CCStudio-batch-v1-{tag}')
        run('v02_catalog_probe.py', '--input', reminted, '--output', final,
            '--report', catalog_report, '--name', name, '--description', description)
        _, entries = read_package(final)
        tgis = {(e['type'], e['group'], e['instance']) for e in entries}
        overlap = tgis & all_tgis
        if overlap:
            raise ValueError(f'{tag}: {len(overlap)} TGIs collide with another batch package')
        all_tgis.update(tgis)
        objd = [e for e in entries if e['type'] == OBJD]
        cobj = [e for e in entries if e['type'] == COBJ]
        stbl = [e for e in entries if e['type'] == STBL and (e['instance'] >> 56) == 0]
        if len(objd) != 1 or len(cobj) != 1 or len(stbl) != 1:
            raise ValueError(f'{tag}: unexpected catalog resource count')
        price = struct.unpack_from('<I', objd[0]['data'], 16)[0]
        if price != expected_price:
            raise ValueError(f'{tag}: expected price {expected_price}, got {price}')
        strings, _ = parse_stbl(stbl[0]['data'])
        values = {e['value'] for e in strings}
        if name not in values or description not in values or name in names:
            raise ValueError(f'{tag}: catalog strings missing or duplicate')
        names.add(name)
        unresolved = [r for r in cobj_refs(cobj[0]['data']) if r['instance'] and
                      (r['type'], r['group'], r['instance']) not in tgis]
        if unresolved:
            raise ValueError(f'{tag}: unresolved COBJ references: {unresolved}')
        report_rows.append(dict(tag=tag, name=name, description=description,
                                expected_price=expected_price, source=str(source),
                                source_sha256=h(source.read_bytes()), package=str(final),
                                package_sha256=h(final.read_bytes()), entry_count=len(entries),
                                remint_report=str(remint_report), catalog_report=str(catalog_report),
                                unresolved_cobj_references=0))
    report = dict(status='PROGRAMMATIC_PASS', manual_game_test='PENDING',
                  note='Four packages have disjoint TGIs and distinct catalog names. COBJ internal names are unchanged and may be duplicated; the control item validates coexistence in game.',
                  package_count=len(report_rows), total_tgi_count=len(all_tgis),
                  packages=report_rows)
    path = out / 'batch_report.json'
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"PROGRAMMATIC_PASS: {len(report_rows)} packages, {len(all_tgis)} disjoint TGIs")
    print(f"Report: {path}")


if __name__ == '__main__':
    main()
