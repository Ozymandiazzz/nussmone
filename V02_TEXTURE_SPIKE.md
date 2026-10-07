# v0.2B texture spike (private)

**Not product. Not commercial S4Studio architecture. No proprietary code copied into the repo.**  
`ccstudio.py` and the mesh exporter were not modified.

## Question

Can `basecolor.png` become a valid Sims 4 Diffuse resource and replace only that resource in a package, without S4Studio UI?

**Programmatic result: PASS** (bytes replaced, TGI present, hashes differ).  
**Manual S4S / in-game: pending you** on `output/v02_texture_spike.package`.

---

## Phase 1 — Diffuse TGI (not “first DST”)

Template: `C:\Users\Cliente-TechNew\Desktop\TheSims4Tool\Vaso.package`

All `0x00B2D882` (`DDSResource` / DST) entries:

| TGI | Size (uncompressed) | DDS header |
|---|---|---|
| `00B2D882:80000000:A80B25E5A15B5729` | 5 592 560 | 2048×2048, mipmaps=12, **DST5** |
| `00B2D882:80000000:DAAC7D25A00E7538` | 87 536 | 256×256, mipmaps=9, DST5 |
| `00B2D882:80000000:E72CCB33FE2BC0DB` | 22 000 | 128×128, mipmaps=8, DST5 |

**Authoritative Diffuse** comes from high-detail MLOD → `MaterialSet` → `MaterialDefinition` → parameter **`DiffuseMap`**:

```text
DiffuseMap = 00B2D882:80000000:A80B25E5A15B5729
```

Same TGI is also referenced as `AlphaMap` on some material variants.  
`NormalMap` → `...:DAAC7D25A00E7538` (left untouched).  
Specular-like map → `...:E72CCB33FE2BC0DB` (left untouched).

So the Diffuse is the **2048 DST5**, identified by MATD, not by picking arbitrarily.

---

## Phase 2 — encoder

| Item | Choice |
|---|---|
| Resource type | **DST5** (DDS signature + FourCC `DST5`, EA shuffle) — type `0x00B2D882` |
| Encoder | **`@s4tk/images` 0.2.4** (MIT) — open-source, Priority A |
| DXT backend | `silent-dxt-js` (dependency of S4TK) |
| Shuffle | `DdsImage.fromImageAsync(..., { shuffle: true })` then `toShuffled()` |
| JPEG→PNG | **Pillow** (open-source) — pipeline `basecolor.png` is JFIF despite `.png` |

S4Studio local `Compressonator_MT_DLL.dll` was **not** used (avoid proprietary encoder in the spike path).

### Input / output formats

| Stage | Format | Dimensions | Bytes |
|---|---|---|---|
| Pipeline file | JPEG (misnamed `.png`) | 1024×1024 RGB | 121 386 |
| After Pillow | PNG | 1024×1024 | ~877 KB |
| Encoded Diffuse | DST5 shuffled DDS | 1024×1024 | 1 398 224 |
| Template Diffuse | DST5 shuffled DDS | 2048×2048 | 5 592 560 (zlib-stored in package) |

Resolution drop 2048→1024 follows the source texture; FourCC still DST5.

### Licenses (dependencies used)

- `@s4tk/images` — MIT (`experiments/node_modules/@s4tk/images/LICENSE`)
- Pillow — HPND/PIL license (installed locally for conversion)
- S4Studio EULA — listed earlier in `V02_HEADLESS_RESEARCH.md`; **not** redistributed; not used as encoder here

`experiments/node_modules/` should stay **out of git** (local install only).

---

## Phase 3 — package patch

Script: `experiments/v02_texture_spike.py`

For a coherent mug test, mesh was inserted first with the **existing** v0.2A mesh spike (no mesh-logic edits):

1. `output/A_handle_or_hollow_v011/sims_ready.blend` → mesh into clone of `Vaso.package`  
   → `output/v02_texture_spike_meshbase.package`
2. Texture spike replaced **only** Diffuse on that package  
   → `output/v02_texture_spike.package`

Untouched: MLOD/MODL, OBJD, catalog, footprint, slots, Normal/Specular DST, other LODs.

### Commands

```powershell
cd C:\Users\Cliente-TechNew\Desktop\nussmone

# one-time: encoder deps
cd experiments
npm install @s4tk/images@0.2.4
pip install pillow
cd ..

# optional mesh base (mug geometry; reuses v0.2A script as-is)
& "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" --background --python "experiments\v02_headless_mesh_spike.py" -- `
  --blend "output\A_handle_or_hollow_v011\sims_ready.blend" `
  --template "C:\Users\Cliente-TechNew\Desktop\TheSims4Tool\Vaso.package" `
  --output "output\v02_texture_spike_meshbase.package"

# texture spike
python experiments\v02_texture_spike.py `
  --package "output\v02_texture_spike_meshbase.package" `
  --png "output\A_handle_or_hollow_v011\basecolor.png" `
  --output "output\v02_texture_spike.package"
```

Log: `output/v02_texture_spike_run.log`  
Report JSON: `output/v02_texture_spike_report.json`

---

## Programmatic proof

**Replaced TGI:** `00B2D882:80000000:A80B25E5A15B5729`

| | Before | After |
|---|---|---|
| stored size | 1 601 874 (zlib `5A42`) | 1 398 224 (uncompressed) |
| uncompressed len | 5 592 560 | 1 398 224 |
| sha256 (uncompressed) | `a6a2fb392422e73df11d6c8220a49bf252a757b4a0551d46bfeb2dce9dd8893c` | `b5582ab6141dbd8269961cbe0233cc6807a53bea0af253c16baebc50dafdd940` |

Re-open checks:

- Diffuse TGI still present  
- `bytes_differ: true`  
- **MLOD identical** to meshbase  
- **Normal DST identical**  
- only Diffuse bytes changed  

Status in report: **`PASS`**

---

## Manual acceptance (you)

Open `output/v02_texture_spike.package` in Sims 4 Studio:

1. Package opens  
2. Mug mesh visible  
3. Mug Diffuse appears without Texture > Import  
4. Then same file in-game  

---

## Scope / safety

- No S4Studio source vendored into git  
- No push  
- No UI / photo→3D / catalog edits  
- Texture path is open-source (`@s4tk/images` + Pillow)  
- Spike stopped after package + this report  
