"""Change only catalog name/description and OBJD string keys on the passing clone."""
from __future__ import annotations

import argparse
import json
import struct
import zlib
from pathlib import Path

from v02_identity_clone import COBJ, OBJD, STBL, ROOT, h, read_package, tgi, write_package


def fnv32(value: str) -> int:
    """Match @s4tk/hashing fnv32: lower-case UTF-16 code units, FNV-1."""
    result = 0x811C9DC5
    for char in value.lower():
        for unit in range(len(char.encode('utf-16-le')) // 2):
            code = struct.unpack_from('<H', char.encode('utf-16-le'), unit * 2)[0]
            result = ((result * 0x01000193) & 0xFFFFFFFF) ^ code
    return result


def parse_stbl(data: bytes) -> tuple[list[dict], bytes]:
    if len(data) < 21 or data[:4] != b'STBL' or struct.unpack_from('<H', data, 4)[0] != 5:
        raise ValueError('Unsupported STBL header')
    count = struct.unpack_from('<Q', data, 7)[0]
    if count > 10000:
        raise ValueError('Unreasonable STBL entry count')
    pos = 21
    entries = []
    for _ in range(count):
        if pos + 7 > len(data):
            raise ValueError('Truncated STBL entry')
        key, flags, size = struct.unpack_from('<IBH', data, pos)
        pos += 7
        if pos + size > len(data):
            raise ValueError('Truncated STBL string')
        value = data[pos:pos + size].decode('utf-8')
        pos += size
        entries.append(dict(key=key, flags=flags, value=value))
    return entries, data[pos:]


def write_stbl(before: bytes, entries: list[dict], trailing: bytes) -> bytes:
    out = bytearray(before[:21])
    struct.pack_into('<I', out, 17,
                     sum(len(e['value'].encode('utf-8')) + 1 for e in entries))
    for e in entries:
        raw = e['value'].encode('utf-8')
        if len(raw) > 65535:
            raise ValueError('STBL string too long')
        out.extend(struct.pack('<IBH', e['key'], e['flags'], len(raw)))
        out.extend(raw)
    out.extend(trailing)
    return bytes(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', type=Path, default=ROOT / 'output/v02_identity_clone.package')
    ap.add_argument('--output', type=Path, default=ROOT / 'output/v02_catalog_probe.package')
    ap.add_argument('--report', type=Path, default=ROOT / 'output/v02_catalog_probe_report.json')
    ap.add_argument('--name', default='CCStudio Catalog Probe')
    ap.add_argument('--description', default='Catalog-only identity clone test')
    args = ap.parse_args()
    if args.output.resolve() == args.input.resolve():
        ap.error('Output must differ from input')
    header, original = read_package(args.input)
    objd = [e for e in original if e['type'] == OBJD]
    cobj = [e for e in original if e['type'] == COBJ]
    stbl = [e for e in original if e['type'] == STBL]
    if len(objd) != 1 or len(cobj) != 1 or len(stbl) != 18:
        raise ValueError('Unexpected decorative donor layout')
    old_name_key, old_desc_key = struct.unpack_from('<II', objd[0]['data'], 8)
    new_name_key, new_desc_key = fnv32(args.name), fnv32(args.description)
    if len({old_name_key, old_desc_key, new_name_key, new_desc_key}) != 4:
        raise ValueError('String key collision')
    updated = []
    rows = []
    for before in original:
        after = dict(before)
        data = before['data']
        changed_fields = []
        if before['type'] == OBJD:
            buf = bytearray(data)
            struct.pack_into('<II', buf, 8, new_name_key, new_desc_key)
            data = bytes(buf)
            changed_fields = ['name_key@8', 'description_key@12']
            if data[:8] != before['data'][:8] or data[16:] != before['data'][16:]:
                raise ValueError('OBJD changed outside the two string keys')
        elif before['type'] == STBL:
            entries, trailing = parse_stbl(data)
            keys = [e['key'] for e in entries]
            if keys.count(old_name_key) != 1 or keys.count(old_desc_key) != 1:
                raise ValueError(f'STBL {tgi(before)} has unexpected keys')
            for ent in entries:
                if ent['key'] == old_name_key:
                    ent.update(key=new_name_key, value=args.name)
                elif ent['key'] == old_desc_key:
                    ent.update(key=new_desc_key, value=args.description)
            data = write_stbl(data, entries, trailing)
            changed_fields = ['name_entry', 'description_entry']
        after['data'] = data
        if data != before['data']:
            if before['comp'] == 0x5A42:
                prefix = b'ZB' if before['raw'].startswith(b'ZB') else b''
                after['raw'] = prefix + zlib.compress(data, 9)
            elif before['comp'] == 0:
                after['raw'] = data
            else:
                raise ValueError('Unsupported compression')
        updated.append(after)
        rows.append(dict(tgi=tgi(before), fields=changed_fields,
                         before_sha256=h(before['data']), after_sha256=h(data),
                         before_length=len(before['data']), after_length=len(data),
                         changed=data != before['data']))
    write_package(header, updated, args.output)
    _, verify = read_package(args.output)
    if [(x['type'], x['group'], x['instance'], x['data']) for x in updated] != [
        (x['type'], x['group'], x['instance'], x['data']) for x in verify
    ]:
        raise ValueError('Output DBPF roundtrip failed')
    changed = [r for r in rows if r['changed']]
    if len(changed) != 19 or {r['tgi'][:8] for r in changed} != {f'{STBL:08X}', f'{OBJD:08X}'}:
        raise ValueError('Unexpected resources changed')
    report = dict(status='PROGRAMMATIC_PASS', manual_game_test='PENDING',
                  input=str(args.input), output=str(args.output),
                  input_sha256=h(args.input.read_bytes()), output_sha256=h(args.output.read_bytes()),
                  entry_count=len(verify), unchanged_tgi_count=len(verify),
                  changed_resource_count=len(changed), unchanged_cobj_sha256=h(cobj[0]['data']),
                  name=args.name, description=args.description,
                  old_keys=[f'{old_name_key:08X}', f'{old_desc_key:08X}'],
                  new_keys=[f'{new_name_key:08X}', f'{new_desc_key:08X}'],
                  price_unchanged=struct.unpack_from('<I', objd[0]['data'], 16)[0] ==
                                  struct.unpack_from('<I', next(e for e in verify if e['type'] == OBJD)['data'], 16)[0],
                  resources=rows)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"PROGRAMMATIC_PASS: {len(verify)} TGIs unchanged; only OBJD and 18 STBL payloads changed")
    print(f"Package: {args.output}\nReport: {args.report}")


if __name__ == '__main__':
    main()
