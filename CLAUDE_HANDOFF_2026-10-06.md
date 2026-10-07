# CC Studio handoff for cloud investigation — 2026-10-06

## Product

Windows desktop software that converts a textured GLB into a standalone Sims 4 decorative-object `.package` with catalog name, description, price, mesh LODs, and texture. Photo-to-3D can become an optional upstream provider later. Avoid a cycle of one game launch per minor change; build and audit offline, then present one well-supported candidate for an integrated game check.

## Local and cloud state

The current working repository is `C:\Users\Cliente-TechNew\Desktop\nussmone` on Windows. The remote GitHub branch `claude/fervent-bardeen-grsnq2` has the v0.1 baseline but lacks local v0.2–v0.7 experiments. Two handoff archives have been prepared: a code/docs/reports archive with no game assets, and a separate private archive with `.package` files, templates, screenshots, fixtures, and old logs. Do not publish the private archive or its contents to the public repo.

The local repo's `.gitignore` ignores `output/` but does **not** ignore `experiments/node_modules/`; a blanket `git add experiments` can stage dependencies. Stage explicit source paths only, or update `.gitignore` first. Some old game-derived `.blend` assets are already tracked in the remote; that is an existing provenance issue, not authorization to publish more.

## Known in-game results

| Package | Result | Meaning |
| --- | --- | --- |
| donor `NovoVasoTeste2.package` | Worked as original vase | Base resource layout for local prototype. |
| `v02_identity_clone.package` | PASS | DBPF writer, remint and basic references did not break placement. |
| `v02_catalog_probe.package` | PASS | Name/description and STBL edits did not break placement. |
| `v02_price_probe.package` | PASS | Price §10 at OBJD offset 16 did not break placement. |
| `v02_texture_dst1_probe.package` | PASS as isolated texture change | Vase remained placeable; texture looked like the other object's UV atlas, as expected. |
| `v06_python_dst1_full_smoke/CCStudio.package` | FAIL | Catalog item §10 shows red X; click produces no ghost and no popup. |
| `v07_modl_fix_full/CCStudio.package` | FAIL | Same red X and no ghost; the v07 MODL correction did not solve the in-game problem. |

**Do not call the S4S-generated full mug a known-good in-game control.** `output/v03_end_to_end_mug/CCStudio.package` and `output/mesh_probe/v02_mesh_probe.package` passed offline only. There is no verified in-game placement result for a full new mesh, whether S4S-exported or independent.

The latest `lastException` file observed was dated 2026-09-22 and the latest `lastCrash` file 2026-10-03. No new exception/crash file was seen during the v06 investigation; after the v07 screenshot, logs had not yet been checked again. The private archive includes the most recent old files for context, not as evidence of a v07 exception.

## Implemented pipeline and failure

- `ccstudio.py`: validated v0.1 GLB → `.blend` + `basecolor.png` Blender engine.
- `experiments/v03_build_package.py`: builds decorative `.package` with mesh, DST1, remint, catalog and optional price. `--mesh-exporter independent_local` calls independent Blender scripts with `--factory-startup` and no S4S imports. The default texture encoder is Pillow DXT1→DST1; the previous Node encoder remains optional.
- `experiments/v04_visual_mlod_export.py`: two external visual MLODs plus low-detail mesh embedded in MODL; `experiments/v04_proxy_mlod_export.py`: three external proxy MLODs.
- `experiments/independent_rcol.py`: RCOL parser/writer, reference and buffer/index/bounds checks.
- Source-run PySide6 UI exposes experimental package generation, donor/template paths, name/description/price. Packaged v0.2 executable still supports only `.blend` output.
- v07 fixed a real v06 omission: embedded MODL low-detail mesh remained the donor vase, and MODL overall bounds did not contain generated geometry. The new audit rejects v06 and approves v07. **Since v07 still fails in game, this was not the complete cause.**
- v07 offline report: seven stages, 34 resources, zero unresolved COBJ references, embedded MODL visual mesh 754 triangles, MODL bbox encloses audited LOD bounds. `PROGRAMMATIC_PASS` is not an in-game result.

## Investigation request

Compare the failing v07 package with the donor and the isolated in-game PASS packages, resource by resource. Check cross-resource and RCOL references beyond COBJ; audit OBJD, MODL and its LOD references, MLOD chunk semantics, MATD/MTST, VRTF/VBUF/IBUF/SKIN, FTPT, THUM and texture. Compare against the S4S-exported full mug only as an **offline reference**. Determine a concrete failure and change the generator/audit accordingly. Produce one candidate and precise acceptance observations. Continue toward a distributable app after the package instantiates; do not bundle S4S code or game assets without rights clarification.

Start with `V03_LOCAL_PIPELINE.md`, `V04_INDEPENDENT_MLOD.md`, `V07_MODL_FIX.md`, the v06/v07 `build_report.json` files, recipe and scripts. The private archive has package binaries and the two failure screenshots.
