# Independent MLOD path — first slice

`experiments/independent_rcol.py` is a standard-library RCOL container reader/writer and structural MLOD audit. It imports no Sims 4 Studio code. The final package audit in `experiments/v03_build_package.py` uses it to validate all five MLODs. `experiments/v04_visual_mlod_export.py` writes visual groups `00000000` and `00000001`; `experiments/v04_proxy_mlod_export.py` writes proxy groups `00010000`, `00010001`, and `00010002`. Both run Blender with `--factory-startup` and import no S4S module.

## Implemented

- Parse the RCOL header, resource-key area, private-chunk table, and contiguous chunk payloads.
- Re-emit the container byte-for-byte when its chunks are unchanged; support replacing one chunk while updating table offsets.
- Follow relative MLOD references to VRTF, VBUF, and IBUF; allow the donor's position-only proxy meshes, which have no VRTF.
- Validate vertex stride, buffer extents, triangle counts, and delta-decoded 16-bit index bounds.
- Report triangle counts for all five LOD groups in the final package audit.
- Encode the `00010000` proxy's 8-byte position vertices and delta-encoded 16-bit triangle indices, update its counts and bounds, and repackage it without loading S4S.
- Encode both visual LODs with the observed 32-byte VRTF: position, normal, UV0, rigid bone assignment and weight, tangent, and UV1. Update UV scales in the four donor material states while preserving all other material data.
- Build all three position-only proxies from progressively simplified geometry.

## Offline evidence

The donor, the earlier high-detail package, and the generated-LOD package each passed byte-exact RCOL roundtrip and mesh-buffer validation across all five MLODs. The generated package has visual triangle counts 5,999 and 3,000, followed by proxy counts 1,500, 800, and 754. This validates container handling and geometry references; it does **not** establish a standalone mesh exporter or an in-game result.

The independent proxy exported 1,409 vertices and 1,500 triangles. Its bounds matched the local S4S export within about `1e-7`; only MLOD group `00010000` changed relative to its input package. The independent visual writer reproduced the high and low triangle counts (5,999 and 3,000 on the mug fixture), with near-identical bounds. On vertex positions present in both outputs, median differences in UV were one 16-bit quantization step (about `3.03e-5`), and median normal and tangent channel differences were about `0.008`.

The full `--mesh-exporter independent_local` path passed offline with three distinct GLBs: mug, asymmetric, and short/wide. Each completed seven stages and produced a 34-resource package with zero unresolved COBJ references. Both geometry stages reported `s4s_loaded: false`. The mug's five visual/proxy triangle counts were 5,999 / 3,000 / 1,500 / 800 / 754. The other two high-detail meshes had 6,000 triangles. None of these independent-geometry packages has an in-game placement result.

2026-10-06 update: the first independent/Python-DST1 package appeared in Build/Buy but showed a red X thumbnail and did not produce a placement ghost when clicked. The five external MLODs were structurally valid; the embedded MODL low-detail MLOD and overall bounds had been left at donor values. The writer and audit now update/check those fields. See `V07_MODL_FIX.md`; the corrected package awaits an in-game result.

## Remaining exporter work

1. Obtain an in-game placement/appearance result for an independently exported package, including its LOD transitions and texture alignment.
2. Broaden beyond the observed decorative-vase VRTF and material layout with new, explicitly validated recipes.
3. Remove remaining distribution dependencies (local donor/template rights, Blender runtime, and the texture encoder's Node dependency) before claiming a standalone product.

The default `.package` path still invokes the locally installed S4S addon. `--mesh-exporter independent_local` replaces all five MLODs without loading it. The source-run desktop interface exposes the independent exporter as an experimental choice. This is an offline milestone; it is not yet the default or a distributable build.

Format references: [Sims4Group MLOD specification](https://github.com/Sims4Group/Sims4Group.github.io/blob/master/0x01D10F34.md), [SimsWiki VRTF specification](https://modthesims.info/wiki.php?title=Sims_4:0x01D0E723), and [sims-package2glb RCOL reader (MIT)](https://github.com/infinition/sims-package2glb/blob/main/src-tauri/src/rcol.rs). CC Studio's Python implementation is its own, limited to the observed decorative-donor layout.
