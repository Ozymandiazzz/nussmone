"""Parse STBL / peel ProductInfo-ish fields from OBJD for catalog research."""
from __future__ import annotations

import struct
import zlib
from pathlib import Path


def decompress_resource(raw: bytes, mem_size: int) -> bytes:
    if len(raw) == mem_size and raw[:4] == b"STBL":
        return raw
    if raw[:2] == b"\x5a\x42":
        return zlib.decompress(raw[2:])
    try:
        out = zlib.decompress(raw)
        return out
    except zlib.error:
        return raw


def read_dbpf(path: Path):
    blob = path.read_bytes()
    count = struct.unpack_from("<I", blob, 36)[0]
    index_offset = struct.unpack_from("<I", blob, 64)[0]
    flags = struct.unpack_from("<I", blob, index_offset)[0]
    assert flags == 0
    pos = index_offset + 4
    entries = []
    for _ in range(count):
        t, g, i_hi, i_lo, offset, file_size, mem_size, comp, unk = struct.unpack_from(
            "<IIIIIIIHH", blob, pos
        )
        pos += 32
        fsz = file_size & 0x0FFFFFFF
        raw = blob[offset : offset + fsz]
        data = decompress_resource(raw, mem_size)
        entries.append(
            {
                "t": t,
                "g": g,
                "i": (i_hi << 32) | i_lo,
                "raw": raw,
                "data": data,
                "mem_size": mem_size,
                "comp": comp,
                "unk": unk,
            }
        )
    return entries


def parse_stbl(data: bytes) -> list[tuple[int, str]]:
    assert data[:4] == b"STBL", data[:8]
    # STBL\x05 ... common layout used by S4TK / community tools
    # After magic: version u16/u8 variants exist; S4TK uses:
    # 'STBL', u8 compressed?, u16/u32...
    # Inspect: b'STBL\x05\x00\x00\x02\x00\x00\x00\x00...'
    count = struct.unpack_from("<I", data, 6)[0] if False else None
    # Try S4TK-compatible: offset 6 may not be count.
    # Manual: many TS4 STBLs:
    # 0: 'STBL'
    # 4: u8 = 5 (version)
    # 5: u8 compressed flag
    # 6: u16 unused?
    # 8: u64 numEntries? or u32
    ver = data[4]
    # Community format (Sims4Tools):
    # magic4, version1, compressed1, numEntries4, reserved2? 
    num = struct.unpack_from("<I", data, 6)[0]
    # If num is huge, try offset 8
    if num > 10000:
        num = struct.unpack_from("<I", data, 8)[0]
        pos = 14
    else:
        pos = 10
    # Actually from head STBL\x05\x00\x00\x02\x00\x00\x00\x00 — 
    # ver=5, flag=0, then 02 00 00 00 = 2 entries at offset 6
    num = struct.unpack_from("<I", data, 6)[0]
    reserved = struct.unpack_from("<H", data, 10)[0] if len(data) > 12 else 0
    pos = 12
    # Some formats have 6 more reserved zeros
    if data[12:18] == b"\x00" * 6:
        pos = 18
    entries = []
    # Two-pass style: first table of (key, flags, length), then strings
    # Sims4Toolkit StringTable:
    # after header, for each: u32 key, u8 flags, u16 length — then string blob
    table = []
    try:
        for _ in range(num):
            key = struct.unpack_from("<I", data, pos)[0]
            flags = data[pos + 4]
            length = struct.unpack_from("<H", data, pos + 5)[0]
            table.append((key, flags, length))
            pos += 7
        for key, flags, length in table:
            s = data[pos : pos + length].decode("utf-8", errors="replace")
            pos += length
            # null terminator?
            if pos < len(data) and data[pos] == 0:
                pos += 1
            entries.append((key, s))
    except Exception as e:
        return [("parse_error", f"{e} at {pos} num={num} head={data[:24].hex()}")]
    return entries


def peel_cobj(data: bytes) -> dict:
    # observed: u16 ver=2, u32 ?, u32 nlen, name bytes, u32 tlen, tuning bytes, ...
    ver = struct.unpack_from("<H", data, 0)[0]
    pos = 2
    unk = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    nlen = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    name = data[pos : pos + nlen].decode("ascii", errors="replace")
    pos += nlen
    tlen = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    tuning = data[pos : pos + tlen].decode("ascii", errors="replace")
    pos += tlen
    return {"version": ver, "unk": unk, "name": name, "tuning": tuning, "rest_offset": pos, "rest_len": len(data) - pos}


def main():
    for label, path in [
        ("A", Path(r"C:\Users\Cliente-TechNew\Desktop\TheSims4Tool\Vaso.package")),
        ("B", Path(r"C:\Users\Cliente-TechNew\Desktop\TheSims4Tool\NovoVasoTeste2.package")),
        ("C", Path(r"output\v02_texture_spike.package")),
    ]:
        ents = read_dbpf(path)
        print("====", label, path.name, "====")
        for e in ents:
            if e["t"] == 0xC0DB5AE7:
                print("COBJ", peel_cobj(e["data"]))
            if e["t"] == 0x220557DA and (e["i"] >> 56) == 0:
                print("STBL0", parse_stbl(e["data"]))
            if e["t"] == 0x319E4F1D:
                d = e["data"]
                # scan for f32 reasonable prices (1..5000)
                prices = []
                for off in range(0, len(d) - 3):
                    f = struct.unpack_from("<f", d, off)[0]
                    if 1.0 <= f <= 5000.0 and f == int(f):
                        prices.append((off, f))
                print("OBJD len", len(d), "candidate int prices", prices[:20])


if __name__ == "__main__":
    main()
