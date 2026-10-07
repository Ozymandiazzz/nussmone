# v0.2 orientation fix spike (private)

**Not product. `ccstudio.py` unchanged. No S4Studio code copied into repo.**

## Bug

`output/v02_mesh_spike.package` opened in S4S and in-game with mesh **inverted / upside down**. Same in S4S preview → bug in exported MLOD, not game placement.

## Cause

The first headless monkeypatch of `rotate_obj` was **wrong**, not a no-op.

`collect_mesh_data` (local addon, inspected only) does:

```text
transform_apply(loc/rot/scale)
rotate_obj(-math.pi / 2.0, 'X')    # once per mesh with cut
transform_apply(rotation=True)
```

During `save_lod` on our vase blend that is **two calls** (cut `0` and cut `1`).

### Original `rotate_obj` (Blender 4.4)

Observed in `%APPDATA%\...\s4studio\blender\__init__.py`:

- Resolves a `VIEW_3D` area (fails in naive `--background` without override).
- Normalizes `'-'` prefix on axis (negates `amount`).
- Blender **≥ 4.0**: `bpy.ops.transform.rotate(value=-amount, orient_axis=axis)` on the **active object**.
- Blender **≥ 5.0** only: extra `amount *= -1` before the op.
- Does **not** edit mesh data directly; mutates **object transform**, then `transform_apply(rotation=True)` bakes it into the mesh.

For `rotate_obj(-π/2, 'X')` on 4.4.3:

| Parameter | Value |
|---|---|
| `amount` | `-π/2` |
| op `value` | `-amount` = `+π/2` |
| Effective rotation | **`-90°` about global X** (verified in-process) |

### Broken monkeypatch

We used `rotation_euler.rotate(Euler(+π/2,0,0))` after `rot = -amount`. That does **not** match the operator: probe showed `euler.rotate` left identity wrong, while `bpy.ops.transform.rotate(value=+π/2, X)` yields euler X = `-π/2`.

Exported mesh 1 bounds with broken patch (from first spike log):

```text
Y: min -0.656  max -0.061   ← negative band (inverted vs template)
Z: min -0.035  max  0.344
```

Template MLOD mesh 1 before export:

```text
Y: min  0.062  max  0.653
Z: min -0.341  max  0.034
```

## Headless equivalent (our code, not copied)

In `experiments/v02_headless_mesh_spike.py`:

```python
def rotate_obj_headless(amount, axis):
    # after optional '-' prefix on axis (same as original)
    if bpy.app.version >= (5, 0, 0):
        amount *= -1
    R = Matrix.Rotation(amount, 4, axis)   # note: amount, NOT -amount
    obj.matrix_world = R @ obj.matrix_world
```

Verified on Blender 4.4.3: `Matrix.Rotation(-π/2, 4, 'X') @ I` matches `bpy.ops.transform.rotate(value=+π/2, orient_axis='X')`.

**Not** used: `ccstudio.py --rotate-*` (explicit user orientation stays separate).

## Regenerated package

```powershell
cd C:\Users\Cliente-TechNew\Desktop\nussmone

& "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" --background --python "experiments\v02_headless_mesh_spike.py" -- `
  --blend "fixtures\v0.1-vase\sims_ready.blend" `
  --template "C:\Users\Cliente-TechNew\Desktop\TheSims4Tool\Vaso.package" `
  --output "output\v02_mesh_spike_orientationfix.package"
```

Log: `output\v02_orientationfix_run.log` (exit 0)

Output: `output/v02_mesh_spike_orientationfix.package`  
Report: `output/v02_mesh_spike_report.json`

Replaced TGI (unchanged): `01D10F34:00000000:A325295480E2E835`

## MLOD comparison (high-detail MLOD, mesh index 1)

| Metric | Template MLOD (before export) | Broken spike | Orientation fix |
|---|---|---|---|
| Vertices | 5770 | 5984 | 5984 |
| Triangles | 5759 | 6000 | 6000 |
| Bbox Y min | **+0.062** | **-0.656** | **+0.061** |
| Bbox Y max | **+0.653** | **-0.061** | **+0.656** |
| Bbox Z min | -0.341 | -0.035 | -0.344 |
| Bbox Z max | +0.034 | +0.344 | +0.035 |

Mesh 0 (cut 0, 4 verts): unchanged bounds.

After the fix, exported mesh 1 **Y/Z axis orientation matches the template MLOD** (positive Y “up” band restored). Vertex/triangle counts still reflect our decimated blend (5984 / 6000), not the EA template mesh.

## Visual validation

**Pending:** open `output/v02_mesh_spike_orientationfix.package` in Sims 4 Studio and confirm upright preview + in-game placement. Bounds evidence suggests the inversion is fixed; S4S preview is the acceptance check.

## Scope not touched

Texture/DST, OBJD, catalog, footprint, other LODs, `ccstudio.py`, `--rotate-*`.

## Proprietary files

Only local import from AppData addon path. No vendor modules added to git.
