# CC Studio — release candidate notes

**Product scope (current):**  
`GLB → sims_ready.blend + basecolor.png` ready for manual import in Sims 4 Studio.  
No automatic `.package`, no UI, no photo→3D.

**Entrypoint:** `ccstudio.ps1`  
**Engine:** `ccstudio.py` (unchanged for this step)  
**Tag baseline:** `v0.1.1-validated` (uniform contain-fit + explicit rotate)

---

## How to run

```powershell
cd C:\Users\Cliente-TechNew\Desktop\nussmone

.\ccstudio.ps1 -Input "caminho\objeto.glb"

# optional orientation (degrees, applied before fit)
.\ccstudio.ps1 -Input "caminho\objeto.glb" -RotateX 90
```

What the wrapper does:

1. Finds Blender 4.4.x under `C:\Program Files\Blender Foundation\`
2. Uses validated template `templates\decor_vase\template.blend` (fallback: `fixtures\v0.1-vase\funcionasera.blend`)
3. Writes a unique folder under `output\` (or `-Name` / `-Force`)
4. Runs `ccstudio.py` headless
5. Emits `sims_ready.blend`, `basecolor.png`, `report.json`, `run.log`
6. Prints a short PASS/FAIL summary (full Blender log stays in `run.log`)
7. Exit code ≠ 0 on failure
8. Refuses to overwrite an existing output folder unless `-Force` or interactive `y`

Optional overrides: `-Blender`, `-Template`, `-Name`, `-Force`.

---

## RC validation (this entrypoint)

Commands used:

```powershell
.\ccstudio.ps1 -Input "fixtures\v0.1-vase\teste.glb" -Name "rc_vaso" -Force

.\ccstudio.ps1 -Input "fixtures\future\A_handle_or_hollow\tmpfme2zl9i.glb" -Name "rc_A_handle_or_hollow" -Force

.\ccstudio.ps1 -Input "fixtures\future\B_asymmetric\model-1789699908959.glb" -Name "rc_B_asymmetric" -Force

.\ccstudio.ps1 -Input "fixtures\future\C_short_wide\model-1789699931683.glb" -Name "rc_C_short_wide" -RotateX 90 -Force
```

Results:

| Case | Rotate | Exit | report.json | Outputs |
|---|---|---|---|---|
| vaso | 0 0 0 | 0 | success | `output\rc_vaso\` |
| A_handle_or_hollow | 0 0 0 | 0 | success | `output\rc_A_handle_or_hollow\` |
| B_asymmetric | 0 0 0 | 0 | success | `output\rc_B_asymmetric\` |
| C_short_wide | **X=90** | 0 | success | `output\rc_C_short_wide\` |

All four **PASS** through `ccstudio.ps1`.

Next manual step (unchanged product flow): open each `sims_ready.blend` in Sims 4 Studio and import the matching `basecolor.png` as Diffuse.

---

## Known product limits (honest)

- One recipe: single-mesh GLB + this vase/decor template
- Orientation is **explicit** (`-Rotate*`), not inferred
- No `.package` generation in product scope
- `basecolor.png` may be JPEG bytes under a `.png` name (Blender save); Studio still accepts it as Diffuse import in prior tests
- Research spikes under `experiments\` / `V02_*.md` are **not** part of the shipping command

---

## Minimal project tree (product)

```text
nussmone/
├── ccstudio.ps1              # product entrypoint
├── ccstudio.py               # headless Blender pipeline
├── run_test.ps1              # older named test runner (still useful)
├── fixtures/
│   ├── README.md
│   ├── v0.1-vase/
│   │   ├── teste.glb
│   │   ├── funcionasera.blend
│   │   ├── sims_ready.blend
│   │   ├── basecolor.png
│   │   └── report.json
│   └── future/
│       ├── A_handle_or_hollow/   # + input GLB
│       ├── B_asymmetric/
│       └── C_short_wide/
├── VALIDATION.md
├── TEST_RESULTS.md
├── RELEASE_CANDIDATE_NOTES.md
└── output/                   # gitignored live runs
    ├── rc_vaso/
    ├── rc_A_handle_or_hollow/
    ├── rc_B_asymmetric/
    └── rc_C_short_wide/
```

Ignore for product use: `experiments/`, `V02_*.md`, web `index.html` leftovers in this repo, automatic package spikes.

---

## Stop line

Release-candidate entrypoint is ready when the four fixtures above PASS via `ccstudio.ps1` — done.
