"""Encode a PNG as donor-layout DST1 using Pillow's DXT1 writer.

The output retains the donor's 128-byte DDS header. DST1 stores the first
four bytes of every DXT1 block followed by the last four bytes of every block.
"""
from __future__ import annotations

import io
import json
import struct
import sys
from pathlib import Path

from PIL import Image, __version__ as pillow_version

HEADER_SIZE = 128


def encode(source: Path, donor_path: Path, output: Path) -> dict:
    donor = donor_path.read_bytes()
    if len(donor) < HEADER_SIZE or donor[:4] != b'DDS ' or donor[84:88] != b'DST1':
        raise ValueError('Expected donor DDS with DST1 FourCC')
    height, width, mip_count = (struct.unpack_from('<I', donor, offset)[0]
                                for offset in (12, 16, 28))
    if not width or not height or not 1 <= mip_count <= 15:
        raise ValueError('Unsupported donor dimensions or mip count')

    blocks = bytearray()
    with Image.open(source) as image:
        image = image.convert('RGBA')
        source_width, source_height = image.size
        w, h = width, height
        for level in range(mip_count):
            padded_w, padded_h = max(4, w), max(4, h)
            mip = image.resize((padded_w, padded_h), Image.Resampling.BILINEAR)
            with io.BytesIO() as buffer:
                mip.save(buffer, format='DDS', pixel_format='DXT1')
                encoded = buffer.getvalue()
            if encoded[:4] != b'DDS ' or encoded[84:88] != b'DXT1':
                raise ValueError(f'Pillow did not write DXT1 at mip {level}')
            expected = ((w + 3) // 4) * ((h + 3) // 4) * 8
            body = encoded[HEADER_SIZE:]
            if len(body) != expected:
                raise ValueError(f'Mip {level} size {len(body)} != {expected}')
            blocks.extend(body)
            w, h = max(1, w // 2), max(1, h // 2)

    if HEADER_SIZE + len(blocks) != len(donor) or len(blocks) % 8:
        raise ValueError('Encoded mip chain differs from donor layout')
    first = bytearray()
    second = bytearray()
    for offset in range(0, len(blocks), 8):
        first.extend(blocks[offset:offset + 4])
        second.extend(blocks[offset + 4:offset + 8])
    result = donor[:HEADER_SIZE] + first + second

    # Decode the first mip independently using Pillow's DDS reader.
    dxt_header = bytearray(donor[:HEADER_SIZE])
    dxt_header[84:88] = b'DXT1'
    first_mip_size = ((width + 3) // 4) * ((height + 3) // 4) * 8
    with Image.open(io.BytesIO(dxt_header + blocks[:first_mip_size])) as decoded:
        decoded.load()
        if decoded.size != (width, height):
            raise ValueError('Decoded dimensions differ from donor')
    output.write_bytes(result)
    return dict(width=width, height=height, mipCount=mip_count, bytes=len(result),
                fourcc='DST1', decoded=True, sourceWidth=source_width,
                sourceHeight=source_height, encoder='pillow', pillowVersion=pillow_version)


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit('Usage: python encode_dst1_compatible.py image.png donor.dst output.dst')
    print(json.dumps(encode(*(Path(arg) for arg in sys.argv[1:]))))


if __name__ == '__main__':
    main()
