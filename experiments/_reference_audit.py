"""
Structural reference audit: donor vs v02_catalog_spike (read-only).
Produces output/v02_reference_audit.json used for V02_REFERENCE_AUDIT.md.
"""
from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

TYPE_NAME = {
    0x220557DA: "STBL",
    0x8EAF13DE: "RIG",
    0xD3044521: "SLOT",
    0x00B2D882: "DST",
    0x01D10F34: "MLOD",
    0x03B4C61D: "LITE",
    0x01661233: "MODL",
    0xD382BF57: "FTPT",
    0xC0DB5AE7: "COBJ",
    0x319E4F1D: "OBJD",
    0x81CA1A10: "THUM",
}


def dec(raw: bytes, mem: int) -> bytes:
    if raw[:2] == b"\x5a\x42":
        return zlib.decompress(raw[2:])
    try:
        out = zlib.decompress(raw)
        return out
    except zlib.error:
        return raw


def read_pkg(path: Path):
    blob = path.read_bytes()
    count = struct.unpack_from("<I", blob, 36)[0]
    index_offset = struct.unpack_from("<I", blob, 64)[0]
    pos = index_offset + 4
    entries = []
    for _ in range(count):
        t, g, i_hi, i_lo, offset, file_size, mem_size, comp, unk = struct.unpack_from(
            "<IIIIIIIHH", blob, pos
        )
        pos += 32
        fsz = file_size & 0x0FFFFFFF
        raw = blob[offset : offset + fsz]
        data = dec(raw, mem_size)
        entries.append({"t": t, "g": g, "i": (i_hi << 32) | i_lo, "data": data})
    return entries


def tgi_str(t, g, i):
    return f"{t:08X}:{g:08X}:{i:016X}"


def peel_cobj(data: bytes):
    nlen = struct.unpack_from("<I", data, 6)[0]
    name = data[10 : 10 + nlen].decode("ascii", "replace")
    tlen = struct.unpack_from("<I", data, 10 + nlen)[0]
    tuning = data[14 + nlen : 14 + nlen + tlen].decode("ascii", "replace")
    rest = data[14 + nlen + tlen :]
    return name, tuning, rest


def parse_cobj_internal_tgis(data: bytes) -> list[dict]:
    """COBJ block: after name/tuning, records of code=4, instance hi/lo (u32 LE), type (u32 LE), group."""
    _, _, rest = peel_cobj(data)
    pos = 8  # skip leading u64-ish header
    out = []
    while pos + 4 <= len(rest):
        code = struct.unpack_from("<I", rest, pos)[0]
        pos += 4
        if code == 4 and pos + 16 <= len(rest):
            hi, lo, typ, group = struct.unpack_from("<IIII", rest, pos)
            pos += 16
            inst = (hi << 32) | lo
            out.append(
                {
                    "type": typ,
                    "type_name": TYPE_NAME.get(typ, f"{typ:08X}"),
                    "group": group,
                    "instance": inst,
                    "tgi": tgi_str(typ, group, inst),
                }
            )
        elif code == 8:
            pos += 16
        else:
            break
    return out


def find_le_u64_instances(data: bytes, known: set[int]) -> list[dict]:
    hits = []
    for off in range(0, max(0, len(data) - 7)):
        v = struct.unpack_from("<Q", data, off)[0]
        if v in known:
            hits.append({"offset": off, "instance": v, "hex": f"{v:016X}"})
    return hits


def find_split_u32_instances(data: bytes, known: set[int]) -> list[dict]:
    """Detect instance stored as two consecutive u32 LE (hi, lo) — COBJ style also appears in FTPT."""
    hits = []
    known_parts = {}
    for inst in known:
        hi = (inst >> 32) & 0xFFFFFFFF
        lo = inst & 0xFFFFFFFF
        known_parts[(hi, lo)] = inst
        known_parts[(lo, hi)] = inst  # tolerate order
    for off in range(0, max(0, len(data) - 7)):
        a, b = struct.unpack_from("<II", data, off)
        if (a, b) in known_parts:
            hits.append(
                {
                    "offset": off,
                    "instance": known_parts[(a, b)],
                    "hex": f"{known_parts[(a, b)]:016X}",
                    "encoding": "u32_pair",
                }
            )
    return hits


def stbl_bases(entries):
    bases = {}
    for e in entries:
        if e["t"] != 0x220557DA:
            continue
        loc = e["i"] >> 56
        base = e["i"] & ((1 << 56) - 1)
        bases[loc] = base
    return bases


