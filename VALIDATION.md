# CC Studio v0.1 — validation

**Status: VALIDATED**  
**Tag: `v0.1-validated`**  
**Branch: `claude/fervent-bardeen-grsnq2`**  
**Relevant commit before this baseline: `3fa7393`**

`ccstudio.py` is the pipeline. Do not refactor it. Do not add product features from this document.

## What was validated

Real Windows run, then a manual Sims 4 Studio import:

- Blender 4.4.3 headless
- Input: `teste.glb` (mesh `geometry_0`)
- Template: `funcionasera.blend` (`s4studio_mesh_1`)
- Faces: `287966` → `6000`
- Base Color extracted to `basecolor.png`
- Source UV `UVMap` copied onto `uv_0`
- Old template geometry removed
- `sims_ready.blend` written
- `report.json` `status=success`
- `sims_ready.blend` imported in Sims 4 Studio
- `basecolor.png` imported as Diffuse
- Preview correct: orange/white vase, UV aligned

Frozen copies: `fixtures/v0.1-vase/`.

## Environment

| Item | Value |
|---|---|
| OS | Windows 10 |
| Blender | 4.4.3 (`C:\Program Files\Blender Foundation\Blender 4.4\blender.exe`) |
| Script | `ccstudio.py` (headless only) |
| Template object | `s4studio_mesh_1` |
| Studio | Sims 4 Studio, manual import (no `.package` generation) |

## Acceptance criteria (v0.1)

Pass only if all of these hold:

1. `blender.exe --background --python ccstudio.py` exits `0`
2. `output/<name>/report.json` has `"status": "success"`
3. `sims_ready.blend` exists
4. `basecolor.png` exists
5. Target mesh is still exactly one `s4studio_mesh_1`
6. Face count after decimate is `> 0` and around the 6000 target when the source is above that
7. `uv_0` is present and non-empty
8. Manual S4S import of the blend + Diffuse preview looks correctly textured (UV not scrambled)

v0.1 is **one recipe**: single-mesh GLB + this vase template. Other object types are out of scope.

## Open risks (do not pre-fix)

- `Cut` on the validated template was `None`. If a real S4S vase template has a Cut value, this fixture does not prove Cut preservation for that value.
- Uniform scale is height (Z) only. Short/wide objects may look wrong even if QA passes.
- Auto-fit centers X/Y and puts the source base on the template Z min. Handles, holes, and asymmetry are untested.
- v0.1 refuses GLBs with zero meshes or more than one mesh.
- Decimate is collapse to 6000 faces; silhouette damage is not scored.
- Preview material in the blend is optional; Diffuse in Studio is the real check.
- `funcionasera.blend` is the file that worked in the real test. It may already be a working Studio scene rather than a virgin S4S export.

## Repeat the validated test

From the repo root:

```powershell
.\run_test.ps1 -Input "fixtures\v0.1-vase\teste.glb" -Name "v0.1-vase-replay"
```

Equivalent raw command:

```powershell
& "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" --background --python ccstudio.py -- `
  --input "fixtures\v0.1-vase\teste.glb" `
  --template "fixtures\v0.1-vase\funcionasera.blend" `
  --output "output\v0.1-vase-replay"
```

Then:

1. Open `output\v0.1-vase-replay\report.json` — expect `success`
2. Import `output\v0.1-vase-replay\sims_ready.blend` in Sims 4 Studio
3. Import `output\v0.1-vase-replay\basecolor.png` as Diffuse
4. Compare against `fixtures\v0.1-vase\` if the live output was overwritten

## Run a new GLB (same pipeline, no code changes)

```powershell
.\run_test.ps1 -Input "caminho\para\objeto.glb" -Name "handle_object"
```

Writes under `output\handle_object\`:

- `sims_ready.blend`
- `basecolor.png`
- `report.json`
- `run.log`

Non-zero exit if `ccstudio.py` fails.

## Future cases (measure breaks only)

Place GLBs and run without adapting the script:

- A — handle or hollow: `fixtures/future/A_handle_or_hollow/input.glb`
- B — asymmetric: `fixtures/future/B_asymmetric/input.glb`
- C — short/wide: `fixtures/future/C_short_wide/input.glb`
