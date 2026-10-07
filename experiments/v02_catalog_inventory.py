"""
Read-only DBPF inventory / diff for v0.2C catalog research.
No proprietary S4S code. Public DBPF index layout only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

HEADER_SIZE = 96

TYPE_NAMES = {
    0x220557DA: "STBL",
    0x8EAF13DE: "RIG",
    0xD3044521: "SLOT",
    0x00B2D882: "DST",
    0x01D10F34: "MLOD",
    0x03B4C61D: "LITE",
    0x01661233: "MODL",
    0xD382BF57: "FTPT",
    0xC0DB5AE7: "COBJ",  # catalog wrapper (pairs with OBJD)
    0x319E4F1D: "OBJD",
    0x81CA1A10: "THUM_META",
    0x0166038C: "NMAP",
}


def tgi_str(t: int, g: int, i: int) -> str:
    return f"{t:08X}:{g:08X}:{i:016X}"


def read_dbpf(path: Path):
    blob = path.read_bytes()
    if blob[:4] != b"DBPF":
        raise SystemExit(f"not DBPF: {path}")
    count = struct.unpack_from("<I", blob, 36)[0]
    index_offset = struct.unpack_from("<I", blob, 64)[0]
    flags = struct.unpack_from("<I", blob, index_offset)[0]
    if flags != 0:
        raise SystemExit(f"index flags={flags:#x} unsupported in {path}")
    pos = index_offset + 4
    entries = []
    for _ in range(count):
        t, g, i_hi, i_lo, offset, file_size, mem_size, comp, unk = struct.unpack_from(
            "<IIIIIIIHH", blob, pos
        )
        pos += 32
        fsz = file_size & 0x0FFFFFFF
        raw = blob[offset : offset + fsz]
        if comp == 0xFFFF and len(raw) >= 2 and raw[:2] == b"\x5a\x42":
            try:
                data = zlib_decompress(raw)
            except Exception:
                data = raw
        else:
            data = raw
        entries.append(
            {
                "t": t,
                "g": g,
                "i": (i_hi << 32) | i_lo,
                "file_size": fsz,
                "mem_size": mem_size,
                "comp": comp,
                "sha256": hashlib.sha256(data).hexdigest(),
                "data_len": len(data),
                "raw": raw,
                "data": data,
            }
        )
    return entries


def zlib_decompress(raw: bytes) -> bytes:
    import zlib

    # EA 5A42 wrapper: skip 2-byte magic then zlib
    return zlib.decompress(raw[2:])


def inventory(path: Path) -> dict:
    entries = read_dbpf(path)
    by_type: dict[str, list] = {}
    for e in entries:
        name = TYPE_NAMES.get(e["t"], f"T_{e['t']:08X}")
        by_type.setdefault(name, []).append(
            {
                "tgi": tgi_str(e["t"], e["g"], e["i"]),
                "t": e["t"],
                "g": e["g"],
                "i": e["i"],
                "data_len": e["data_len"],
                "sha256": e["sha256"],
            }
        )
    objds = [e for e in entries if e["t"] == 0x319E4F1D]
    cobjs = [e for e in entries if e["t"] == 0xC0DB5AE7]
    mlods = [e for e in entries if e["t"] == 0x01D10F34]
    modls = [e for e in entries if e["t"] == 0x01661233]
    dsts = [e for e in entries if e["t"] == 0x00B2D882]
    stbls = [e for e in entries if e["t"] == 0x220557DA]
    return {
        "path": str(path),
        "count": len(entries),
        "by_type_counts": {k: len(v) for k, v in sorted(by_type.items())},
        "OBJD": [{"tgi": tgi_str(e["t"], e["g"], e["i"]), "i": e["i"], "sha256": e["sha256"], "data_len": e["data_len"]} for e in objds],
        "COBJ": [{"tgi": tgi_str(e["t"], e["g"], e["i"]), "i": e["i"], "sha256": e["sha256"], "data_len": e["data_len"]} for e in cobjs],
        "MODL": [{"tgi": tgi_str(e["t"], e["g"], e["i"]), "i": e["i"], "sha256": e["sha256"]} for e in modls],
        "MLOD_instances": sorted({e["i"] for e in mlods}),
        "MLOD_groups": sorted({e["g"] for e in mlods}),
        "DST_instances": sorted({e["i"] for e in dsts}),
        "STBL_instances": sorted({e["i"] for e in stbls}),
        "all_tgis": [tgi_str(e["t"], e["g"], e["i"]) for e in entries],
        "entries": entries,
        "by_type": by_type,
    }


def instance_set(inv: dict) -> set[int]:
    return {e["i"] for e in inv["entries"]}


def diff_instances(a: dict, b: dict) -> dict:
    ia, ib = instance_set(a), instance_set(b)
    return {
        "only_a": sorted(ia - ib),
        "only_b": sorted(ib - ia),
        "shared": sorted(ia & ib),
        "shared_count": len(ia & ib),
        "a_count": len(ia),
        "b_count": len(ib),
    }


def find_u64s_in(data: bytes, targets: set[int]) -> list[dict]:
    hits = []
    for off in range(0, max(0, len(data) - 7)):
        v = struct.unpack_from("<Q", data, off)[0]
        if v in targets:
            hits.append({"offset": off, "value": f"{v:016X}"})
    return hits


def scan_cross_refs(inv: dict) -> dict:
    """Find where key instance IDs appear inside other resources' payloads."""
    entries = inv["entries"]
    objd_i = {e["i"] for e in entries if e["t"] == 0x319E4F1D}
    cobj_i = {e["i"] for e in entries if e["t"] == 0xC0DB5AE7}
    modl_i = {e["i"] for e in entries if e["t"] == 0x01661233}
    dst_i = {e["i"] for e in entries if e["t"] == 0x00B2D882}
    interesting = objd_i | cobj_i | modl_i | dst_i
    refs = []
    for e in entries:
        if e["t"] in (0x01D10F34,):  # MLOD huge; skip full scan for speed later if needed
            # still scan — important for DiffuseMap refs
            pass
        hits = find_u64s_in(e["data"], interesting)
        # filter self-instance matches at start noise — keep all for research
        if hits:
            refs.append(
                {
                    "host": tgi_str(e["t"], e["g"], e["i"]),
                    "type": TYPE_NAMES.get(e["t"], f"{e['t']:08X}"),
                    "hits": hits[:40],
                    "hit_count": len(hits),
                }
            )
    return {"interesting_instances": [f"{x:016X}" for x in sorted(interesting)], "refs": refs}


