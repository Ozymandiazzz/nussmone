"""
PRIVATE technical spike — texture only. Not product code.

basecolor (PNG or JPEG-misnamed) → DST5 (shuffled DDS) via open-source @s4tk/images
→ replace DiffuseMap resource in a clone of a test package.

Does NOT copy Sims 4 Studio proprietary code.
Does NOT modify MLOD / OBJD / catalog / other textures.

Diffuse TGI is identified from MaterialDefinition.DiffuseMap inside the
high-detail MLOD of the template (see V02_TEXTURE_SPIKE.md).

  node is required (experiments/node_modules/@s4tk/images).
  Optional Blender is used only to re-encode JPEG→PNG when the input is JFIF.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXPERIMENTS = Path(__file__).resolve().parent
DST_TYPE = 0x00B2D882
HEADER_SIZE = 96

# Proven DiffuseMap for TheSims4Tool\Vaso.package via MLOD MaterialSet:
# MaterialDefinition.DiffuseMap → 00B2D882:80000000:A80B25E5A15B5729
DEFAULT_DIFFUSE_T = DST_TYPE
DEFAULT_DIFFUSE_G = 0x80000000
DEFAULT_DIFFUSE_I = 0xA80B25E5A15B5729


def log(msg: str) -> None:
    print(msg, flush=True)


def parse_args():
    p = argparse.ArgumentParser(prog="v02_texture_spike")
    p.add_argument("--package", required=True, help="template or mesh-spike package to clone")
    p.add_argument("--png", required=True, help="basecolor path (PNG or JPEG bytes)")
    p.add_argument("--output", required=True)
    p.add_argument("--diffuse-t", type=lambda x: int(x, 0), default=DEFAULT_DIFFUSE_T)
    p.add_argument("--diffuse-g", type=lambda x: int(x, 0), default=DEFAULT_DIFFUSE_G)
    p.add_argument("--diffuse-i", type=lambda x: int(x, 0), default=DEFAULT_DIFFUSE_I)
    p.add_argument("--max-mipmaps", type=int, default=12)
    p.add_argument("--blender", default=r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe")
    return p.parse_args()


def read_dbpf_index(path: str):
    with open(path, "rb") as f:
        blob = f.read()
    if blob[:4] != b"DBPF":
        raise RuntimeError("not DBPF: %s" % path)
    count = struct.unpack_from("<I", blob, 36)[0]
    index_offset = struct.unpack_from("<I", blob, 64)[0]
    flags = struct.unpack_from("<I", blob, index_offset)[0]
    if flags != 0:
        raise RuntimeError("spike only handles index flags=0")
    pos = index_offset + 4
    entries = []
    for _ in range(count):
        t, g, i_hi, i_lo, offset, file_size, mem_size, comp, unk = struct.unpack_from(
            "<IIIIIIIHH", blob, pos)
        pos += 32
        fsz = file_size & 0x0FFFFFFF
        entries.append({
            "t": t, "g": g, "i": (i_hi << 32) | i_lo,
            "offset": offset, "file_size": fsz, "mem_size": mem_size,
            "comp_flag": comp, "compressed": comp == 0xFFFF,
            "unknown": unk, "raw": blob[offset:offset + fsz],
        })
    return blob[:HEADER_SIZE], entries


def write_dbpf(header96, entries, out_path: str):
    payload = bytearray()
    payload += header96
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
        comp = e.get("comp_flag", 0)
        if e.get("compressed"):
            comp = 0xFFFF
        payload += struct.pack(
            "<IIIIIIIHH",
            e["t"], e["g"], i_hi, i_lo,
            e["offset"], e["file_size"] | 0x80000000, e["mem_size"],
            comp, e["unknown"],
        )
    index_size = len(payload) - index_offset
    struct.pack_into("<I", payload, 36, len(new_entries))
    struct.pack_into("<I", payload, 44, index_size)
    struct.pack_into("<I", payload, 64, index_offset)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(payload)
    return new_entries


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ensure_png(src: str, blender: str, work_dir: str) -> tuple[str, dict]:
    raw = open(src, "rb").read()
    info = {"source": src, "source_bytes": len(raw), "source_magic": raw[:4].hex()}
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", raw[16:24])
        info.update({"format": "PNG", "width": w, "height": h})
        return src, info
    if raw[:2] == b"\xff\xd8":
        # Misnamed JPEG from Blender img.save() — convert with Pillow (open-source).
        from PIL import Image
        info["format"] = "JPEG"
        out_png = os.path.join(work_dir, "basecolor_converted.png")
        im = Image.open(src)
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA")
        im.save(out_png, format="PNG")
        w, h = im.size
        info.update({
            "converted_png": out_png,
            "width": w,
            "height": h,
            "png_bytes": os.path.getsize(out_png),
            "converter": "Pillow",
        })
        log("[tex] converted JPEG->PNG via Pillow (%dx%d)" % (w, h))
        return out_png, info
    raise RuntimeError("unsupported image magic %s" % raw[:8].hex())


def encode_dst5(png_path: str, max_mipmaps: int, out_bin: str) -> dict:
    js = EXPERIMENTS / "_encode_dst5.mjs"
    js.write_text(
        """
