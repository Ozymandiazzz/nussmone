"""Diagnose placement failure: compare donor vs catalog spike refs (read-only)."""
from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

TYPE = {
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
    if len(raw) == mem and not raw.startswith(b"\x78\xda"):
        return raw
    if raw[:2] == b"\x5a\x42":
        return zlib.decompress(raw[2:])
    try:
        return zlib.decompress(raw)
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
        entries.append(
            {
                "t": t,
                "g": g,
                "i": (i_hi << 32) | i_lo,
                "data": data,
                "mem": mem_size,
                "comp": comp,
            }
        )
    return entries


def tgi(e):
    return f"{e['t']:08X}:{e['g']:08X}:{e['i']:016X}"


def peel_cobj(data: bytes):
    nlen = struct.unpack_from("<I", data, 6)[0]
    name = data[10 : 10 + nlen].decode("ascii", "replace")
    tlen = struct.unpack_from("<I", data, 10 + nlen)[0]
    tuning = data[14 + nlen : 14 + nlen + tlen].decode("ascii", "replace")
    rest = data[14 + nlen + tlen :]
    return name, tuning, rest


def find_u64s(data: bytes, known: set[int]):
    hits = []
    for off in range(0, max(0, len(data) - 7)):
        v = struct.unpack_from("<Q", data, off)[0]
        if v in known:
            hits.append((off, v))
    return hits


def find_all_u64(data: bytes, min_val=0x10000):
    """Collect plausible instance-like u64s (heuristic)."""
    vals = []
    for off in range(0, max(0, len(data) - 7), 1):
        v = struct.unpack_from("<Q", data, off)[0]
        if v >= min_val and v < (1 << 63):
            vals.append((off, v))
    return vals


def main():
    donor = Path(r"C:\Users\Cliente-TechNew\Desktop\TheSims4Tool\Vaso.package")
    spike = Path(r"output\v02_catalog_spike.package")
    s4s = Path(r"C:\Users\Cliente-TechNew\Desktop\TheSims4Tool\NovoVasoTeste2.package")

    D = read_pkg(donor)
    S = read_pkg(spike)
    B = read_pkg(s4s)

    d_by_type = {}
    s_by_type = {}
    for e in D:
        d_by_type.setdefault(e["t"], []).append(e)
    for e in S:
        s_by_type.setdefault(e["t"], []).append(e)

    d_ids = {e["i"] for e in D}
    s_ids = {e["i"] for e in S}

    print("=== INDEX ===")
    for t, name in TYPE.items():
        dn = d_by_type.get(t, [])
        sn = s_by_type.get(t, [])
        if not dn and not sn:
            continue
        print(f"{name}: donor={[hex(x['i']) for x in dn]} spike={[hex(x['i']) for x in sn]}")

    # COBJ
    dc = d_by_type[0xC0DB5AE7][0]
    sc = s_by_type[0xC0DB5AE7][0]
    dname, dtuning, drest = peel_cobj(dc["data"])
    sname, stuning, srest = peel_cobj(sc["data"])
    print("\n=== COBJ ===")
    print("donor", dname, dtuning, "rest", len(drest))
    print("spike", sname, stuning, "rest", len(srest))

    # U64s in COBJ rest that are package instances
    print("\nCOBJ rest u64s that match package instances (donor):")
    for off, v in find_u64s(drest, d_ids):
        owners = [TYPE.get(e["t"], hex(e["t"])) + ":" + hex(e["i"]) for e in D if e["i"] == v]
        print(f"  +{off}: {v:016X} -> {owners}")

    print("\nCOBJ rest u64s that match package instances (spike):")
    for off, v in find_u64s(srest, s_ids):
        owners = [TYPE.get(e["t"], hex(e["t"])) + ":" + hex(e["i"]) for e in S if e["i"] == v]
        print(f"  +{off}: {v:016X} -> {owners}")

    # Orphan refs: u64s in spike COBJ that look like old donor IDs
    print("\nCOBJ rest u64s still equal to DONOR instances (broken if present):")
    for off, v in find_u64s(srest, d_ids):
        print(f"  BROKEN +{off}: {v:016X}")

    # OBJD
    do = d_by_type[0x319E4F1D][0]
    so = s_by_type[0x319E4F1D][0]
    print("\n=== OBJD ===")
    print("donor len", len(do["data"]), "spike len", len(so["data"]))
    print("donor keys", hex(struct.unpack_from("<I", do["data"], 8)[0]), hex(struct.unpack_from("<I", do["data"], 12)[0]))
    print("spike keys", hex(struct.unpack_from("<I", so["data"], 8)[0]), hex(struct.unpack_from("<I", so["data"], 12)[0]))

    print("\nOBJD u64s matching package instances (donor):")
    for off, v in find_u64s(do["data"], d_ids):
        owners = [TYPE.get(e["t"], "?") for e in D if e["i"] == v]
        print(f"  +{off}: {v:016X} {owners}")

    print("\nOBJD u64s matching package instances (spike):")
    for off, v in find_u64s(so["data"], s_ids):
        owners = [TYPE.get(e["t"], "?") for e in S if e["i"] == v]
        print(f"  +{off}: {v:016X} {owners}")

    print("\nOBJD u64s still equal to DONOR instances:")
    for off, v in find_u64s(so["data"], d_ids):
        print(f"  BROKEN +{off}: {v:016X}")

    # LITE / FTPT / SLOT / RIG / MODL presence
    print("\n=== SUPPORT RESOURCES ===")
    for t in (0x03B4C61D, 0xD382BF57, 0xD3044521, 0x8EAF13DE, 0x01661233):
        name = TYPE[t]
        print(name, "donor", len(d_by_type.get(t, [])), "spike", len(s_by_type.get(t, [])))
        if d_by_type.get(t) and s_by_type.get(t):
            de, se = d_by_type[t][0], s_by_type[t][0]
            print(f"  donor i={de['i']:016X} mem={de['mem']} spike i={se['i']:016X} mem={se['mem']} same_bytes={de['data']==se['data']}")

    # Exception args
    arg0 = 370446558990767178
    arg1 = 13063099358557992262
    print("\n=== EXCEPTION ARGS ===")
    print(f"arg0 definition/tuning? {arg0:016X} ({arg0})")
    print(f"arg1 catalog instance?  {arg1:016X} match spike OBJD={arg1 in s_ids}")

    # Compare with working S4S standalone COBJ tuning
    bc = [e for e in B if e["t"] == 0xC0DB5AE7][0]
    bn, bt, br = peel_cobj(bc["data"])
    print("\n=== S4S STANDALONE (NovoVasoTeste2) ===")
    print("COBJ", bn, "tuning", bt)

    # Scan spike OBJD/COBJ for u32/u64 that equal arg0
    print("\n=== arg0 occurrences in spike payloads ===")
    packed = struct.pack("<Q", arg0)
    packed32 = struct.pack("<I", arg0 & 0xFFFFFFFF)
    for e in S:
        if packed in e["data"]:
            print("u64 in", TYPE.get(e["t"], hex(e["t"])), tgi(e), "count", e["data"].count(packed))
        if packed32 in e["data"] and arg0 < (1 << 32):
            print("u32 in", TYPE.get(e["t"], hex(e["t"])))

    # Dump COBJ rest hex interpreted as TGI list (common pattern: typecount entries)
    print("\n=== COBJ rest head hex spike ===")
    print(srest[:128].hex())
    print("=== COBJ rest head hex donor ===")
    print(drest[:128].hex())

    out = {
        "exception_arg0_hex": f"{arg0:016X}",
        "exception_arg1_hex": f"{arg1:016X}",
        "arg1_is_spike_objd": arg1 in s_ids,
        "spike_tuning": stuning,
        "donor_tuning": dtuning,
        "s4s_tuning": bt,
        "cobj_orphan_donor_refs": [
            f"{v:016X}" for _, v in find_u64s(srest, d_ids)
        ],
        "objd_orphan_donor_refs": [
            f"{v:016X}" for _, v in find_u64s(so["data"], d_ids)
        ],
    }
    Path("output/v02_placement_diag.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("\nwrote output/v02_placement_diag.json")


if __name__ == "__main__":
    main()
