"""
Minimal COBJ TGI fix for v0.2C placement.

Rewrites COBJ internal hi/lo u32 instance pairs from donor IDs to reminted IDs.
Does NOT touch STBL, mesh, MLOD content intent, DST content, tuning, thumbnail, ccstudio.py.

  python experiments/v02_cobj_fix.py \\
    --package output/v02_catalog_spike.package \\
    --donor path\\to\\donor.package \\
    --output output/v02_catalog_cobjfix.package
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_DONOR = Path(r"C:\Users\Cliente-TechNew\Desktop\TheSims4Tool\Vaso.package")
DEFAULT_INPUT = REPO / "output" / "v02_catalog_spike.package"
DEFAULT_OUTPUT = REPO / "output" / "v02_catalog_cobjfix.package"
DEFAULT_REPORT = REPO / "output" / "v02_cobj_fix_report.json"
DEFAULT_LOG = REPO / "output" / "v02_cobj_fix_run.log"

COBJ = 0xC0DB5AE7
OBJD = 0x319E4F1D
MLOD = 0x01D10F34
DST = 0x00B2D882
HEADER = 96


def log(msg: str, lines: list[str]) -> None:
    print(msg, flush=True)
    lines.append(msg)


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def decompress(raw: bytes, mem: int) -> bytes:
    if raw[:2] == b"\x5a\x42":
        return zlib.decompress(raw[2:])
    try:
        return zlib.decompress(raw)
    except zlib.error:
        if len(raw) == mem:
            return raw
        raise


def compress_zlib(data: bytes) -> bytes:
    # Match observed donor/spike style: raw zlib stream, comp flag 0x5A42 in index.
    return zlib.compress(data, 9)


def read_dbpf(path: Path):
    blob = path.read_bytes()
    if blob[:4] != b"DBPF":
        raise SystemExit(f"not DBPF: {path}")
    count = struct.unpack_from("<I", blob, 36)[0]
    index_offset = struct.unpack_from("<I", blob, 64)[0]
    flags = struct.unpack_from("<I", blob, index_offset)[0]
    if flags != 0:
        raise SystemExit(f"unsupported index flags {flags:#x}")
    pos = index_offset + 4
    entries = []
    for _ in range(count):
        t, g, i_hi, i_lo, offset, file_size, mem_size, comp, unk = struct.unpack_from(
            "<IIIIIIIHH", blob, pos
        )
        pos += 32
        fsz = file_size & 0x0FFFFFFF
        raw = blob[offset : offset + fsz]
        entries.append(
            {
                "t": t,
                "g": g,
                "i": (i_hi << 32) | i_lo,
                "raw": raw,
                "mem_size": mem_size,
                "comp": comp,
                "unk": unk,
                "data": decompress(raw, mem_size),
            }
        )
    return blob[:HEADER], entries


def write_dbpf(header96: bytes, entries: list[dict], out: Path) -> None:
    payload = bytearray(header96)
    new_entries = []
    for e in entries:
        offset = len(payload)
        payload += e["raw"]
        ne = dict(e)
        ne["offset"] = offset
        ne["file_size"] = len(e["raw"])
        new_entries.append(ne)
    index_offset = len(payload)
    payload += struct.pack("<I", 0)
    for e in new_entries:
        i_hi = e["i"] >> 32
        i_lo = e["i"] & 0xFFFFFFFF
        payload += struct.pack(
            "<IIIIIIIHH",
            e["t"],
            e["g"],
            i_hi,
            i_lo,
            e["offset"],
            e["file_size"] | 0x80000000,
            e["mem_size"],
            e["comp"],
            e["unk"],
        )
    index_size = len(payload) - index_offset
    struct.pack_into("<I", payload, 36, len(new_entries))
    struct.pack_into("<I", payload, 44, index_size)
    struct.pack_into("<I", payload, 64, index_offset)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(payload)


def peel_cobj(data: bytes):
    nlen = struct.unpack_from("<I", data, 6)[0]
    name = data[10 : 10 + nlen].decode("ascii", "replace")
    tlen = struct.unpack_from("<I", data, 10 + nlen)[0]
    tuning = data[14 + nlen : 14 + nlen + tlen].decode("ascii", "replace")
    rest_off = 14 + nlen + tlen
    return name, tuning, rest_off, data[rest_off:]


def parse_cobj_tgis(data: bytes) -> list[dict]:
    name, tuning, rest_off, rest = peel_cobj(data)
    pos = 8
    refs = []
    while pos + 4 <= len(rest):
        code = struct.unpack_from("<I", rest, pos)[0]
        abs_off = rest_off + pos
        pos += 4
        if code == 4 and pos + 16 <= len(rest):
            hi, lo, typ, group = struct.unpack_from("<IIII", rest, pos)
            inst = (hi << 32) | lo
            refs.append(
                {
                    "abs_offset": abs_off,  # start of code field
                    "hi_offset": rest_off + pos,
                    "lo_offset": rest_off + pos + 4,
                    "type": typ,
                    "group": group,
                    "instance": inst,
                    "tgi": f"{typ:08X}:{group:08X}:{inst:016X}",
                }
            )
            pos += 16
        elif code == 8:
            pos += 16
        else:
            break
    return refs


def build_remap(donor_entries, spike_entries) -> dict[int, int]:
    """Map donor instance -> spike instance by (type, group) list order."""
    from collections import defaultdict

    d = defaultdict(list)
    s = defaultdict(list)
    for e in donor_entries:
        d[(e["t"], e["g"])].append(e["i"])
    for e in spike_entries:
        s[(e["t"], e["g"])].append(e["i"])
    remap = {}
    for key, dlist in d.items():
        slist = s.get(key, [])
        for i, old in enumerate(dlist):
            if i < len(slist):
                remap[old] = slist[i]
    return remap


def patch_cobj(data: bytes, remap: dict[int, int], lines: list[str]) -> tuple[bytes, list[dict]]:
    refs = parse_cobj_tgis(data)
    buf = bytearray(data)
    changes = []
    for ref in refs:
        old = ref["instance"]
        if old == 0:
            continue
        new = remap.get(old)
        if new is None:
            log(f"[cobj] WARNING no remap for {old:016X} ({ref['tgi']})", lines)
            continue
        if new == old:
            continue
        hi = (new >> 32) & 0xFFFFFFFF
        lo = new & 0xFFFFFFFF
        struct.pack_into("<I", buf, ref["hi_offset"], hi)
        struct.pack_into("<I", buf, ref["lo_offset"], lo)
        changes.append(
            {
                "type": f"{ref['type']:08X}",
                "group": f"{ref['group']:08X}",
                "old": f"{old:016X}",
                "new": f"{new:016X}",
                "hi_offset": ref["hi_offset"],
                "lo_offset": ref["lo_offset"],
            }
        )
        log(
            f"[cobj] {ref['type']:08X}:{ref['group']:08X} {old:016X} -> {new:016X}",
            lines,
        )
    return bytes(buf), changes


def content_hashes(entries):
    out = {"DST": {}, "MLOD": {}}
    for e in entries:
        if e["t"] == DST:
            out["DST"][f"{e['i']:016X}"] = sha256(e["data"])
        if e["t"] == MLOD and e["g"] == 0:
            out["MLOD"][f"{e['i']:016X}"] = sha256(e["data"])
    return out


def parse_args():
    p = argparse.ArgumentParser(prog="v02_cobj_fix")
    p.add_argument("--package", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--donor", type=Path, default=DEFAULT_DONOR)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    p.add_argument("--log", type=Path, default=DEFAULT_LOG)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    donor = args.donor
    inp = args.package
    output = args.output
    report_path = args.report
    log_path = args.log

    lines: list[str] = []
    log(f"[cobjfix] input={inp}", lines)
    log(f"[cobjfix] donor={donor}", lines)

    donor_hdr, donor_entries = read_dbpf(donor)
    hdr, entries = read_dbpf(inp)
    remap = build_remap(donor_entries, entries)
    log(f"[cobjfix] remap entries={len(remap)}", lines)

    before_hashes = content_hashes(entries)
    cobj = next(e for e in entries if e["t"] == COBJ)
    before_refs = parse_cobj_tgis(cobj["data"])
    donor_ids = {e["i"] for e in donor_entries}
    spike_ids = {e["i"] for e in entries}

    before_orphans = [
        r["tgi"]
        for r in before_refs
        if r["instance"] and r["instance"] in donor_ids and r["instance"] not in spike_ids
    ]
    log(f"[cobjfix] before orphan count={len(before_orphans)}", lines)
    for o in before_orphans:
        log(f"[cobjfix]   orphan {o}", lines)

    new_data, changes = patch_cobj(cobj["data"], remap, lines)
    after_refs = parse_cobj_tgis(new_data)
    after_orphans = [
        r["tgi"]
        for r in after_refs
        if r["instance"] and r["instance"] in donor_ids and r["instance"] not in spike_ids
    ]

    # Also flag any COBJ instance not present in spike index (except 0)
    missing = [
        r["tgi"]
        for r in after_refs
        if r["instance"] and r["instance"] not in spike_ids
    ]

    compressed = compress_zlib(new_data)
    cobj["data"] = new_data
    cobj["raw"] = compressed
    cobj["mem_size"] = len(new_data)
    cobj["comp"] = 0x5A42

    write_dbpf(hdr, entries, output)
    log(f"[cobjfix] wrote {output} ({output.stat().st_size} bytes)", lines)

    # Re-open verify
    _, verify = read_dbpf(output)
    vc = next(e for e in verify if e["t"] == COBJ)
    vrefs = parse_cobj_tgis(vc["data"])
    v_orphans = [
        r["tgi"]
        for r in vrefs
        if r["instance"] and r["instance"] in donor_ids and r["instance"] not in {e["i"] for e in verify}
    ]
    after_hashes = content_hashes(verify)
    dst_same = sorted(before_hashes["DST"].values()) == sorted(after_hashes["DST"].values())
    mlod_same = sorted(before_hashes["MLOD"].values()) == sorted(after_hashes["MLOD"].values())

    # OBJD instance unchanged
    objd_before = next(e["i"] for e in entries if e["t"] == OBJD)
    objd_after = next(e["i"] for e in verify if e["t"] == OBJD)

    ok = (
        len(changes) >= 1
        and len(v_orphans) == 0
        and len(missing) == 0
        and dst_same
        and mlod_same
        and objd_before == objd_after
    )

    report = {
        "status": "PASS" if ok else "FAIL",
        "input": str(inp),
        "donor": str(donor),
        "output": str(output),
        "changes": changes,
        "before_refs": [{"tgi": r["tgi"], "instance": f"{r['instance']:016X}"} for r in before_refs],
        "after_refs": [{"tgi": r["tgi"], "instance": f"{r['instance']:016X}"} for r in vrefs],
        "before_orphan_count": len(before_orphans),
        "after_orphan_count": len(v_orphans),
        "after_orphans": v_orphans,
        "missing_in_spike_index": missing,
        "dst_content_unchanged": dst_same,
        "mlod0_content_unchanged": mlod_same,
        "objd_instance_unchanged": objd_before == objd_after,
        "objd_instance": f"{objd_after:016X}",
        "before_dst_shas": before_hashes["DST"],
        "after_dst_shas": after_hashes["DST"],
        "before_mlod0_shas": before_hashes["MLOD"],
        "after_mlod0_shas": after_hashes["MLOD"],
        "stbl_untouched": True,
        "note": "STBL not modified in this fix.",
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log_path.write_text("\n".join(lines) + "\n" + json.dumps(report, indent=2) + "\n", encoding="utf-8")
    log(f"[cobjfix] report={report_path}", lines)
    log(f"[cobjfix] RESULT {report['status']}", lines)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
