# v0.2 research spike (read-only)

**Date:** 2026-09-21  
**Status:** research only. `ccstudio.py` unchanged. No package writer implemented.  
**Question:** smallest path `sims_ready.blend` + `basecolor.png` + `template.package` → `final.package`.

Sources inspected:

- `%APPDATA%\Blender Foundation\Blender\4.4\scripts\addons\s4studio\`
- `%APPDATA%\Blender Foundation\Blender\4.4\scripts\addons\io_sims.py`
- `TheSims4Tool\Sims4Studio_v3.2.6.4 (Star)\Blender\Scripts\Templates\`
- Local validated-style packages in `TheSims4Tool\` (`Vaso.package`, `NovoVasoTeste2.package`, …)

---

## Current S4S flow (`.blend` → package)

Sims 4 Studio is a **C# app** that owns the `.package`. The Blender addon is a **geometry library**, not a package editor UI.

### Import (Studio → Blender)

Template: `objectimporter.py`

1. C# extracts the current **MLOD** RCOL to a temp file (`__MLOD__`) and optional RIG (`__RIG__`).
2. Blender `ModelLod.read()` parses that file.
3. `load_lod()` creates `s4studio_mesh_<index>` and sets **`mesh.data.s4studio.cut = str(mesh_index)`**.
4. Diffuse preview PNGs are loaded from the same temp folder (`0.png`, `1.png`, …).
5. User saves a `.blend`. That is what v0.1 already produces (`sims_ready.blend`).

### Export (Blender → Studio)

Template: `objectexporter.py`

```text
mlod = ModelLod()
mlod.read(mlod_file)          # original MLOD bytes from the package
save_lod(mlod, state, scale)  # overwrite mesh chunks from the open .blend
mlod.write(mlod_file.out)     # new MLOD RCOL bytes
```

Blender **does not write DBPF**. It writes **MLOD bytes**. C# then:

1. Puts `.out.mlod` back into the package as type `0x01D10F34`.
2. Separately, the Material tab replaces Diffuse: PNG → **DST** (`0x00B2D882`). That conversion is **not** in the Python addon (`DDSResource` is a raw byte blob).

So the Studio “Import mesh from Blender” button is already: **open blend + original MLOD → new MLOD**. v0.2 is that loop without the GUI.

---

## Can we call it headless?

**Yes, with two caveats.** S4S already launches Blender as a subprocess with those templates. `--background` is possible in principle because `save_lod` / `collect_mesh_data` are plain Python.

Blockers:

1. **`rotate_obj()` requires a `VIEW_3D` area.**  
   `s4studio/blender/__init__.py` does  
   `[a for a in bpy.context.screen.areas if a.type == "VIEW_3D"][0]`  
   then `bpy.ops.transform.rotate`.  
   `--background` has no 3D view → the same `IndexError: VIEW_3D` that already broke earlier tests.  
   `collect_mesh_data()` always calls `rotate_obj(-π/2, 'X')` after applying transforms (Sims Y-up vs Blender Z-up).

2. **`Package.__init__` uses `shutil.abspath`**, which does not exist. Loading a package from stock addon code crashes unless `shutil.abspath = os.path.abspath` is patched. Do **not** rely on editing the vendor addon; wrap it.

3. **`io_sims` must be registered** so `Mesh.s4studio.cut` exists. `save_lod` indexes meshes by **cut string**, not by object name. Empty cut → “No meshes found to import”.

4. Edit-mode `bpy.ops` (`quads_convert_to_tris`, `mode_set`) need an active mesh. Override/context is required, same class of problem as v0.1, already solved there with `temp_override`.

Headless is viable if we **reuse `save_lod`** and **replace only `rotate_obj`** with a matrix rotate (or run Blender with a hidden window, not `--background`). Do not reimplement MLOD packing.

---

## What the exporter actually produces

`save_lod` mutates a `ModelLod` (`TAG='MLOD'`, type `0x01D10F34`) **in memory** and `RCOL.write()` serializes it.

It does **not** emit a `.package`.

Inside one MLOD RCOL (private chunks, not separate DBPF entries):

| Chunk | Type ID | Role |
|---|---|---|
| MLOD | `0x01D10F34` | LOD container |
| VBUF | `0x01D0E6FB` | vertex buffer |
| IBUF | `0x01D0E70F` | index buffer |
| VRTF | `0x01D0E723` | vertex format (copied from template) |
| MATD | `0x01D0E75D` | material definition (kept) |
| SKIN | `0x01D0E76B` | skin controller if present |

`save_mesh()` fills VBUF/IBUF from `SimMeshData` (positions, normals, swizzled UVs, tangents, bone `transformBone`). UV scales and pos scales are recomputed; shader/VRTF stay from the template mesh.

**MODL** (`0x01661233`) is a small parent (LOD list + bounds). The exporter template does **not** rewrite MODL. Studio may refresh bounds in C#. v0.2 should check whether keeping the old MODL is enough for a vase (likely yes if LOD count unchanged).

---

## Relevant files and dependencies

| Path | Role |
|---|---|
| `Templates/objectexporter.py` | C# fill-in script: read MLOD → `save_lod` → write `.out.mlod` |
| `Templates/objectimporter.py` | C# fill-in script: MLOD → `s4studio_mesh_*` + cut |
| `s4studio/buybuild/blender.py` | `save_lod`, `save_mesh`, `load_lod`, `load_mesh` |
| `s4studio/blender/__init__.py` | `collect_mesh_data`, `rotate_obj`, `swizzle_uv` |
| `s4studio/buybuild/geometry.py` | `ModelLod` / `Model` / VBUF / IBUF / VRTF RCOL read+**write** |
| `s4studio/io.py` | `RCOL` serializer (public/private chunks) |
| `s4studio/data/package.py` | DBPF `Package` load/save/replace resource |
| `s4studio/core.py` | `ResourceKey` TGI |
| `s4studio/material/__init__.py` | `DDSResource` (raw DST bytes only) |
| `s4studio/buybuild/catalog.py` | `CatalogProductObject` OBJD |
| `io_sims.py` | registers `mesh.data.s4studio.cut`; Blender Tools UI |

Python deps: Blender’s `bpy`/`bmesh`/`mathutils` only. No extra pip packages inside the addon.

C# still owns: clone identity, STBL, catalog name, thumbnail (`0x81CA1A10` in these files), PNG→DST.

---

## Validated template `.package` TGI (local)

Inspected `TheSims4Tool\Vaso.package` (clone of a vase; 35 entries). Same **shape** as `NovoVasoTeste2.package` / `tigela.package`.

**Not present** as top-level DBPF resources: `OBJC` `0x02DC343F`, `VPXY` `0x736884F1`, packed CST `0x0333406C`, standalone MATD/VBUF. Those live inside MLOD or are omitted in this S4S object-clone layout.

| Tag | Type | Count in `Vaso.package` | v0.2 action |
|---|---|---|---|
| STBL | `0x220557DA` | 18 (languages) | keep |
| RIG | `0x8EAF13DE` | 1 | keep |
| SLOT | `0xD3044521` | 1 | keep |
| **DST** | **`0x00B2D882`** | **3** | **replace Diffuse** (largest DST is the color map; Vaso ~5.5 MB uncompressed). Keep the other two (spec/shadow-style). |
| **MLOD** | **`0x01D10F34`** | **5** (groups `0`, `1`, `00010000`, `00010001`, `00010002`) | **replace high LOD** (`g=0`). Others are lower LOD / shadow; leaving them = original vase at distance. |
| LITE | `0x03B4C61D` | 1 | keep |
| **MODL** | **`0x01661233`** | **1** (same instance as MLOD) | keep unless bounds break in-game |
| FTPT | `0xD382BF57` | 1 | keep (footprint) |
| catalog wrapper | `0xC0DB5AE7` | 1 | keep (pairs with OBJD instance) |
| **OBJD** | **`0x319E4F1D`** | **1** | keep (catalog / flags / name) |
| helper | `0x81CA1A10` | 1 (~68 B) | keep |
| NMAP | `0x0166038C` | 1 (empty in these files) | keep / ignore |

Instance sharing: MODL + MLODs + LITE share one instance (e.g. `A325295480E2E835` on `Vaso.package`). OBJD shares instance with `0xC0DB5AE7`.

`NovoVasoTeste2.package` is the same 35-type layout with a **small** DST (~43 KB) and smaller main MLOD — typical after a Studio mesh+diffuse save. That is the layout v0.2 must emit.

---

## What we can reuse headless

- `ModelLod.read` / `write` (real MLOD bytes)
- `save_lod` + `collect_mesh_data` (mesh → VBUF/IBUF)
- `Package.find_key` / `save_resource` / `save` (clone DBPF, swap resources)
- Template VRTF + MATD + bone `transformBone` from existing MLOD
- OBJD / STBL / SLOT / FTPT / extra DST unchanged

Need a **thin wrapper**, not a format reimplementation:

1. Copy `template.package` → `final.package`
2. Open `sims_ready.blend` in Blender 4.4.3
3. Ensure `s4studio_mesh_1` has `mesh.data.s4studio.cut` matching the MLOD mesh index (`"1"` if that is mesh 1; confirm against template — `load_lod` uses `str(mesh_index)`)
4. Extract MLOD `g=0` bytes → `save_lod` → write bytes back
5. Encode `basecolor.png` to DST and replace the Diffuse `0x00B2D882`
6. `Package.save()`

`ccstudio.py` stays the mesh/UV/fit robot. Package step is a **new** script beside it.

---

## What must be replaced vs kept

**Replace**

- High-detail **MLOD** (geometry + UVs from `sims_ready.blend`)
- Diffuse **DST** (from `basecolor.png`)

**Keep from template**

- OBJD + catalog wrapper + STBL (name, category, catalog id)
- RIG, SLOT, FTPT, LITE
- Specular/shadow DST
- Lower MLODs until we decide to generate them (optional; visual LOD pop)

**Do not invent**

- New instance IDs, new OBJD, new categories, CAS, S4TK-from-scratch MLOD

---

## Smallest architecture

```text
ccstudio.py (unchanged)
    → sims_ready.blend + basecolor.png

