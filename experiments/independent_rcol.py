"""Small independent RCOL container reader/writer for the current MLOD layout.

Format references: Sims4Group MLOD documentation and the MIT-licensed
sims-package2glb RCOL reader. No Sims 4 Studio code is imported or bundled.
This module preserves private chunk payloads; it does not yet encode vertices.

Each VBUF names a vertex-buffer swizzle-info chunk (VBSI) holding one segment
per buffer: vertex size, vertex count, byte offset and one swizzle command per
four bytes of vertex. s4pi's VBSI.FromMesh rebuilds it from the mesh
(VertexCount = mesh vertex count, ByteOffset = stream offset). Every donor and
in-game PASS package satisfies that; v06/v07 kept the donor counts.
"""
from __future__ import annotations

import struct
import math
from dataclasses import dataclass

U32 = struct.Struct('<I')
PAIR = struct.Struct('<II')
MAX_CHUNKS = 4096
SWIZZLE_32 = 1
SWIZZLE_16X2 = 2
# VRTF element format -> swizzle commands, for the formats in the supported
# decorative layout (Short4, UByte4N, Short2, UByte4). Matches the donor VBSI
# and s4pi's per-format mapping.
FORMAT_SWIZZLES = {7: (SWIZZLE_16X2, SWIZZLE_16X2), 8: (SWIZZLE_32,),
                   6: (SWIZZLE_16X2,), 4: (SWIZZLE_32,)}


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

    def keys(self) -> tuple[list[tuple[int, int, int]], list[tuple[int, int, int]]]:
        """Internal and external (type, group, instance) keys of this RCOL."""
        _, _, _, external, count = struct.unpack_from('<5I', self.prefix)
        keys = []
        for index in range(count + external):
            instance, kind, group = struct.unpack_from('<QII', self.prefix, 20 + 16 * index)
            keys.append((kind, group, instance))
        return keys[:count], keys[count:]

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
                # Position-only proxy (8 bytes) or drop-shadow plane (16 bytes):
                # no VRTF, so the VBSI segment carries the vertex size.
                stride = parse_vbsi(self.chunks[self.vbsi_index(refs['vbuf'], base)])[0][0]
            else:
                stride = u32(self.chunks[refs['vrtf']], 8)
            if not 0 < stride <= 256:
                raise ValueError(f'MLOD mesh {index} has invalid vertex stride')
            vertex_end = 16 + u32(entry, 24) + vertex_count * stride
            index_start = u32(entry, 32)
            index_end = 16 + (index_start + triangle_count * 3) * 2
            if vertex_end > len(vertex_buffer) or index_end > len(index_buffer):
                raise ValueError(f'MLOD mesh {index} exceeds its buffers')
            vbsi = self.check_vbsi(refs, base, u32(entry, 24), vertex_count, stride, index)
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
                'refs': refs, 'vbsi': vbsi,
            })
            pos += size
        if pos > len(chunk):
            raise ValueError('MLOD mesh list overflow')
        return meshes

    def vbsi_index(self, vbuf_index: int, base: int) -> int:
        index = self.chunk_ref(u32(self.chunks[vbuf_index], 12), base)
        if index is None:
            raise ValueError(f'VBUF chunk {vbuf_index} has no swizzle info')
        return index

    def check_vbsi(self, refs: dict, base: int, stream_offset: int,
                   vertex_count: int, stride: int, mesh_index: int) -> dict:
        index = self.vbsi_index(refs['vbuf'], base)
        segments = parse_vbsi(self.chunks[index])
        if len(segments) != 1:
            raise ValueError(f'MLOD mesh {mesh_index} VBSI has {len(segments)} segments')
        size, count, offset, commands = segments[0]
        expected = expected_swizzles(self.chunks[refs['vrtf']] if refs['vrtf'] is not None else None,
                                     size)
        problems = []
        if size != stride:
            problems.append(f'vertex size {size} != stride {stride}')
        if count != vertex_count:
            problems.append(f'vertex count {count} != mesh vertex count {vertex_count}')
        if offset != stream_offset:
            problems.append(f'byte offset {offset} != stream offset {stream_offset}')
        if tuple(commands) != expected:
            problems.append(f'swizzles {commands} != {list(expected)}')
        if problems:
            raise ValueError(f'MLOD mesh {mesh_index} VBSI stale: ' + '; '.join(problems))
        return {'chunk': index, 'vertex_size': size, 'vertex_count': count,
                'byte_offset': offset}

    def sync_vbsi(self, vbuf_index: int, vertex_count: int, stream_offset: int = 0) -> 'Rcol':
        """Rewrite the VBSI named by one VBUF for a re-encoded vertex buffer."""
        base = next(i for i, chunk in enumerate(self.chunks) if chunk[:4] == b'MLOD')
        index = self.vbsi_index(vbuf_index, base)
        users = [i for i, chunk in enumerate(self.chunks)
                 if chunk[:4] == b'VBUF' and self.chunk_ref(u32(chunk, 12), base) == index]
        if users != [vbuf_index]:
            raise ValueError(f'VBSI chunk {index} is shared by VBUF chunks {users}')
        segments = parse_vbsi(self.chunks[index])
        if len(segments) != 1:
            raise ValueError('Only single-segment VBSI is supported')
        size = segments[0][0]
        if len(self.chunks[vbuf_index]) != 16 + stream_offset + size * vertex_count:
            raise ValueError('VBUF payload does not match VBSI vertex size and count')
        patched = bytearray(self.chunks[index])
        struct.pack_into('<II', patched, 8, vertex_count, stream_offset)
        return self.replace(index, bytes(patched))


def parse_vbsi(chunk: bytes) -> list[tuple[int, int, int, list[int]]]:
    count = u32(chunk, 0)
    if not 0 < count < 64:
        raise ValueError('Invalid VBSI segment count')
    pos = 4
    segments = []
    for _ in range(count):
        size, vertex_count, offset = struct.unpack_from('<3I', chunk, pos)
        pos += 12
        if size == 0 or size % 4 or pos + size > len(chunk):
            raise ValueError('Invalid VBSI segment')
        commands = list(struct.unpack_from(f'<{size // 4}I', chunk, pos))
        pos += size
        segments.append((size, vertex_count, offset, commands))
    if pos != len(chunk):
        raise ValueError('VBSI has trailing bytes')
    return segments


def expected_swizzles(vrtf: bytes | None, vertex_size: int) -> tuple[int, ...]:
    if vrtf is None:
        # Donor proxies (8 bytes) and the shadow plane (16 bytes) are all 16x2.
        return (SWIZZLE_16X2,) * (vertex_size // 4)
    if vrtf[:4] != b'VRTF':
        raise ValueError('Expected VRTF chunk')
    count = u32(vrtf, 12)
    elements = sorted(struct.unpack_from('<4B', vrtf, 20 + 4 * i) for i in range(count))
    elements.sort(key=lambda element: element[3])
    commands = []
    for usage, _usage_index, fmt, _offset in elements:
        if fmt not in FORMAT_SWIZZLES:
            raise ValueError(f'Unsupported VRTF format {fmt} for usage {usage}')
        commands.extend(FORMAT_SWIZZLES[fmt])
    return tuple(commands)