import fs from "fs";
import { createRequire } from "module";
const require = createRequire(import.meta.url);
const { DdsImage } = require("@s4tk/images");

const pngPath = process.argv[2];
const outPath = process.argv[3];
const maxMipMaps = Number(process.argv[4] || 12);

const png = fs.readFileSync(pngPath);
const img = await DdsImage.fromImageAsync(png, { shuffle: true, maxMipMaps });
const dst = img.toShuffled();
fs.writeFileSync(outPath, dst.buffer);
const fourcc = dst.buffer.slice(84, 88).toString("ascii");
console.log(JSON.stringify({
  bytes: dst.buffer.length,
  width: dst.header.width,
  height: dst.header.height,
  fourcc,
  isShuffled: dst.isShuffled,
  encoder: "@s4tk/images",
}));
""".lstrip(),
        encoding="utf-8",
    )
    cmd = ["node", str(js), png_path, out_bin, str(max_mipmaps)]
    log("[tex] encoding DST5 via @s4tk/images")
    out = subprocess.check_output(cmd, cwd=str(EXPERIMENTS), text=True).strip().splitlines()[-1]
    meta = json.loads(out)
    meta["path"] = out_bin
    return meta


def decompress_resource(e: dict) -> bytes:
    raw = e["raw"]
    if e.get("comp_flag") == 0x5A42 or raw[:2] in (b"\x78\xda", b"\x78\x9c", b"\x78\x01"):
        return zlib.decompress(raw)
    return raw


def main():
    args = parse_args()
    package = os.path.abspath(args.package)
    png_in = os.path.abspath(args.png)
    output = os.path.abspath(args.output)
    target = (args.diffuse_t, args.diffuse_g, args.diffuse_i)

    if not os.path.isfile(package):
        raise SystemExit("package not found: %s" % package)
    if not os.path.isfile(png_in):
        raise SystemExit("image not found: %s" % png_in)
    if not (EXPERIMENTS / "node_modules" / "@s4tk" / "images").is_dir():
        raise SystemExit("missing experiments/node_modules/@s4tk/images — run npm install there")

    work = tempfile.mkdtemp(prefix="v02_tex_")
    png_path, img_info = ensure_png(png_in, args.blender, work)
    dst_bin = os.path.join(work, "diffuse.dst5")
    enc = encode_dst5(png_path, args.max_mipmaps, dst_bin)
    new_bytes = open(dst_bin, "rb").read()

    header, entries = read_dbpf_index(package)
    found = None
    for e in entries:
        if (e["t"], e["g"], e["i"]) == target:
            found = e
            break
    if found is None:
        raise SystemExit("Diffuse TGI not in package: %08X:%08X:%016X" % target)

    before_raw = found["raw"]
    before_unc = decompress_resource(found)
    before = {
        "tgi": "%08X:%08X:%016X" % target,
        "file_size": found["file_size"],
        "mem_size": found["mem_size"],
        "comp_flag": "%04X" % found.get("comp_flag", 0),
        "sha256_stored": sha256(before_raw),
        "sha256_uncompressed": sha256(before_unc),
        "uncompressed_len": len(before_unc),
    }

    # Leave uncompressed (comp_flag=0), same strategy that worked for MLOD spike.
    found["raw"] = new_bytes
    found["mem_size"] = len(new_bytes)
    found["compressed"] = False
    found["comp_flag"] = 0

    write_dbpf(header, entries, output)

    # Re-open and verify
    _, after_entries = read_dbpf_index(output)
    after_e = next(e for e in after_entries if (e["t"], e["g"], e["i"]) == target)
    after_unc = decompress_resource(after_e)
    after = {
        "tgi": "%08X:%08X:%016X" % target,
        "file_size": after_e["file_size"],
        "mem_size": after_e["mem_size"],
        "comp_flag": "%04X" % after_e.get("comp_flag", 0),
        "sha256_stored": sha256(after_e["raw"]),
        "sha256_uncompressed": sha256(after_unc),
        "uncompressed_len": len(after_unc),
    }

    changed = before["sha256_uncompressed"] != after["sha256_uncompressed"]
    report = {
        "status": "PASS" if changed and after["sha256_stored"] == sha256(new_bytes) else "FAIL",
        "package_in": package,
        "package_out": output,
        "image": img_info,
        "encoder": enc,
        "diffuse_before": before,
        "diffuse_after": after,
        "bytes_differ": changed,
        "note": "Diffuse only; MLOD/OBJD/other DST unchanged",
    }
    report_path = os.path.join(os.path.dirname(output), "v02_texture_spike_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    log("[tex] wrote %s (%d bytes)" % (output, os.path.getsize(output)))
    log("[tex] report %s" % report_path)
    log("[tex] Diffuse before sha256=%s len=%d" % (before["sha256_uncompressed"], before["uncompressed_len"]))
    log("[tex] Diffuse after  sha256=%s len=%d" % (after["sha256_uncompressed"], after["uncompressed_len"]))
    log("[tex] REPLACED TGI %08X:%08X:%016X" % target)
    if report["status"] != "PASS":
        raise SystemExit("programmatic verification FAILED")
    log("[PASS] Diffuse resource replaced and verified")


if __name__ == "__main__":
    main()
