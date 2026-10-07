"""Change only the known OBJD catalog price field on the passing catalog probe."""
from __future__ import annotations

import argparse
import json
import struct
import zlib
from pathlib import Path

from v02_identity_clone import OBJD, ROOT, h, read_package, tgi, write_package


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', type=Path, default=ROOT / 'output/v02_catalog_probe.package')
    ap.add_argument('--output', type=Path, default=ROOT / 'output/v02_price_probe.package')
    ap.add_argument('--report', type=Path, default=ROOT / 'output/v02_price_probe_report.json')
    ap.add_argument('--price', type=int, default=10)
    ap.add_argument('--expected-old-price', type=int, default=1300)
    args = ap.parse_args()
    if args.output.resolve() == args.input.resolve():
        ap.error('Output must differ from input')
    if not 0 <= args.price <= 1_000_000:
        ap.error('Price must be between 0 and 1,000,000')
    header, original = read_package(args.input)
    if len([e for e in original if e['type'] == OBJD]) != 1:
        raise ValueError('Expected one OBJD')
    updated = []
    old_price = None
    for before in original:
        after = dict(before)
        if before['type'] == OBJD:
            old_price = struct.unpack_from('<I', before['data'], 16)[0]
            buf = bytearray(before['data'])
            struct.pack_into('<I', buf, 16, args.price)
            data = bytes(buf)
            if data[:16] != before['data'][:16] or data[20:] != before['data'][20:]:
                raise ValueError('OBJD changed outside price@16')
            after['data'] = data
            if before['comp'] == 0x5A42:
                prefix = b'ZB' if before['raw'].startswith(b'ZB') else b''
                after['raw'] = prefix + zlib.compress(data, 9)
            elif before['comp'] == 0:
                after['raw'] = data
            else:
                raise ValueError('Unsupported OBJD compression')
        updated.append(after)
    if old_price != args.expected_old_price:
        raise ValueError(f'Expected donor price {args.expected_old_price}, got {old_price}')
    write_package(header, updated, args.output)
    _, verify = read_package(args.output)
    if [(e['type'], e['group'], e['instance'], e['data']) for e in verify] != [
        (e['type'], e['group'], e['instance'], e['data']) for e in updated
    ]:
        raise ValueError('Output DBPF roundtrip failed')
    changed = [(a, b) for a, b in zip(original, verify) if a['data'] != b['data']]
    if len(changed) != 1 or changed[0][0]['type'] != OBJD:
        raise ValueError('Expected exactly one changed OBJD payload')
    report = dict(status='PROGRAMMATIC_PASS', manual_game_test='PENDING',
                  input=str(args.input), output=str(args.output),
                  input_sha256=h(args.input.read_bytes()), output_sha256=h(args.output.read_bytes()),
                  entry_count=len(verify), unchanged_tgi_count=len(verify),
                  changed_resource_count=1, changed_tgi=tgi(changed[0][0]),
                  changed_offset=16, changed_length=4,
                  old_price=old_price, new_price=args.price,
                  old_objd_sha256=h(changed[0][0]['data']),
                  new_objd_sha256=h(changed[0][1]['data']),
                  other_resource_payloads_unchanged=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"PROGRAMMATIC_PASS: only OBJD price@16 changed {old_price} -> {args.price}")
    print(f"Package: {args.output}\nReport: {args.report}")


if __name__ == '__main__':
    main()
