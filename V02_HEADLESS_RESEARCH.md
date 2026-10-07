# v0.2 private headless spike

**Not product. Not commercial architecture. Not for publish/push of S4Studio files.**

Question answered here:

> É tecnicamente possível pegar nosso `sims_ready.blend` e gerar automaticamente um `.package` funcional, sem abrir a UI do Sims 4 Studio, usando apenas a instalação LOCAL do S4Studio como ferramenta externa?

`ccstudio.py` was not modified. No S4Studio modules were copied into this repo.

---

## Answer (technical, not legal, not commercial)

**Mesh-only subprocess: PASS (package written, exporter ran headless).**

- Blender 4.4.3 `--background`
- Local addon import only (`%APPDATA%\...\addons\s4studio`, `io_sims.py`)
- `save_lod` collected `s4studio_mesh_1` (5984 verts / 18000 indices) plus cut `0` (4 verts)
- Output: `output/v02_mesh_spike.package` (1 905 386 bytes)
- Replaced **only** high-detail MLOD  
  `01D10F34:00000000:A325295480E2E835`  
  mem `246912` → uncompressed `256060`, `comp_flag` `5A42` → `0` (left uncompressed)

**S4S UI / in-game geometry check: pending you.** Open `output/v02_mesh_spike.package` in Studio as validator. A PASS here means the file was produced without clicking Studio, not that this is the shipping design.

Vendor `Package.save()` was **not** used: `Compression.compress()` is unimplemented, and `0x5A42` resources are **zlib**, not the addon’s RefPack path.

---

## Phase 1 — local flow

### How Studio passes MLOD to Blender

C# (not in our repo) fills  
`Sims4Studio_v3.2.6.4 (Star)\Blender\Scripts\Templates\objectexporter.py`:

- `__MLOD__` → temp **uncompressed** MLOD file
- `__STATE__` → geometry state (empty = default)
- `__STATIC_POS_SCALE__` → float (0 = compute)

Blender is launched as a subprocess. The addon does not write DBPF.

Importer template `objectimporter.py` does the reverse: MLOD file → `s4studio_mesh_<i>` and `mesh.data.s4studio.cut = str(i)`.

### How the addon turns the blend back into MLOD bytes

1. `ModelLod.read(stream)` (`s4studio.buybuild.geometry`, RCOL in `s4studio.io`)
2. `save_lod(mlod, geometry_state, static_pos_scale)` (`s4studio.buybuild.blender`)
   - meshes keyed by **`mesh.data.s4studio.cut`**, not object `Cut`
   - `collect_mesh_data` (`s4studio.blender`)
   - `save_mesh` / `preserve_mesh`
3. `ModelLod.write(stream)` → MLOD RCOL bytes (VBUF/IBUF/VRTF/MATD **inside** the RCOL)

Call graph (observed):

```text
save_lod
  apply_all_modifiers, collect_mesh_data, calculate_uv_scales, calculate_pos_scales
  save_mesh | preserve_mesh
collect_mesh_data
  set_context, bpy.ops mesh tris, transform_apply
  rotate_obj(-π/2, X)     ← VIEW_3D
  swizzle UV, split verts
Package.save             ← not usable as-is (see risks)
Package.Compression.uncompress  ← RefPack / s3pi; local vase MLOD is zlib 0x5A42
```

### VIEW_3D / UI vs `--background`

| Piece | Headless? |
|---|---|
| `ModelLod.read` / `write` | yes |
| `save_mesh` vertex pack | yes |
| `collect_mesh_data` edit ops | yes in this run (active mesh) |
| `rotate_obj` + `bpy.ops.transform.rotate` | **no** — indexes `VIEW_3D` area |
| Material tab PNG→DST | C# UI / not in this spike |
| `Package.save` | broken for these packages |

Spike workaround: **monkeypatch `rotate_obj` in-process** (Euler on the active object). Installed addon files were not edited.

`io_sims` must be enabled so `Mesh.s4studio.cut` exists. Validated `sims_ready.blend` already had cut `0` and `1`.

---

## Phase 2 — kill-test (mesh-only)

Script (ours): `experiments/v02_headless_mesh_spike.py`  
Imports local `s4studio` from AppData. Does not copy it.

### Command

```powershell
cd C:\Users\Cliente-TechNew\Desktop\nussmone

& "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" --background --python "experiments\v02_headless_mesh_spike.py" -- `
  --blend "fixtures\v0.1-vase\sims_ready.blend" `
  --template "C:\Users\Cliente-TechNew\Desktop\TheSims4Tool\Vaso.package" `
  --output "output\v02_mesh_spike.package"