s4s_package.py  (new, later)
    copy template.package
    blender --background:
        patch rotate_obj (matrix, no VIEW_3D)
        enable io_sims
        ModelLod.read(extracted.mlod)
        save_lod(...)
        ModelLod.write(out.mlod)
    Package.save_resource(MLOD)
    encode PNG → DST, Package.save_resource(DST)
    Package.save(final.package)
```

One Blender subprocess, one Package rewrite. No Electron, no Studio UI.

PNG→DST is the only piece **not** in the addon. Options later: `texconv` / NVIDIA, or a small DXT1/5 writer. Do not reverse-engineer DST if a known encoder exists.

---

## Risks

| Risk | Why |
|---|---|
| VIEW_3D in `rotate_obj` | `--background` crash unless patched or GUI Blender |
| `shutil.abspath` in `Package` | stock loader crash |
| Cut mismatch | `save_lod` keys off `mesh.data.s4studio.cut`, not object `Cut` and not only the name `s4studio_mesh_1` |
| Multi-LOD leftover | distant LODs still EA vase if only `g=0` is replaced |
| MODL bounds | stale bounding box / fade |
| DST format | wrong FourCC / mips → pink or crash in-game |
| Addon license / fragility | vendor code; wrap, don’t fork unless a one-line patch is unavoidable |
| Empty NMAP | loader fabricates a namemap; saving without care could dirty the package |
| Axis | exporter applies −90° X; double-rotate if we also rotate in ccstudio |

---

## Recommendation A / B / C

### A — Reuse S4S Python (recommended)

Drive `save_lod` + `Package` exactly as Studio does. Patch `rotate_obj` and `abspath` in **our** wrapper. Replace MLOD + Diffuse DST. Keep catalog.

**Why:** MLOD/VBUF/IBUF writers already exist and match Studio’s validated packages. Smallest honest v0.2.

### B — Automate the Sims 4 Studio GUI

Sendkeys / UI automation of “Import mesh” + “Import diffuse”.

**Why not:** not headless, brittle, still needs Studio installed and focused. Reject for v0.2.

### C — Reimplement binary formats (S4TK / custom MLOD)

Rewrite MODL/MLOD/DST from specs.

**Why not now:** duplicates `buybuild/geometry.py` which already has `write_rcol`. Use S4TK later only if DST encoding or DBPF save in the addon is too broken — not for mesh packing.

**Decision for v0.2 start:** **A**. Do not implement yet.

---

## Out of scope (still)

UI, Electron, installer, new templates, CAS, TRELLIS, login, payments, changing `ccstudio.py`.
