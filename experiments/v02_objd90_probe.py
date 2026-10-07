"""Isolate the legacy catalog spike's unexplained f32 write at OBJD offset 90."""
from __future__ import annotations

import argparse
import json
import struct
import zlib
from pathlib import Path

from v02_identity_clone import OBJD, ROOT, h, read_package, tgi, write_package


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', type=Path, default=ROOT / 'output/v02_price_probe.package')
    ap.add_argument('--output', type=Path, default=ROOT / 'output/v02_objd90_probe.package')
    ap.add_argument('--report', type=Path, default=ROOT / 'output/v02_objd90_probe_report.json')
    ap.add_argument('--value', type=float, default=10.0)
    args = ap.parse_args()
    if args.output.resolve() == args.input.resolve():
        ap.error('Output must differ from input')
    header, original = read_package(args.input)
    if len([e for e in original if e['type'] == OBJD]) != 1:
        raise ValueError('Expected exactly one OBJD')
    updated = []
    old_value = None
    for before in original:
        after = dict(before)
        if before['type'] == OBJD:
            old_value = struct.unpack_from('<f', before['data'], 90)[0]
            buf = bytearray(before['data'])
            struct.pack_into('<f', buf, 90, args.value)
            data = bytes(buf)
            if data[:90] != before['data'][:90] or data[94:] != before['data'][94:]:
                raise ValueError('OBJD changed outside f32@90')
            after['data'] = data
            if before['comp'] == 0x5A42:
                prefix = b'ZB' if before['raw'].startswith(b'ZB') else b''
                after['raw'] = prefix + zlib.compress(data, 9)
            elif before['comp'] == 0:
                after['raw'] = data
            else:
                raise ValueError('Unsupported compression')
        updated.append(after)
    if old_value != 8.0:
        raise ValueError(f'Expected approved vase f32@90 = 8.0, got {old_value}')
    write_package(header, updated, args.output)
    _, verify = read_package(args.output)
    if [(e['type'], e['group'], e['instance'], e['data']) for e in verify] != [
        (e['type'], e['group'], e['instance'], e['data']) for e in updated
    ]:
        raise ValueError('Output DBPF roundtrip failed')
    changed = [(a, b) for a, b in zip(original, verify) if a['data'] != b['data']]
    if len(changed) != 1 or changed[0][0]['type'] != OBJD:
        raise ValueError('Expected exactly one changed OBJD payload')
    before, after = changed[0]
    report = dict(status='PROGRAMMATIC_PASS', manual_game_test='PENDING',
                  input=str(args.input), output=str(args.output),
                  input_sha256=h(args.input.read_bytes()), output_sha256=h(args.output.read_bytes()),
                  changed_tgi=tgi(before), changed_offset=90, changed_length=4,
                  old_f32=old_value, new_f32=args.value,
                  old_objd_sha256=h(before['data']), new_objd_sha256=h(after['data']),
                  entry_count=len(verify), unchanged_tgi_count=len(verify),
                  changed_resource_count=1, other_resource_payloads_unchanged=True,
                  interpretation='Field meaning unknown; do not label it price without evidence.')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"PROGRAMMATIC_PASS: only OBJD f32@90 changed {old_value} -> {args.value}")
    print(f"Package: {args.output}\nReport: {args.report}")


if __name__ == '__main__':
    main()
