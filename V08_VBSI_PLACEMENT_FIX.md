# v0.8: stale vertex-buffer swizzle info, off-footprint mesh, widened audit

v06 and v07 appeared in Build/Buy with a red X thumbnail and produced no placement ghost. With no THUM resource, the game renders the catalog thumbnail from the model itself, so both symptoms mean the model never loaded, while catalog, price and strings were fine. This investigation compared v07 resource by resource and chunk by chunk with the donor `NovoVasoTeste2.package`, the four in-game PASS probes, and the S4S-exported mug (offline reference only).

## Findings

### 1. Stale VBSI in every regenerated mesh (load-level defect)

Each VBUF header names a small "vertex buffer swizzle info" (VBSI) chunk: one segment with vertex size, **vertex count**, byte offset, and one swizzle command per four vertex bytes. The open-source reference implementation, s4pi `VBSI.FromMesh`, rebuilds it from the mesh: `VertexCount = mesh.VertexCount` and `ByteOffset = mesh.StreamOffset`.

| Package | In game | Meshes whose VBSI count ≠ VBUF/mesh count |
| --- | --- | --- |
| donor, identity clone, catalog, price, texture probes | PASS | 0 |
| v06 | FAIL | 5 (e.g. LOD0: VBSI says 824 vertices, VBUF holds 7,968) |
| v07 | FAIL | 6 (the five MLODs plus the MODL-embedded mesh) |
| S4S mug (offline only) | never tested | 1 (LOD0: 824 vs 7,645) |

The writers replaced VBUF/IBUF/MLOD and kept the donor VBSI. If the engine sizes or validates the vertex buffer from the VBSI, it sees 824 vertices while indices reach 7,967, and the model fails to load. That would explain both the red X and the missing ghost. This is the only load-level defect found that splits every in-game PASS package from every failing or never-tested new-mesh package. The S4S mug carrying the same defect is consistent with this: it has no in-game result.

What else was checked and found consistent in v07:
- Vertex bytes: on positions shared with the S4S export of the same blend, positions, blend indices, weights and UV1 are byte-identical. Normals, tangents and UV0 differ by at most 1 LSB.
- VRTF, SKIN, MTST, LITE, RIG, RSLT, FTPT and the MODL LOD table are unchanged from the donor.
- OBJD→RIG/RSLT/MODL/FTPT references resolve. In the code, `COBJ = 0xC0DB5AE7` is the Object Definition and `OBJD = 0x319E4F1D` is the Catalog Object, the reverse of the usual TS4 labels. The existing "COBJ reference" check already covers the Object Definition, so nothing was renamed.
- MODL→5 external MLOD keys resolve, and every MATD texture id names a DST present in the package. No donor instance id survives remint in any encoding.
- DST1: header and payload size match the donor. With the same unshuffle, the EA donor texture decodes cleanly, and the Node probe and the Python v07/v08 textures decode to the same mug atlas.

### 2. Mesh placed off the donor footprint (visual defect)

`templates/decor_vase/template.blend` (hash-identical to `fixtures/v0.1-vase/funcionasera.blend`) is the validated v0.1 object, not the NovoVasoTeste2 donor. Its `s4studio_mesh_1` is off-centre and starts 6 cm above the floor, and the v0.1 engine fits the GLB to it. In game space, v07's LOD0 spans X −0.32..0.05 and Z −0.30..−0.01, and floats from Y = 0.06, while the donor vase is centred on the origin from Y = 0. This would not stop the model from loading, but the object would hover beside its footprint.

### 3. Minor

- MLODs were stored uncompressed. That is valid DBPF, but every PASS package uses zlib. Removed as a variable.
- The proxy exporter never grew the MODL bounds. Once the mesh sits on the floor, collapse decimation leaves proxy vertices up to 5.7 mm below it, outside the MODL box. v07 passed this check only because its geometry was displaced.
- `inspect_mlod` assumed an 8-byte stride for every mesh without a VRTF. The drop-shadow plane is 16 bytes, and the VBSI now provides that stride.

## Changes

