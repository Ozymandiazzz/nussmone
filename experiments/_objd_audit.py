"""
READ-ONLY OBJD audit for v0.2C placement failure ranking.
Compares light donor, our reminted package, and S4S decorative standalone.
"""
from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

TYPE = {
    0x8EAF13DE: "RIG",
    0xD3044521: "SLOT",
    0x01661233: "MODL",
    0xD382BF57: "FTPT",
    0x03B4C61D: "LITE",
    0x00B2D882: "DST",
    0x01D10F34: "MLOD",
    0x319E4F1D: "OBJD",
    0xC0DB5AE7: "COBJ",
}


def dec(raw, mem):
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
    ents = []
    for _ in range(count):
        t, g, i_hi, i_lo, offset, file_size, mem_size, comp, unk = struct.unpack_from(
            "<IIIIIIIHH", blob, pos
        )
        pos += 32
        raw = blob[offset : offset + (file_size & 0x0FFFFFFF)]
        ents.append(
            {
                "t": t,
                "g": g,
                "i": (i_hi << 32) | i_lo,
                "data": dec(raw, mem_size),
            }
        )
    return ents


def peel_cobj(data: bytes):
    nlen = struct.unpack_from("<I", data, 6)[0]
    name = data[10 : 10 + nlen].decode("ascii", "replace")
    tlen = struct.unpack_from("<I", data, 10 + nlen)[0]
    tuning = data[14 + nlen : 14 + nlen + tlen].decode("ascii", "replace")
    return name, tuning


def find_u64(data: bytes, known: set[int]):
    hits = []
    for off in range(0, max(0, len(data) - 7)):
        v = struct.unpack_from("<Q", data, off)[0]
        if v in known:
            hits.append((off, v))
    return hits


def find_u32_pairs(data: bytes, known: set[int]):
    hits = []
    parts = {}
    for inst in known:
        hi = (inst >> 32) & 0xFFFFFFFF
        lo = inst & 0xFFFFFFFF
        parts[(hi, lo)] = inst
        parts[(lo, hi)] = inst
    for off in range(0, max(0, len(data) - 7)):
        a, b = struct.unpack_from("<II", data, off)
        if (a, b) in parts:
            hits.append((off, parts[(a, b)], a, b))
    return hits


def find_u32_types(data: bytes):
    """Find LE u32 values that look like known resource types."""
    hits = []
    for off in range(0, max(0, len(data) - 3)):
        v = struct.unpack_from("<I", data, off)[0]
        if v in TYPE and v not in (0,):
            hits.append((off, v, TYPE[v]))
    return hits


def dump_objd(label: str, path: Path, id_universe: set[int] | None = None):
    ents = read_pkg(path)
    ids = {e["i"] for e in ents}
    if id_universe is not None:
        ids = ids | id_universe
    objd = next(e for e in ents if e["t"] == 0x319E4F1D)
    cobj = next((e for e in ents if e["t"] == 0xC0DB5AE7), None)
    lite = [e for e in ents if e["t"] == 0x03B4C61D]
    name = tuning = None
    if cobj:
        name, tuning = peel_cobj(cobj["data"])
    d = objd["data"]
    info = {
        "label": label,
        "path": str(path),
        "objd_tgi": f"319E4F1D:80000000:{objd['i']:016X}",
        "objd_len": len(d),
        "version": struct.unpack_from("<I", d, 0)[0],
        "word1": struct.unpack_from("<I", d, 4)[0],
        "u32_8": f"0x{struct.unpack_from('<I', d, 8)[0]:08X}",
        "u32_12": f"0x{struct.unpack_from('<I', d, 12)[0]:08X}",
        "u32_16": struct.unpack_from("<I", d, 16)[0],
        "u32_20": struct.unpack_from("<I", d, 20)[0],
        "u32_24": struct.unpack_from("<I", d, 24)[0],
        "u32_28": f"0x{struct.unpack_from('<I', d, 28)[0]:08X}",
        "f32_90": struct.unpack_from("<f", d, 90)[0] if len(d) > 94 else None,
        "hex_0_64": d[:64].hex(),
        "cobj_name": name,
        "tuning": tuning,
        "has_lite": len(lite) > 0,
        "lite_instances": [f"{e['i']:016X}" for e in lite],
        "le_u64_hits_in_pkg_ids": [
            {"offset": o, "instance": f"{v:016X}"} for o, v in find_u64(d, ids)
        ],
        "u32_pair_hits": [
            {
                "offset": o,
                "instance": f"{v:016X}",
                "hi": f"{a:08X}",
                "lo": f"{b:08X}",
            }
            for o, v, a, b in find_u32_pairs(d, ids)
        ],
        "type_u32_hits": [
            {"offset": o, "type": f"{v:08X}", "name": n} for o, v, n in find_u32_types(d)
        ],
        "index_resources": sorted(
            {
                TYPE.get(e["t"], f"{e['t']:08X}")
                for e in ents
            }
        ),
    }
    return info, ents, objd