```

Log: `output\v02_mesh_spike_run.log`  
Report: `output\v02_mesh_spike_report.json`

### Inputs

| Role | Path |
|---|---|
| blend | `fixtures/v0.1-vase/sims_ready.blend` |
| template package | `TheSims4Tool\Vaso.package` (local, not in git) |
| addon | `%APPDATA%\Blender Foundation\Blender\4.4\scripts\addons` |

### TGI replaced

```text
type    01D10F34  MLOD
group   00000000  high-detail
instance A325295480E2E835
```

Unchanged: other MLODs, all DST, OBJD, STBL, RIG, SLOT, FTPT, LITE, catalog wrapper.

### Log (trimmed)

```text
[spike] s4studio_mesh_0 cut already=0
[spike] s4studio_mesh_1 cut already=1
[spike] zlib-decompressing MLOD (comp_flag=0x5A42)
[spike] MLOD uncompressed bytes=246912
[spike] save_lod (geometry_state='', static_pos_scale=0)
collecting mesh data from s4studio_mesh_0
[spike] rotated active object via Euler (axis=X rad=1.5708)
collecting mesh data from s4studio_mesh_1
5984 vertices in mesh data
[spike] new MLOD bytes=256060
[spike] REPLACED TGI 01D10F34:00000000:A325295480E2E835
[PASS] mesh-only package written
EXIT 0
```

Output DBPF re-read: magic `DBPF`, 34 entries, replacement MLOD `comp=0`, size 256060.

---

## Risks found on the local install

1. **`rotate_obj` requires VIEW_3D** — must wrap, not edit vendor files.
2. **`shutil.abspath` in `Package.__init__`** — missing; patch `shutil.abspath = os.path.abspath` in-process.
3. **`Package.save` / `Compression.compress`** — `NotImplementedError`. Not used.
4. **MLOD on disk is zlib `comp_flag=0x5A42` (`78 DA`)** — vendor uncompress path is RefPack (`0xFFFF`). Spike used stdlib `zlib.decompress`.
5. **`IndexEntry.fetch(ModelLod)`** failed `cExternal == 0` when compression was not zlib-decoded first.
6. High-detail MLOD contains **cut 0 and cut 1**; both were rewritten (Studio does the same).

---

## License / EULA files found (list + relevant quotes)

No legal conclusion. Paths are on this machine’s S4Studio 3.2.6.4 (Star) copy.

| File | Path |
|---|---|
| EULA | `...\Sims4Studio_v3.2.6.4 (Star)\EULA.rtf` |
| Third-party licenses (folder) | `...\Sims4Studio_v3.2.6.4 (Star)\Licenses\` |
| Json.Net.txt, IronSnappy.txt, AMDCompress.rtf, GongSolutions.WPF.DragDrop.txt, simplifyCS.txt, MahApps.Metro.IconPacks.txt, Serilog.txt, Dirkster.HL.txt, WPFLocalizationExtension.txt, HelixToolkit.txt, MahApps.Metro.txt, protobuf-net.txt, VirtualizingWrapPanel.txt, SharpZipLib.txt, sqlite-net.txt, AvalonEdit.txt, Rick.txt, PropertyChanged.Fody.txt | same `Licenses\` folder |

**EULA.rtf (excerpts that mention license / commercial use / third parties):**

> Sims 4 Studio grants you a revocable, non-exclusive, non-transferable, limited license to download, install and use the Application solely for your personal purposes strictly in accordance with the terms of this Agreement.

> You agree not to, and you will not permit others to:  
> a) license, sell, rent, lease, assign, distribute, transmit, host, outsource, disclose or otherwise commercially exploit the Application or make the Application available to any third party.  
> b) use the Application to infringe on EA’s intellectual property rights.  
> c) use the Application to generate content based on game content made by others if you do not have permission to use their material.

No EULA sentence specifically named “automation” or “headless Blender”. The quotes above are the closest commercial / distribution restrictions in that file.

**Licenses\Rick.txt** is a third-party zlib-style notice (Gibbed / sims4), including permission for commercial use of **that** third-party material — not a grant over Sims 4 Studio itself.

Addon Python under `%APPDATA%\...\addons\s4studio` has `__author__ = 'Sims 4 Studio'` in `__init__.py`; no separate LICENSE file next to the addon.

---

## What was added to git (ours only)

- `experiments/v02_headless_mesh_spike.py`
- `V02_HEADLESS_RESEARCH.md` (this file)

Not added: S4Studio program files, `s4studio/` addon, `.package` outputs, GLBs.

`output/` remains gitignored.

Texture swap was **not** implemented (per spike stop).
