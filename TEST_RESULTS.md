# v0.1.1 generalization tests

**Template:** `fixtures/v0.1-vase/funcionasera.blend` (`0.376 x 0.375 x 0.592`)  
**Blender:** 4.4.3 headless

GLBs:

| Case | File |
|---|---|
| A_handle_or_hollow | `fixtures/future/A_handle_or_hollow/tmpfme2zl9i.glb` |
| B_asymmetric | `fixtures/future/B_asymmetric/model-1789699908959.glb` |
| C_short_wide | `fixtures/future/C_short_wide/model-1789699931683.glb` |

---

## 1. First run (v0.1 Z-fit, no code change)

Pipeline: `v0.1-validated` / `8af5399` — scale = `template_z / source_z`.

| case | exit_code | pipeline_status | faces_before | faces_after | source_uv | cut | S4S | notes |
|---|---|---|---|---|---|---|---|---|
| A_handle_or_hollow | 0 | success | 44732 | 5999 | UVMap | None | **PASS** — handle/hollow, texture, geometry | After Z-fit XY `0.631 x 0.494` (overflow vs template). S4S still accepted. |
| B_asymmetric | 0 | success | 17476 | 6000 | UVMap | None | **PASS** — asymmetry, texture, geometry | After Z-fit XY `0.364 x 0.207`. Scale `0.6335`. |
| C_short_wide | 0 | success | 34272 | 6000 | UVMap | None | **SOFT FAIL** — geometry+texture OK, orientation/fit bad | After Z-fit XY `0.932 x 0.896` (~2.5× template). Scale `1.0255`. |

No HARD FAIL.

Outputs: `output/A_handle_or_hollow/`, `output/B_asymmetric/`, `output/C_short_wide/`.

---

## 2. Fit + explicit rotate (only two pipeline changes)

`ccstudio.py` now:

1. Uniform contain: `scale = min(tx/sx, ty/sy, tz/sz)`, then center XY, align min Z.
2. Optional `--rotate-x/y/z` degrees on the source **before** fit. Default `0 0 0`. No axis heuristics.

UV, Decimate, Base Color, Join, Cut, template logic unchanged.

C was imported short in Z (`0.909 x 0.874 x 0.577`). Explicit test rotation: **`--rotate-x 90`** so it stands (former Y → Z). Chosen only for this rerun, not inferred by the script.

### Commands

```powershell
.\run_test.ps1 -Input "fixtures\future\A_handle_or_hollow\tmpfme2zl9i.glb" -Name "A_handle_or_hollow_v011"

.\run_test.ps1 -Input "fixtures\future\B_asymmetric\model-1789699908959.glb" -Name "B_asymmetric_v011"

.\run_test.ps1 -Input "fixtures\future\C_short_wide\model-1789699931683.glb" -Name "C_short_wide_v011_rx90" -RotateX 90
```

All three: **exit_code 0**, `report.json` `status=success`.

### BBox before → after (fit)

`source_dimensions_before` is measured at fit time (after optional rotate).

| case | rotate | fit_scale | dims before | dims after (v011) | dims after (old Z-fit) |
|---|---|---|---|---|---|
| A_handle_or_hollow_v011 | 0 0 0 | 0.4013 | 0.937 × 0.734 × 0.879 | **0.376 × 0.295 × 0.353** | 0.631 × 0.494 × 0.592 |
| B_asymmetric_v011 | 0 0 0 | 0.6335 | 0.575 × 0.327 × 0.934 | **0.364 × 0.207 × 0.592** | 0.364 × 0.207 × 0.592 (same) |
| C_short_wide_v011_rx90 | 90 0 0 | 0.4138 | 0.909 × 0.577 × 0.874 (post-rx90) | **0.376 × 0.239 × 0.362** | 0.932 × 0.896 × 0.592 (no rotate, Z-fit) |

Template: `0.376 × 0.375 × 0.592`.

- **A:** now limited by X; footprint no longer overflows. Height dropped (0.353 vs old 0.592).
- **B:** Z was already the tight axis; identical bbox to v0.1.
- **C:** after rx90 + contain, all axes ≤ template. Old XY overflow gone.

### New outputs

```text
output/A_handle_or_hollow_v011/
output/B_asymmetric_v011/
output/C_short_wide_v011_rx90/
```

Each has `run.log`, `report.json`, `sims_ready.blend`, `basecolor.png`.

### Final Sims 4 Studio visuals (v0.1.1)

| case | S4S | notes |
|---|---|---|
| A_handle_or_hollow_v011 | **PASS** | Geometry correct, handle preserved, texture aligned, fit correct. |
| B_asymmetric_v011 | **PASS** | Geometry correct, texture aligned, fit acceptable. |
| C_short_wide_v011_rx90 | **PASS técnico** | Geometry correct, texture aligned, fit correct. Orientation via explicit `--rotate-x 90` only. |

No HARD FAIL. No further engine change for v0.1.1.

**v0.1.1-validated.** Next milestone is v0.2 (GLB → `.package` automatic). Not started.