def byte_diff(a: bytes, b: bytes):
    n = min(len(a), len(b))
    diffs = []
    for i in range(n):
        if a[i] != b[i]:
            diffs.append({"offset": i, "a": f"{a[i]:02X}", "b": f"{b[i]:02X}"})
    return {
        "len_a": len(a),
        "len_b": len(b),
        "diff_count": len(diffs),
        "diffs": diffs[:80],
    }


def main():
    light_donor = Path(r"C:\Users\Cliente-TechNew\Desktop\TheSims4Tool\Vaso.package")
    decor_s4s = Path(r"C:\Users\Cliente-TechNew\Desktop\TheSims4Tool\NovoVasoTeste2.package")
    decor_bowl = Path(r"C:\Users\Cliente-TechNew\Desktop\TheSims4Tool\tigela.package")
    our = Path("output/v02_catalog_cobjfix.package")
    if not our.exists():
        our = Path("output/v02_catalog_spike.package")

    light_info, light_ents, light_objd = dump_objd("light_donor_Vaso", light_donor)
    our_info, our_ents, our_objd = dump_objd(
        "our_cobjfix", our, id_universe={e["i"] for e in light_ents}
    )
    # Also check our OBJD against light donor IDs specifically (stale refs)
    donor_ids = {e["i"] for e in light_ents}
    our_ids = {e["i"] for e in our_ents}
    stale_le = find_u64(our_objd["data"], donor_ids - our_ids)
    stale_pair = find_u32_pairs(our_objd["data"], donor_ids - our_ids)

    decor_info, decor_ents, decor_objd = dump_objd("decor_s4s_NovoVasoTeste2", decor_s4s)
    bowl_info, bowl_ents, bowl_objd = dump_objd("decor_s4s_tigela", decor_bowl)

    # Diff light donor OBJD vs our reminted OBJD
    diff_light_our = byte_diff(light_objd["data"], our_objd["data"])
    # Diff light donor vs decor S4S (different objects — structural shape compare)
    shape = {
        "light_len": light_info["objd_len"],
        "our_len": our_info["objd_len"],
        "decor_vase_len": decor_info["objd_len"],
        "decor_bowl_len": bowl_info["objd_len"],
        "light_version": light_info["version"],
        "decor_version": decor_info["version"],
    }

    # Scan our OBJD for any occurrence of reminted model/rig ids as hi/lo (should be present if reminted)
    model_new = next(e["i"] for e in our_ents if e["t"] == 0x01661233)
    rig_new = next(e["i"] for e in our_ents if e["t"] == 0x8EAF13DE)
    model_old = next(e["i"] for e in light_ents if e["t"] == 0x01661233)
    rig_old = next(e["i"] for e in light_ents if e["t"] == 0x8EAF13DE)

    def has_inst(data, inst):
        le = struct.pack("<Q", inst) in data
        hi = (inst >> 32) & 0xFFFFFFFF
        lo = inst & 0xFFFFFFFF
        pair_hl = struct.pack("<II", hi, lo) in data
        pair_lh = struct.pack("<II", lo, hi) in data
        return {"le_u64": le, "hi_lo": pair_hl, "lo_hi": pair_lh}

    ranking = [
        {
            "rank": 1,
            "suspect": "OBJD internal / definition linkage",
            "why": (
                "Immediate script popup with no placement ghost => instantiate path. "
                "OBJD is the catalog→definition bridge; our remint patched string keys/price "
                "but did not systematically remint OBJD-internal resource linkage the way S4S does "
                f"(OBJD size light={light_info['objd_len']} vs decor S4S={decor_info['objd_len']})."
            ),
            "evidence": {
                "our_stale_donor_le_u64": [{"offset": o, "i": f"{v:016X}"} for o, v in stale_le],
                "our_stale_donor_u32_pairs": [
                    {"offset": o, "i": f"{v:016X}"} for o, v, a, b in stale_pair
                ],
                "type_markers_in_our_objd": our_info["type_u32_hits"],
                "type_markers_in_decor_objd": decor_info["type_u32_hits"],
                "contains_new_model": has_inst(our_objd["data"], model_new),
                "contains_old_model": has_inst(our_objd["data"], model_old),
                "contains_new_rig": has_inst(our_objd["data"], rig_new),
                "contains_old_rig": has_inst(our_objd["data"], rig_old),
            },
        },
        {
            "rank": 2,
            "suspect": "tuning / definition id (COBJ tuning string + game definition)",
            "why": (
                "create_object arg0 is a definition id not found as raw bytes in package. "
                "Light donor uses object_light_table; decorative S4S clones use "
                "prototype_RetailCompatible. Switching donor removes lamp definition path."
            ),
            "evidence": {
                "light_tuning": light_info["tuning"],
                "decor_tuning": decor_info["tuning"],
                "our_tuning": our_info["tuning"],
            },
        },
        {
            "rank": 3,
            "suspect": "SLOT/RIG linkage",
            "why": "Needed for script object init; COBJ was fixed to new RIG/SLOT but OBJD may still carry independent linkage fields.",
            "evidence": {
                "our_objd_pair_hits": our_info["u32_pair_hits"],
                "decor_objd_pair_hits": decor_info["u32_pair_hits"],
            },
        },
        {
            "rank": 4,
            "suspect": "FTPT",
            "why": "Downgraded: no ghost/red outline means failure occurs before footprint validation.",
            "evidence": "re-ranked lower given no placement preview",
        },
        {
            "rank": 5,
            "suspect": "STBL base split",
            "why": "Still a defect (18 bases) but search works; less likely sole cause of immediate instantiate popup.",
            "evidence": "known from V02_REFERENCE_AUDIT.md",
        },
    ]

    report = {
        "failure_mode": {
            "observation": "No placement ghost/outline; script popup immediately",
            "interpretation": "Object instantiation failure, not footprint rejection",
        },
        "donor_recommendation": {
            "avoid": str(light_donor),
            "avoid_reason": "tuning=object_light_table + lighting semantics",
            "prefer": [str(decor_s4s), str(decor_bowl)],
            "prefer_reason": "tuning=prototype_RetailCompatible (decor clone). Note: these packages still contain a LITE resource entry, but COBJ tuning is not object_light_table.",
            "note": "All local S4S clones inspected still ship a LITE typed resource; decorative selection is by COBJ tuning string, not by absence of LITE bytes.",
        },
        "packages": {
            "light_donor": light_info,
            "our_cobjfix": our_info,
            "decor_s4s_vase": decor_info,
            "decor_s4s_bowl": bowl_info,
        },
        "objd_byte_diff_light_to_our": diff_light_our,
        "objd_shape_compare": shape,
        "ranking": ranking,
        "smallest_fix_proposal": {
            "do_not_apply_yet": True,
            "step_1": "Rebuild pipeline using decorative donor (NovoVasoTeste2 or tigela) with prototype_RetailCompatible — remove object_light_table from path.",
            "step_2": "After rebuild, byte-diff OBJD against an S4S standalone of the SAME donor; remint any hi/lo or embedded MODL/FTPT/SLOT/RIG fields found (same class of bug as COBJ).",
            "step_3": "Only if instantiate still fails with no ghost: unify STBL bases; then SLOT/RSLT deeper.",
            "avoid_now": "Broad FTPT-first fixes; retuning hacks without OBJD parity to S4S.",
        },
    }

    out = Path("output/v02_objd_audit.json")
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("wrote", out)
    print("tuning light", light_info["tuning"], "decor", decor_info["tuning"], "our", our_info["tuning"])
    print("stale le", len(stale_le), "stale pair", len(stale_pair))
    print("our type hits", our_info["type_u32_hits"])
    print("decor type hits", decor_info["type_u32_hits"])
    print("diff count light->our", diff_light_our["diff_count"])
    print("model old/new in our OBJD", has_inst(our_objd["data"], model_old), has_inst(our_objd["data"], model_new))


if __name__ == "__main__":
    main()
