# CC Studio v0.3 local package pipeline

`experiments/v03_build_package.py` is one local command for **GLB → `.blend` → standalone `.package`** using the supported decorative-vase recipe. It composes the validated v0.1 GLB engine, the existing local mesh exporter, donor-compatible DST1 texture encoding, DBPF remint, catalog strings, and optional price. It writes a stage log and a final audit. It does not modify `ccstudio.py` or the v0.1 CLI.

Example:

```powershell
python experiments/v03_build_package.py `
  --input "C:\path\object.glb" `
  --name "My CC Object" `
  --description "Custom decor" `
  --price 10
```

PowerShell shortcut:

```powershell
.\ccstudio-package.ps1 -Input "C:\path\object.glb" -Name "My CC Object" -Price 10
```

Optional flags: `--output`, `--rotate-x`, `--rotate-y`, `--rotate-z`, `--blender`, `--blend-template`, `--donor`, and `--recipe`. `CCSTUDIO_DECOR_VASE_DONOR` can set the donor path. The Python command defaults to the recipe's base price when `--price` is omitted. The output directory must not exist; the default creates a timestamped directory under `output/`. Successful output contains `CCStudio.package`, `build_report.json`, stage logs, `stages/engine/sims_ready.blend`, and `stages/engine/basecolor.png`. A failed run keeps its logs and records `FAILED` in the report.

Before building, install `requirements-package.txt`, then run `python experiments/v03_build_package.py --check --mesh-exporter independent_local` or `.\ccstudio-package.ps1 -Check -MeshExporter independent_local`. This reports Blender, the blend template, donor package, scripts, and Pillow DXT1 support as JSON, and exits nonzero if something is missing. The source-run desktop package mode performs the same preflight before creating an output folder. Blender can be selected with `--blender` or `CCSTUDIO_BLENDER`. The default DST1 encoder now uses Pillow; Node and `node_modules` are no longer required for this path. The previous Node encoder remains available with `--texture-encoder node` or `-TextureEncoder node`; select its runtime with `--node`, `CCSTUDIO_NODE`, or `-Node`. A portable Node executable placed at `tools/node.exe` is also detected for that option. This is dependency detection, not a distributable installer.

The Python encoder preserves the donor's 128-byte DDS header, DST1 shuffle, 256×256 size and nine mip levels in the validated vase recipe. It decodes its first mip with Pillow before writing. On the mug fixture, both encoders produced a 43,832-byte DST1; source-image RGB RMS error was 7.73 for Python versus 5.90 for the previous Node encoder. The slight quality difference is a BC1 encoder difference, not a missing texture. The resulting Python-encoded `.package` still requires an in-game appearance result.

The source-run desktop form now accepts an optional donor `.package` and blend template path. The same paths are passed to preflight and build; an incompatible donor is rejected by the recipe validator. Empty fields retain the local defaults. This allows a creator to point the app at their own resources without editing Python paths.

Full independent pipeline smoke with the Python encoder: `output/v06_python_dst1_full_smoke/CCStudio.package` and `build_report.json`. It passed seven stages, produced 34 resources and zero unresolved COBJ references while Node was deliberately configured to a nonexistent path. `game_placement` remains `NOT_TESTED`.

## Recipe and current limits

The source-run desktop app (`python -m app.main`) now offers an experimental `.package` output mode. Select a GLB, choose that format, and set catalog name, description, and price. The app calls the same recipe builder and shows the resulting package and report in a fresh output directory. The packaged v0.2 desktop executable still offers only `.blend` and texture output because this experimental path requires the local Python project and installed S4S addon.

- The current recipe is the decorative `NovoVasoTeste2.package`. `recipes/decor_vase.json` records its template, Diffuse resource, catalog baseline, and local mesh exporter. The builder validates that layout before writing. This is the only supported recipe and exporter today.
- Blender 4.4 and the user's locally installed Sims 4 Studio Blender addon are required. The addon is invoked locally and is **not** bundled or copied. This workflow is a private technical prototype; a distributable commercial build still needs permission or an independent MLOD exporter.
- The supported input is a textured GLB with a usable UV map. The v0.1 engine handles decimation, fitting, explicit rotation, UV transfer, and basecolor extraction.
- The highest-detail MLOD is replaced. Lower LODs and donor metadata remain from the decorative vase recipe. Broader object categories need their own recipes.
- Optional `--lod-strategy generated` also rebuilds the second visual LOD and three proxy LODs from simplified copies of the GLB mesh. It runs offline and records triangle counts in `stages/lod_report.json`. This is experimental and has no in-game placement result; the default `donor-lower` retains the passing path.
- Optional `--proxy-exporter independent` replaces proxy group `00010000` using Blender and CC Studio's own RCOL/VBUF/IBUF writer, with `--factory-startup` to disable installed addons. It composes with `--lod-strategy generated` and has passed an eight-stage offline smoke. The remaining MLODs still depend on the local S4S exporter.
- Optional `--mesh-exporter independent_local` builds all five MLODs with CC Studio's own RCOL/VBUF/IBUF writers, running Blender with `--factory-startup`. This experimental mode passed offline with three GLB fixtures and is selectable in the source-run desktop app. It does not yet have an in-game result and is not bundled in the v0.2 executable.
- `PROGRAMMATIC_PASS` means the DBPF reopens, catalog strings and price resolve, STBL locales share a base, and COBJ references resolve. It does not claim that each generated asset was placed in game.

## End-to-end smoke

Ran the mug fixture `fixtures/future/A_handle_or_hollow/tmpfme2zl9i.glb` through all six stages. The result is `output/v03_end_to_end_mug/CCStudio.package` with 34 resources, zero unresolved COBJ references, name **CCStudio End to End Mug**, and price **§10**. The engine also produced `sims_ready.blend` and `basecolor.png`. All stage exit codes were zero. This is a programmatic smoke; the package has not been placed in game.

The corrected texture-only vase package was seen in game with its changed texture and placed, as reported by the user. Its atlas comes from another source object, so the odd pattern on the vase is expected. This supports the DST1 encoding path but does not yet establish the full new GLB-to-package composition in game.

## Generated LOD smoke (offline)

`--lod-strategy generated` completed all seven stages with the mug fixture in `output/v03_generated_lods_smoke/`. It changed exactly four lower/proxy MLOD payloads beyond the known high-detail MLOD. Exported triangle counts were 3000, 1500, 800, and 754; the farthest proxy could not reach the nominal 750 exactly. The final package reopened with 34 resources, price §10, and no unresolved COBJ references. No game placement result exists for this option.