- `experiments/independent_rcol.py`: parses VBSI, validates it in `inspect_mlod()` (size, count, offset, VRTF-derived swizzles), adds `Rcol.sync_vbsi()` and `Rcol.keys()`.
- `experiments/v04_visual_mlod_export.py`, `experiments/v04_proxy_mlod_export.py`: sync VBSI after each re-encode and store MLODs zlib-compressed. The proxy exporter also grows the MODL bounds.
- `experiments/v08_place_on_donor.py` (new, Blender `--factory-startup`): translates `s4studio_mesh_1` only, centring it in X/Z on the donor LOD0 and resting it on the donor floor. No scale or rotation.
- `experiments/v08_mesh_normalize.py` (new, stdlib): applies the same VBSI sync and compression to `s4s_local` output.
- `experiments/v03_build_package.py`: new stages `01b_place_on_donor` (both exporters) and `02n_mesh_normalize` (`s4s_local`). The final audit adds VBSI on every mesh, zlib for MLOD/MODL, LOD0 anchor error ≤ 1 mm, MODL external refs, MATD→DST refs, and a leftover-donor-id scan.

The new audit rejects v06 and v07 (`MLOD mesh 1 VBSI stale: vertex count 824 != mesh vertex count 7968`) and accepts the donor and all four PASS probes.

## Candidate

`output/v08_candidate/CCStudio.package` was built from the same `mug.glb` as v07, with `--mesh-exporter independent_local --price 10`. Catalog name **CCStudio v08 Candidate**. SHA-256 `7312353fc9e893ec356042413ef5cf416a36aeba0df0c730bbbb2fb48adf46d9`, 366,368 bytes, 34 resources.

- Stages: all nine exited 0, final `PROGRAMMATIC_PASS`. Built here with Blender's `bpy` 5.0.1 module, not Blender 4.4. Rebuilding on Windows produces a different SHA (random remint salt) and should pass the same audit.
- LOD triangles: 5,999 / 3,000 / 1,500 / 800 / 754, plus 754 in the MODL.
- All nine VBSI segments match, all MLOD/MODL are zlib, LOD0 anchor error is 7e-9 m, 5 MODL refs and 3 texture refs resolve, and no donor ids are left.
- An independent decoder rebuilt LOD0 from the package bytes (VBUF, IBUF, MATD UV scale, DST1) and rendered it. It shows the textured mug standing on the floor at the origin. Decoded the same way, v07 floats off-centre.

`PROGRAMMATIC_PASS` is still not an in-game result. v08 changes three things relative to v07: VBSI, placement, and compression. Only VBSI is expected to matter for loading.

## In-game acceptance check

1. Close the game. In `Mods`, remove the v06/v07 `CCStudio.package` and any other CC Studio test package, then add only the v08 package. Delete `localthumbcache.package` from the Sims 4 user folder.
2. Open a lot and go to Build mode. Search **CCStudio v08 Candidate**.
3. Record each observation separately:
   - **A. Thumbnail:** a mug image instead of the red X.
   - **B. Ghost:** clicking the item shows a placement ghost.
   - **C. Position:** the mug sits on the floor, centred on the cursor tile, not floating or offset.
   - **D. Appearance:** white mug with an orange band. Shading may look odd because two of the three textures are still the donor vase's maps (see below). Note it, but it is not a failure for this test.
   - **E. Distance:** zooming out keeps a mug shape (LOD1 and proxies), with no vase and no disappearance.
   - **F. Logs:** whether a new `lastException*.txt` or `lastCrash*.txt` appears.

How to read the result: A+B pass means the package instantiates, and VBSI is the leading explanation. If A or B still fail, VBSI was not sufficient. The next single discriminating build would then pass the donor vase's own geometry through the independent writer: it separates "our writer" from "new geometry". Bring the new `lastException` if there is one.

## Distribution blockers still present

The independent path rebuilds all mesh geometry and the Diffuse texture. The candidate still carries donor-derived content: RIG, RSLT and LITE unchanged; two of three DST textures (the donor vase's other maps); the drop-shadow plane mesh; MATD/MTST/SKIN/VRTF chunks; and the FTPT/OBJD/COBJ layouts. A distributable app cannot bundle the donor or its derivatives without rights clarification. It must either have the user point it at their own donor, as today, or generate these resources from scratch. Replacing the two remaining textures with generated neutral maps is the next step toward that, and also removes the shading caveat in D.
