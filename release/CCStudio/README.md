# CC Studio CLI v0.1

Converts a GLB into a Sims-ready Blender file for manual import in Sims 4 Studio.

## Requirement

- **Blender 4.4.x** installed in the default Windows location  
  (`C:\Program Files\Blender Foundation\Blender 4.4\`)

## Basic command

From this folder:

```powershell
.\ccstudio.ps1 -Input "objeto.glb"
```

## Optional rotation

Apply orientation before fit (degrees):

```powershell
.\ccstudio.ps1 -Input "objeto.glb" -RotateX 90
.\ccstudio.ps1 -Input "objeto.glb" -RotateY 90
.\ccstudio.ps1 -Input "objeto.glb" -RotateZ 90
```

You can combine axes. Defaults are `0`.

## Generated files

Each run creates a unique folder under `output\`:

| File | Purpose |
|---|---|
| `sims_ready.blend` | Mesh fit into the decorative template — open in Sims 4 Studio |
| `basecolor.png` | Diffuse texture extracted from the GLB |
| `report.json` | Machine-readable PASS/FAIL summary |
| `run.log` | Full Blender console log |

Exit code is `0` on success, non-zero on failure. Existing output folders are not overwritten unless you confirm or pass `-Force`.

## Import in Sims 4 Studio

1. Open Sims 4 Studio → create or open a decorative object of the matching type.
2. Import **`sims_ready.blend`** as the mesh.
3. Import **`basecolor.png`** as the **Diffuse** / base color texture.
4. Save the package and test in-game.

No installer and no GUI — this is the CLI release candidate only.