def parse_product_info_guids(objd_data: bytes) -> dict:
    """
    Best-effort peel of CatalogProductObject:
    u32 version, TGIList..., presets..., optional instance_name, then ProductInfo.
    We do NOT reimplement full parser — locate ProductInfo by scanning for
    consecutive u64 name_guid + desc_guid near known layout after presets.
    """
    if len(objd_data) < 64:
        return {"error": "too small"}
    version = struct.unpack_from("<I", objd_data, 0)[0]
    # Fallback: search for price float  near name/desc keys — report raw head hex
    return {
        "version": version,
        "version_hex": f"{version:#x}",
        "head_hex": objd_data[:64].hex(),
        "size": len(objd_data),
        "note": "full OBJD parse deferred to spike using structured approach",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="donor/template")
    ap.add_argument("--b", required=True, help="S4S standalone / re-save")
    ap.add_argument("--c", required=True, help="our texture spike")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    packs = {
        "A_donor": inventory(Path(args.a)),
        "B_s4s": inventory(Path(args.b)),
        "C_spike": inventory(Path(args.c)),
    }

    # Drop heavy raw/data from JSON export
    slim = {}
    for k, inv in packs.items():
        slim[k] = {kk: vv for kk, vv in inv.items() if kk not in ("entries",)}
        slim[k]["objd_head"] = parse_product_info_guids(inv["entries"][[e["t"] for e in inv["entries"]].index(0x319E4F1D)].get("data") if False else next(e["data"] for e in inv["entries"] if e["t"] == 0x319E4F1D))
        slim[k]["cross_refs_summary"] = {
            "ref_hosts": len(scan_cross_refs(inv)["refs"]),
        }

    report = {
        "packages": {k: {kk: vv for kk, vv in slim[k].items() if kk != "by_type"} for k in slim},
        "diff_A_vs_B_instances": diff_instances(packs["A_donor"], packs["B_s4s"]),
        "diff_A_vs_C_instances": diff_instances(packs["A_donor"], packs["C_spike"]),
        "diff_B_vs_C_instances": diff_instances(packs["B_s4s"], packs["C_spike"]),
        "A_vs_B_OBJD": {
            "A": packs["A_donor"]["OBJD"],
            "B": packs["B_s4s"]["OBJD"],
            "same_instance": packs["A_donor"]["OBJD"][0]["i"] == packs["B_s4s"]["OBJD"][0]["i"] if packs["A_donor"]["OBJD"] and packs["B_s4s"]["OBJD"] else None,
            "same_hash": packs["A_donor"]["OBJD"][0]["sha256"] == packs["B_s4s"]["OBJD"][0]["sha256"] if packs["A_donor"]["OBJD"] and packs["B_s4s"]["OBJD"] else None,
        },
        "A_vs_C_OBJD": {
            "A": packs["A_donor"]["OBJD"],
            "C": packs["C_spike"]["OBJD"],
            "same_instance": packs["A_donor"]["OBJD"][0]["i"] == packs["C_spike"]["OBJD"][0]["i"] if packs["A_donor"]["OBJD"] and packs["C_spike"]["OBJD"] else None,
            "same_hash": packs["A_donor"]["OBJD"][0]["sha256"] == packs["C_spike"]["OBJD"][0]["sha256"] if packs["A_donor"]["OBJD"] and packs["C_spike"]["OBJD"] else None,
        },
        "shared_instances_A_C_detail": [],
    }

    shared = set(diff_instances(packs["A_donor"], packs["C_spike"])["shared"])
    for e in packs["C_spike"]["entries"]:
        if e["i"] in shared:
            report["shared_instances_A_C_detail"].append(
                {
                    "tgi": tgi_str(e["t"], e["g"], e["i"]),
                    "type": TYPE_NAMES.get(e["t"], f"{e['t']:08X}"),
                    "sha_match_donor": any(
                        d["i"] == e["i"] and d["t"] == e["t"] and d["g"] == e["g"] and d["sha256"] == e["sha256"]
                        for d in packs["A_donor"]["entries"]
                    ),
                }
            )

    # Deeper cross-ref for spike package (limited)
    report["C_cross_refs"] = scan_cross_refs(packs["C_spike"])

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Make JSON serializable
    def scrub(o):
        if isinstance(o, dict):
            return {k: scrub(v) for k, v in o.items() if k not in ("raw", "data", "entries")}
        if isinstance(o, list):
            return [scrub(x) for x in o]
        if isinstance(o, (int, float, str, bool)) or o is None:
            return o
        return str(o)

    out.write_text(json.dumps(scrub(report), indent=2), encoding="utf-8")
    print(f"wrote {out}")
    print("A OBJD", report["A_vs_B_OBJD"]["A"])
    print("B OBJD", report["A_vs_B_OBJD"]["B"])
    print("C OBJD", report["A_vs_C_OBJD"]["C"])
    print("A_vs_B same_instance", report["A_vs_B_OBJD"]["same_instance"])
    print("A_vs_C same_instance", report["A_vs_C_OBJD"]["same_instance"])
    print("shared A-C count", report["diff_A_vs_C_instances"]["shared_count"])


if __name__ == "__main__":
    main()
