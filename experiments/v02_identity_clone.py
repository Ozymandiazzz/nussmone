"""Private identity-clone experiment for a Sims 4 decorative donor.

Only DBPF instances and embedded references to those instances are changed.
No game assets, catalog fields, tuning, or product engine code are modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DONOR = Path(r"C:\Users\Cliente-TechNew\Desktop\TheSims4Tool\NovoVasoTeste2.package")
STBL = 0x220557DA
COBJ = 0xC0DB5AE7
OBJD = 0x319E4F1D
MASK56 = (1 << 56) - 1
ENTRY = struct.Struct("<IIIIIIIHH")


def h(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tgi(e: dict) -> str:
    return f"{e['type']:08X}:{e['group']:08X}:{e['instance']:016X}"


def read_package(path: Path) -> tuple[bytes, list[dict]]:
    blob = path.read_bytes()
    if len(blob) < 96 or blob[:4] != b"DBPF":
        raise ValueError(f"Invalid DBPF: {path}")
    count = struct.unpack_from("<I", blob, 36)[0]
    index_offset = struct.unpack_from("<I", blob, 64)[0]
    index_size = struct.unpack_from("<I", blob, 44)[0]
    if index_offset + index_size > len(blob) or index_size < 4 + count * ENTRY.size:
        raise ValueError("Invalid DBPF index bounds")
    flags = struct.unpack_from("<I", blob, index_offset)[0]
    if flags != 0:
        raise ValueError(f"Unsupported DBPF index flags: {flags:#x}")
    entries = []
    for n in range(count):
        pos = index_offset + 4 + n * ENTRY.size
        typ, group, hi, lo, offset, size_word, mem_size, comp, unk = ENTRY.unpack_from(blob, pos)
        size = size_word & 0x0FFFFFFF
        if offset + size > len(blob):
            raise ValueError(f"Resource {n} outside package")
        raw = blob[offset:offset + size]
        if comp == 0:
            data = raw
        elif comp == 0x5A42:
            data = zlib.decompress(raw[2:] if raw.startswith(b"ZB") else raw)
        else:
            raise ValueError(f"Unsupported compression {comp:#x} in resource {n}")
        if len(data) != mem_size:
            raise ValueError(f"Memory-size mismatch in resource {n}")
        entries.append(dict(type=typ, group=group, instance=(hi << 32) | lo,
                            raw=raw, data=data, comp=comp, unk=unk,
                            size_flags=size_word & 0xF0000000))
    if len({(e['type'], e['group'], e['instance']) for e in entries}) != count:
        raise ValueError("Duplicate source TGI")
    return blob[:96], entries


def mint(old: int, salt: str, used: set[int], locale: int | None = None) -> int:
    attempt = 0
    while True:
        digest = hashlib.blake2b(f"{salt}:{old:016X}:{attempt}".encode(), digest_size=8).digest()
        candidate = int.from_bytes(digest, "big")
        if locale is not None:
            candidate = (locale << 56) | (candidate & MASK56)
        if candidate != 0 and candidate not in used:
            used.add(candidate)
            return candidate
        attempt += 1


def build_remap(entries: list[dict], salt: str) -> dict[int, int]:
    ids = {e['instance'] for e in entries}
    used = set(ids)
    stbl_ids = {e['instance'] for e in entries if e['type'] == STBL}
    bases = {x & MASK56 for x in stbl_ids}
    if len(bases) != 1:
        raise ValueError(f"Expected one shared STBL base, found {len(bases)}")
    base = bases.pop()
    remap = {}
    new_base = mint(base, salt + ':STBL', used, locale=0) & MASK56
    for old in sorted(stbl_ids):
        remap[old] = ((old >> 56) << 56) | new_base
    if len(set(remap.values())) != len(remap):
        raise ValueError("STBL locale collision")
    used.update(remap.values())
    for old in sorted(ids - stbl_ids):
        remap[old] = mint(old, salt, used)
    return remap


def cobj_refs(data: bytes) -> list[dict]:
    if len(data) < 14:
        raise ValueError("COBJ too short")
    name_len = struct.unpack_from('<I', data, 6)[0]
    tuning_len_at = 10 + name_len
    if tuning_len_at + 4 > len(data):
        raise ValueError("COBJ name exceeds resource")
    tuning_len = struct.unpack_from('<I', data, tuning_len_at)[0]
    pos = tuning_len_at + 4 + tuning_len + 8
    refs = []
    while pos + 4 <= len(data):
        code = struct.unpack_from('<I', data, pos)[0]
        pos += 4
        if code == 4 and pos + 16 <= len(data):
            hi, lo, typ, group = struct.unpack_from('<IIII', data, pos)
            refs.append(dict(offset=pos, type=typ, group=group, instance=(hi << 32) | lo))
            pos += 16
        elif code == 8 and pos + 16 <= len(data):
            pos += 16
        else:
            break
    return refs


def patch_refs(data: bytes, remap: dict[int, int]) -> tuple[bytes, list[dict]]:
    """Replace exact eight-byte instances in either observed encoding."""
    patterns = {}
    for old, new in remap.items():
        patterns[old.to_bytes(8, 'little')] = (new.to_bytes(8, 'little'), old, new, 'u64_le')
        pair_old = struct.pack('<II', old >> 32, old & 0xFFFFFFFF)
        pair_new = struct.pack('<II', new >> 32, new & 0xFFFFFFFF)
        patterns[pair_old] = (pair_new, old, new, 'hi_lo_u32')
    changes = []
    occupied = set()
    out = bytearray(data)
    for offset in range(len(data) - 7):
        found = patterns.get(data[offset:offset + 8])
        if found is None:
            continue
        replacement, old, new, encoding = found
        if any(i in occupied for i in range(offset, offset + 8)):
            raise ValueError(f"Overlapping reference matches at {offset}")
        out[offset:offset + 8] = replacement
        occupied.update(range(offset, offset + 8))
        changes.append(dict(offset=offset, encoding=encoding,
                            old=f"{old:016X}", new=f"{new:016X}"))
    return bytes(out), changes


def write_package(header: bytes, entries: list[dict], path: Path) -> None:
    output = bytearray(header)
    indexed = []
    for e in entries:
        offset = len(output)
        output.extend(e['raw'])
        indexed.append((e, offset))
    index_offset = len(output)
    output.extend(struct.pack('<I', 0))
    for e, offset in indexed:
        instance = e['instance']
        output.extend(ENTRY.pack(e['type'], e['group'], instance >> 32,
                                 instance & 0xFFFFFFFF, offset,
                                 len(e['raw']) | e['size_flags'], len(e['data']),
                                 e['comp'], e['unk']))
    struct.pack_into('<I', output, 36, len(entries))
    struct.pack_into('<I', output, 44, len(output) - index_offset)
    struct.pack_into('<I', output, 64, index_offset)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(output)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--donor', type=Path, default=DEFAULT_DONOR)
    ap.add_argument('--output', type=Path, default=ROOT / 'output/v02_identity_clone.package')
    ap.add_argument('--report', type=Path, default=ROOT / 'output/v02_identity_clone_report.json')
    ap.add_argument('--salt', default='CCStudio-v02-identity-clone-1')
    args = ap.parse_args()
    if args.output.resolve() == args.donor.resolve():
        ap.error('Output must differ from donor')
    header, donor = read_package(args.donor)
    remap = build_remap(donor, args.salt)
    donor_tgis = {(e['type'], e['group'], e['instance']) for e in donor}
    clone = []
    rows = []
    for old in donor:
        before = old['data']
        after, changes = patch_refs(before, remap)
        if old['type'] == COBJ:
            parsed = cobj_refs(before)
            for ref in parsed:
                old_ref = ref['instance']
                if old_ref and (ref['type'], ref['group'], old_ref) in donor_tgis:
                    expected = remap[old_ref]
                    hi, lo = struct.unpack_from('<II', after, ref['offset'])
                    actual = (hi << 32) | lo
                    if actual != expected:
                        raise ValueError(f"COBJ reference not rewritten at {ref['offset']}")
        new = dict(old)
        new['instance'] = remap[old['instance']]
        new['data'] = after
        if changes:
            if old['comp'] == 0x5A42:
                prefix = b'ZB' if old['raw'].startswith(b'ZB') else b''
                new['raw'] = prefix + zlib.compress(after, 9)
            else:
                new['raw'] = after
        clone.append(new)
        rows.append(dict(resource=f"{old['type']:08X}", old_tgi=tgi(old),
                         new_tgi=tgi(new), old_sha256=h(before), new_sha256=h(after),
                         bytes_changed=sum(a != b for a, b in zip(before, after)),
                         old_length=len(before), new_length=len(after),
                         compressed_bytes_changed=(sum(a != b for a, b in zip(old['raw'], new['raw']))
                                                   + abs(len(old['raw']) - len(new['raw']))),
                         internal_refs_before=[dict(offset=c['offset'], encoding=c['encoding'], instance=c['old']) for c in changes],
                         internal_refs_after=[dict(offset=c['offset'], encoding=c['encoding'], instance=c['new']) for c in changes]))
    write_package(header, clone, args.output)
    _, reopened = read_package(args.output)
    if [(e['type'], e['group'], e['instance'], e['data']) for e in reopened] != [
        (e['type'], e['group'], e['instance'], e['data']) for e in clone
    ]:
        raise ValueError('Output failed DBPF roundtrip')
    new_tgis = {(e['type'], e['group'], e['instance']) for e in reopened}
    unresolved = []
    for e in reopened:
        if e['type'] == COBJ:
            unresolved.extend(f"{tgi(e)} -> {r['type']:08X}:{r['group']:08X}:{r['instance']:016X}"
                              for r in cobj_refs(e['data']) if r['instance'] and
                              (r['type'], r['group'], r['instance']) not in new_tgis)
    old_patterns = [p for old in remap for p in
                    (old.to_bytes(8, 'little'), struct.pack('<II', old >> 32, old & 0xFFFFFFFF))]
    orphans = [tgi(e) for e in reopened if any(p in e['data'] for p in old_patterns)]
    stbl_bases = {e['instance'] & MASK56 for e in reopened if e['type'] == STBL}
    report = dict(status='PROGRAMMATIC_PASS' if not orphans and not unresolved and len(stbl_bases) == 1 else 'FAIL',
                  manual_game_test='PENDING', donor=str(args.donor), output=str(args.output),
                  donor_sha256=h(args.donor.read_bytes()), clone_sha256=h(args.output.read_bytes()),
                  entry_count=len(reopened), remap_count=len(remap),
                  old_to_new={f'{o:016X}': f'{n:016X}' for o, n in sorted(remap.items())},
                  stbl_base_count=len(stbl_bases), orphan_count=len(orphans), orphans=orphans,
                  unresolved_count=len(unresolved), unresolved=unresolved,
                  changed_resource_count=sum(bool(r['bytes_changed']) for r in rows),
                  cobj_diff=[r for r in rows if r['resource'] == f'{COBJ:08X}'],
                  objd_diff=[r for r in rows if r['resource'] == f'{OBJD:08X}'],
                  resources=rows)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"{report['status']}: {len(reopened)} resources, {len(remap)} reminted instances, "
          f"{len(orphans)} orphans, {len(unresolved)} unresolved COBJ references")
    print(f"Package: {args.output}\nReport: {args.report}")
    if report['status'] != 'PROGRAMMATIC_PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
