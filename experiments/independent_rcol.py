"""Small independent RCOL container reader/writer for the current MLOD layout.

Format references: Sims4Group MLOD documentation and the MIT-licensed
sims-package2glb RCOL reader. No Sims 4 Studio code is imported or bundled.
This module preserves private chunk payloads; it does not yet encode vertices.
"""
from __future__ import annotations

import struct
import math
from dataclasses import dataclass

U32 = struct.Struct('<I')
PAIR = struct.Struct('<II')
MAX_CHUNKS = 4096


def u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError(f'Read outside chunk at {offset}')
    return U32.unpack_from(data, offset)[0]


@dataclass(frozen=True)
class Rcol:
    prefix: bytes  # 20-byte header and all 16-byte resource keys
    chunks: tuple[bytes, ...]

    @classmethod
    def parse(cls, data: bytes) -> 'Rcol':
        if len(data) < 20:
            raise ValueError('RCOL header truncated')
        version, public, _unknown, external, count = struct.unpack_from('<5I', data)
        if version != 3 or not 0 < public <= count <= MAX_CHUNKS or external > MAX_CHUNKS:
            raise ValueError('Unsupported RCOL header')
        table = 20 + 16 * (external + count)
        payload_start = table + 8 * count
        if payload_start > len(data):
            raise ValueError('RCOL key/index table truncated')
        chunks = []
        cursor = payload_start
        for index in range(count):
            offset, size = PAIR.unpack_from(data, table + 8 * index)
            if offset != cursor or size < 4 or offset + size > len(data):
                raise ValueError(f'RCOL chunk {index} has a gap, overlap, or invalid size')
            chunks.append(data[offset:offset + size])
            cursor = offset + size
        if cursor != len(data):
            raise ValueError('RCOL has trailing bytes')
        return cls(data[:table], tuple(chunks))

    def to_bytes(self) -> bytes:
        count = u32(self.prefix, 16)
        if count != len(self.chunks):
            raise ValueError('Chunk count changed')
        cursor = len(self.prefix) + 8 * count
        table = bytearray()
        for chunk in self.chunks:
            if len(chunk) < 4:
                raise ValueError('Empty RCOL chunk')
            table.extend(PAIR.pack(cursor, len(chunk)))
            cursor += len(chunk)
        return self.prefix + table + b''.join(self.chunks)

    def replace(self, index: int, data: bytes) -> 'Rcol':
        chunks = list(self.chunks)
        chunks[index] = data
        return Rcol(self.prefix, tuple(chunks))

    def chunk_ref(self, value: int, base: int) -> int | None:
        if value == 0:
            return None
        if value & 0xF0000000 != 0x10000000:
            raise ValueError(f'Unsupported chunk reference {value:08X}')
        index = base + (value & 0x0FFFFFFF)
        if index >= len(self.chunks):
            raise ValueError(f'Chunk reference outside RCOL: {index}')
        return index

    def inspect_mlod(self) -> list[dict]:
        mlods = [(i, chunk) for i, chunk in enumerate(self.chunks) if chunk[:4] == b'MLOD']
        if len(mlods) != 1:
            raise ValueError(f'Expected one MLOD chunk, got {len(mlods)}')
        base, chunk = mlods[0]
        if len(chunk) < 12 or u32(chunk, 4) >> 8 != 2:
            raise ValueError('Unsupported MLOD version')
        count = u32(chunk, 8)
        if not 0 < count < 64:
            raise ValueError('Invalid MLOD mesh count')
        meshes = []
        pos = 12
        for index in range(count):
            size = u32(chunk, pos)
            pos += 4
            if size < 72 or pos + size > len(chunk):
                raise ValueError(f'MLOD mesh {index} truncated')
            entry = chunk[pos:pos + size]
            refs = {}
            for offset, label, expected in ((8, 'vrtf', b'VRTF'),
                                             (12, 'vbuf', b'VBUF'),
                                             (16, 'ibuf', b'IBUF')):
                ref = self.chunk_ref(u32(entry, offset), base)
                if ref is None and label == 'vrtf':
                    refs[label] = None
                    continue
                if ref is None or self.chunks[ref][:4] != expected:
                    raise ValueError(f'MLOD mesh {index} has invalid {label} reference')
                refs[label] = ref
            vertex_count = u32(entry, 40)
            triangle_count = u32(entry, 44)
            bounds = struct.unpack_from('<6f', entry, 48)
            if (not all(math.isfinite(value) for value in bounds) or
                    any(bounds[axis] > bounds[axis + 3] for axis in range(3))):
                raise ValueError(f'MLOD mesh {index} has invalid bounds')
            if vertex_count == 0 or triangle_count == 0:
                raise ValueError(f'MLOD mesh {index} is empty')
            vertex_buffer = self.chunks[refs['vbuf']]
            index_buffer = self.chunks[refs['ibuf']]
            if len(vertex_buffer) < 16 or len(index_buffer) < 16:
                raise ValueError(f'MLOD mesh {index} has a truncated buffer')
            if refs['vrtf'] is None:
                stride = 8  # position-only shadow/proxy VBUF in this donor layout
            else:
                stride = u32(self.chunks[refs['vrtf']], 8)
            if not 0 < stride <= 256:
                raise ValueError(f'MLOD mesh {index} has invalid vertex stride')
            vertex_end = 16 + u32(entry, 24) + vertex_count * stride
            index_start = u32(entry, 32)
            index_end = 16 + (index_start + triangle_count * 3) * 2
            if vertex_end > len(vertex_buffer) or index_end > len(index_buffer):
                raise ValueError(f'MLOD mesh {index} exceeds its buffers')
            index_values = []
            current = 0
            delta = bool(u32(index_buffer, 8) & 1)
            for at in range(16, index_end, 2):
                value = struct.unpack_from('<h' if delta else '<H', index_buffer, at)[0]
                current = current + value if delta else value
                if at >= 16 + index_start * 2:
                    index_values.append(current)
            if len(index_values) != triangle_count * 3 or not all(
                    0 <= value < vertex_count for value in index_values):
                raise ValueError(f'MLOD mesh {index} has out-of-range triangle indices')
            meshes.append({
                'index': index, 'name_hash': f'{u32(entry, 0):08X}',
                'vertex_count': vertex_count, 'triangle_count': triangle_count,
                'vertex_byte_offset': u32(entry, 24),
                'index_offset': index_start, 'vertex_stride': stride,
                'index_min': min(index_values), 'index_max': max(index_values),
                'bounds': bounds,
                'refs': refs,
            })
            pos += size
        if pos > len(chunk):
            raise ValueError('MLOD mesh list overflow')
        return meshes