def main():
    donor_p = Path(r"C:\Users\Cliente-TechNew\Desktop\TheSims4Tool\Vaso.package")
    spike_p = Path("output/v02_catalog_spike.package")
    s4s_p = Path(r"C:\Users\Cliente-TechNew\Desktop\TheSims4Tool\NovoVasoTeste2.package")

    donor = read_pkg(donor_p)
    spike = read_pkg(spike_p)
    s4s = read_pkg(s4s_p)

    # Build remap by matching (type, group) pairs in order for multi-resources
    from collections import defaultdict

    d_groups = defaultdict(list)
    s_groups = defaultdict(list)
    for e in donor:
        d_groups[(e["t"], e["g"])].append(e)
    for e in spike:
        s_groups[(e["t"], e["g"])].append(e)

    remap = {}  # old_i -> new_i (best effort by type+group index)
    rows = []
    donor_ids = {e["i"] for e in donor}
    spike_ids = {e["i"] for e in spike}

    for key in sorted(d_groups.keys(), key=lambda k: (k[0], k[1])):
        dlist = d_groups[key]
        slist = s_groups.get(key, [])
        for idx, de in enumerate(dlist):
            se = slist[idx] if idx < len(slist) else None
            old_tgi = tgi_str(de["t"], de["g"], de["i"])
            new_tgi = tgi_str(se["t"], se["g"], se["i"]) if se else None
            if se:
                remap[de["i"]] = se["i"]

            d_refs_le = find_le_u64_instances(de["data"], donor_ids)
            s_refs_le = find_le_u64_instances(se["data"], spike_ids | donor_ids) if se else []
            d_refs_pair = find_split_u32_instances(de["data"], donor_ids)
            s_refs_pair = find_split_u32_instances(se["data"], spike_ids | donor_ids) if se else []

            # COBJ structured refs
            cobj_before = cobj_after = None
            if de["t"] == 0xC0DB5AE7:
                cobj_before = parse_cobj_internal_tgis(de["data"])
                if se:
                    cobj_after = parse_cobj_internal_tgis(se["data"])

            orphans = []
            if se:
                # any internal ref still pointing at donor instance that is NOT in spike index
                for r in s_refs_le + s_refs_pair:
                    inst = r["instance"]
                    if inst in donor_ids and inst not in spike_ids:
                        orphans.append(f"{r['hex']} (still donor, not in spike)")
                if cobj_after:
                    for ref in cobj_after:
                        inst = ref["instance"]
                        if inst == 0:
                            continue
                        if inst in donor_ids and inst not in spike_ids:
                            orphans.append(f"COBJ->{ref['tgi']} donor-only")
                        elif inst not in spike_ids and inst not in donor_ids:
                            orphans.append(f"COBJ->{ref['tgi']} missing both")

            rows.append(
                {
                    "resource": TYPE_NAME.get(de["t"], f"{de['t']:08X}"),
                    "old_tgi": old_tgi,
                    "new_tgi": new_tgi,
                    "internal_refs_before": {
                        "le_u64": [r["hex"] for r in d_refs_le],
                        "u32_pair": [r["hex"] for r in d_refs_pair],
                        "cobj_tgis": cobj_before,
                    },
                    "internal_refs_after": {
                        "le_u64": [r["hex"] for r in s_refs_le] if se else None,
                        "u32_pair": [r["hex"] for r in s_refs_pair] if se else None,
                        "cobj_tgis": cobj_after,
                    },
                    "resolved_in_spike": len(orphans) == 0 if se else False,
                    "orphan": orphans,
                    "notes": "",
                }
            )

    # Annotate key notes
    for row in rows:
        if row["resource"] == "COBJ" and row["orphan"]:
            row["notes"] = (
                "COBJ TGI block uses hi/lo u32 instance encoding; remint only patched "
                "raw LE u64 — block still names donor RIG/SLOT/MODL/FTPT instances. "
                "S4S standalone updates these fields."
            )
        if row["resource"] == "STBL":
            row["notes"] = "See STBL base integrity section — locales must share one base."
        if row["resource"] == "OBJD":
            row["notes"] = (
                "Keys/price patched; no package-instance u64s inside OBJD body for this donor layout."
            )
        if row["resource"] == "FTPT" and row["new_tgi"]:
            row["notes"] = "Partial LE/u32 remint of model instance inside footprint (bytes ~20-26)."
        if row["resource"] == "SLOT" and row["new_tgi"]:
            row["notes"] = "Partial remint of embedded instance refs (7 bytes differ)."
        if row["resource"] == "LITE":
            row["notes"] = "Payload identical to donor; only index instance reminted."
        if row["resource"] == "MLOD":
            row["notes"] = "LE u64 remint of DST instances inside materials (expected)."

    d_bases = stbl_bases(donor)
    s_bases = stbl_bases(spike)
    b_bases = stbl_bases(s4s)

    report = {
        "exception": {
            "type": "TypeError: 'NoneType' object is not iterable",
            "site": "base_object.py:84 via definition.instantiate / c_api_create_object",
            "arg0_definition_id": "0524172EC4E9144A",
            "arg1_catalog_instance": "B54973A7C47B7546",
            "arg1_matches_spike_objd": True,
        },
        "remap_graph": {f"{k:016X}": f"{v:016X}" for k, v in remap.items()},
        "stbl_base_integrity": {
            "donor_unique_bases": len(set(d_bases.values())),
            "spike_unique_bases": len(set(s_bases.values())),
            "s4s_unique_bases": len(set(b_bases.values())),
            "expected": 1,
            "spike_broken": len(set(s_bases.values())) != 1,
        },
        "first_orphan": None,
        "rows": rows,
    }

    for row in rows:
        if row["orphan"]:
            report["first_orphan"] = {
                "resource": row["resource"],
                "old_tgi": row["old_tgi"],
                "new_tgi": row["new_tgi"],
                "orphans": row["orphan"],
                "notes": row["notes"],
            }
            break

    # Also flag STBL as structural defect even if not classic orphan
    report["critical_defects"] = []
    if report["stbl_base_integrity"]["spike_broken"]:
        report["critical_defects"].append(
            {
                "id": "STBL_BASE_SPLIT",
                "summary": "Each STBL locale received an independent random base; donor/S4S keep one shared base.",
                "severity": "High",
            }
        )
    if report["first_orphan"]:
        report["critical_defects"].append(
            {
                "id": "COBJ_DONOR_TGI_STALE",
                "summary": report["first_orphan"]["notes"] or str(report["first_orphan"]["orphans"]),
                "severity": "Critical",
            }
        )

    out = Path("output/v02_reference_audit.json")
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("wrote", out)
    print("first_orphan", json.dumps(report["first_orphan"], indent=2))
    print("stbl", report["stbl_base_integrity"])
    print("defects", report["critical_defects"])


if __name__ == "__main__":
    main()
