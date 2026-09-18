# Fixtures

Regression assets for the validated CC Studio v0.1 pipeline.
`ccstudio.py` is unchanged. These files exist so a real Windows + Blender 4.4.3 run can be repeated.

Total size of the v0.1 vase case is about 12 MB, so the binaries **are versioned** here.

## Validated case: `v0.1-vase/`

| File | Role |
|---|---|
| `teste.glb` | Real input mesh (single mesh `geometry_0`) |
| `funcionasera.blend` | Real `decor_vase` template used in the passing run |
| `sims_ready.blend` | Pipeline output imported in Sims 4 Studio |
| `basecolor.png` | Extracted Diffuse |
| `report.json` | `status=success` from the passing run |

Expected names if you recreate the layout by hand:

```text
fixtures/v0.1-vase/teste.glb
fixtures/v0.1-vase/funcionasera.blend
fixtures/v0.1-vase/sims_ready.blend
fixtures/v0.1-vase/basecolor.png
fixtures/v0.1-vase/report.json
```

Replay:

```powershell
.\run_test.ps1 -Input "fixtures\v0.1-vase\teste.glb" -Name "v0.1-vase-replay"
```

Live pipeline output still goes to `output/<name>/` (gitignored). Do not overwrite these fixture copies.

## Future break-finding cases (no code changes yet)

Drop one GLB per folder. Use the **same** `funcionasera.blend` template. Goal: see where v0.1 fails.

| Folder | Case | What we want to observe |
|---|---|---|
| `future/A_handle_or_hollow/` | Object with a handle or holes | Fit / decimate / UV / old-geo delete on non-solid vase topology |
| `future/B_asymmetric/` | Asymmetric object | Uniform Z-fit vs visual centering |
| `future/C_short_wide/` | Short / wide object | Height-based uniform scale vs footprint |

Each folder expects:

```text
input.glb
```

Example:

```powershell
.\run_test.ps1 -Input "fixtures\future\A_handle_or_hollow\input.glb" -Name "A_handle_or_hollow"
```

Do not add extra meshes, extra templates, or pipeline branches for these cases until a real failure is recorded.
