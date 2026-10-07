# v0.2 batch placement test

This batch reduces four placement checks to **one game launch**. It builds four independently reminted packages with disjoint resource TGIs and distinct catalog names, using the already prepared probes as sources. The catalog rename is the same name/description edit that previously passed in game. The private COBJ internal name is left unchanged; the control item detects whether that shared name interferes with coexistence.

Build:

```powershell
python experiments/v02_batch_probes.py
```

Packages are in `output/v02_batch_probes/`; `batch_report.json` contains hashes and source provenance. Programmatic audit: **PASS**, four packages, 136 distinct TGIs, no COBJ unresolved references, distinct catalog names. Game results are pending.

| Search name | Source condition | Expected price | What it isolates |
|---|---|---:|---|
| `CCStudio 01 Control` | Price probe that placed successfully | §10 | Batch coexistence and remint control |
| `CCStudio 02 Field90` | Control + OBJD f32@90 `8.0 → 10.0` | §10 | Unknown old catalog write |
| `CCStudio 03 Mesh` | Passing catalog + mug high-detail MLOD | §1,300 | Mesh export/replacement |
| `CCStudio 04 Texture` | Passing catalog + mug Diffuse DST | §1,300 | Texture replacement |

All four can be active simultaneously. Test each by searching its exact name, selecting, checking the green ghost, and placing it. Record any popup or new LastException. The mesh and texture variants are intentionally incomplete visual combinations; placement is the criterion.

**Interpretation:** If `01 Control` fails, the batch coexistence setup is invalid and no conclusion should be drawn about the other variants. If it passes, each other result isolates the listed change relative to a previously passing source package. Do not mix these with older v0.2 packages in Mods.

Offline audits can verify DBPF structure and reference integrity. They cannot replace the in-game definition instantiation and placement check.

## Observed result — 2026-10-03

The user reported that browsing `CCStudio 04 Texture` crashed and closed the game. Two new `lastCrash` files were found with the same category/stack prefix. The screenshot supplied with the report shows a red-X catalog thumbnail for `CCStudio 02 Field90`; it does not show item 04. Placement results for 01–03 were not reported. Therefore the batch has **not** validated coexistence through the control item, and the crash cannot yet be assigned exclusively to the texture payload.

All four batch packages were removed from Mods. The original `texture.package` is preserved as `output/mods_quarantine_identity_test/texture_batch_crash.package`; the others are preserved with `batch_` prefixes. A single-package donor-compatible DST1 replacement is now the next test.
