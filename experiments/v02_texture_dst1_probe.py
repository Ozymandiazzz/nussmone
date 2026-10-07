"""Replace Diffuse with donor-compatible DST1, preserving donor layout and compression."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

from PIL import Image

from v02_identity_clone import ROOT, h, read_package, tgi, write_package

DST = 0x00B2D882
DIFFUSE_INSTANCE = 0xE85CC651F486CD25


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', type=Path, default=ROOT / 'output/v02_catalog_probe.package')
    ap.add_argument('--image', type=Path, default=ROOT / 'output/A_handle_or_hollow_v011/basecolor.png')
    ap.add_argument('--diffuse-instance', type=lambda value: int(value, 0), default=DIFFUSE_INSTANCE)
    ap.add_argument('--encoder', choices=('python', 'node'), default='python')
    ap.add_argument('--node', type=Path, help='Node executable (or set CCSTUDIO_NODE)')
    ap.add_argument('--output', type=Path, default=ROOT / 'output/texture_dst1_probe/v02_texture_dst1_probe.package')
    ap.add_argument('--report', type=Path, default=ROOT / 'output/texture_dst1_probe/v02_texture_dst1_probe_report.json')
    args = ap.parse_args()
    node = args.node or os.environ.get('CCSTUDIO_NODE') or shutil.which('node')
    if args.encoder == 'node' and (not node or not Path(node).is_file()):
        raise FileNotFoundError('Node not found; install Node or set CCSTUDIO_NODE')
    header, entries = read_package(args.input)
    matches = [e for e in entries if (e['type'], e['group'], e['instance']) ==
               (DST, 0x80000000, args.diffuse_instance)]
    if len(matches) != 1:
        raise ValueError('Expected one reminted Diffuse DST')
    original = matches[0]
    with tempfile.TemporaryDirectory(prefix='ccstudio_dst1_') as folder:
        donor_path = Path(folder) / 'donor.dst'
        output_path = Path(folder) / 'replacement.dst'
        image_path = Path(folder) / 'source.png'
        donor_path.write_bytes(original['data'])
        with Image.open(args.image) as image:
            image.convert('RGBA').save(image_path, format='PNG')
        command = ([sys.executable, str(ROOT / 'experiments/encode_dst1_compatible.py')]
                   if args.encoder == 'python' else
                   [str(node), str(ROOT / 'experiments/encode_dst1_compatible.cjs')])
        completed = subprocess.run(command + [str(image_path), str(donor_path),
                                              str(output_path)], cwd=ROOT / 'experiments',
                                   capture_output=True, text=True)
        if completed.returncode:
            raise RuntimeError(f'DST1 encoder failed: {completed.stderr.strip()}')
        encoder = json.loads(completed.stdout.strip().splitlines()[-1])
        replacement = output_path.read_bytes()
    if replacement[:128] != original['data'][:128]:
        raise ValueError('Donor DDS header changed')
    if len(replacement) != len(original['data']) or replacement == original['data']:
        raise ValueError('DST1 size/content invariant failed')
    updated = []
    for entry in entries:
        next_entry = dict(entry)
        if entry is original:
            next_entry['data'] = replacement
            if entry['comp'] == 0x5A42:
                prefix = b'ZB' if entry['raw'].startswith(b'ZB') else b''
                next_entry['raw'] = prefix + zlib.compress(replacement, 9)
            elif entry['comp'] == 0:
                next_entry['raw'] = replacement
            else:
                raise ValueError('Unsupported donor compression')
        updated.append(next_entry)
    write_package(header, updated, args.output)
    _, verify = read_package(args.output)
    if [(e['type'], e['group'], e['instance']) for e in entries] != [
        (e['type'], e['group'], e['instance']) for e in verify
    ]:
        raise ValueError('TGIs changed')
    changed = [(a, b) for a, b in zip(entries, verify) if a['data'] != b['data']]
    if len(changed) != 1 or changed[0][0] is not original:
        raise ValueError('Unexpected changed resource')
    if any(a['raw'] != b['raw'] for a, b in zip(entries, verify) if a['data'] == b['data']):
        raise ValueError('Unchanged stored bytes modified')
    report = dict(status='PROGRAMMATIC_PASS', manual_game_test='PENDING',
                  input=str(args.input), output=str(args.output), image=str(args.image),
                  input_sha256=h(args.input.read_bytes()), output_sha256=h(args.output.read_bytes()),
                  changed_tgi=tgi(original), original_dst_sha256=h(original['data']),
                  replacement_dst_sha256=h(replacement), donor_header_identical=True,
                  donor_length_identical=True, donor_compression_preserved=True,
                  other_resource_raw_bytes_unchanged=True, encoder=encoder)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"PROGRAMMATIC_PASS: donor-compatible DST1 {encoder['width']}x{encoder['height']}, "
          f"{encoder['mipCount']} mips, {len(replacement)} bytes")
    print(f"Package: {args.output}\nReport: {args.report}")


if __name__ == '__main__':
    main()
