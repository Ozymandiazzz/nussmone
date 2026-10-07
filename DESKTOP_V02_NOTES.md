# CC Studio v0.2 Desktop Prototype — notes

**Goal:** thin Windows GUI over the frozen v0.1 CLI pipeline.  
**Motor:** `ccstudio.py` **unchanged**.  
**Tag baseline:** `v0.1-cli-rc`

---

## Structure

```text
app/
  main.py                 # python app/main.py
  __init__.py             # repo root helpers
  services/
    detect.py             # Blender 4.4.x + template discovery
    pipeline_runner.py    # calls Blender + ccstudio.py (no motor logic)
  ui/
    main_window.py        # PySide6 window
requirements-desktop.txt
```

The GUI never reimplements fit/decimate/UV/basecolor. It only:

1. detects Blender + template  
2. creates a unique `output/<name>/` folder  
3. runs `blender --background --python ccstudio.py -- …`  
4. reads `report.json` for PASS/FAIL  

Same contract as `ccstudio.ps1`.

---

## Dependencies

- Python 3.12+ (tested 3.12.10)
- Blender 4.4.x (tested 4.4.3)
- PySide6

```powershell
python -m pip install -r requirements-desktop.txt
```

---

## How to run

From the repo root:

```powershell
python app/main.py
```

Batch check (same `pipeline_runner` the GUI uses — no window):

```powershell
python app/main.py --batch-fixtures
```

### UI

- Drag/drop or browse a `.glb`
- Presets: Sem rotação / Girar X·Y·Z 90
- Manual Rotate X/Y/Z
- **Processar** (non-blocking `QThread`)
- Status PASS/FAIL + short log
- **Abrir pasta de saída**

No external PowerShell window; Blender console noise stays in `run.log`.

---

## Fixture results (via `pipeline_runner` / GUI path)

| Demo name | Fixture | Rotate | Output | Result |
|---|---|---|---|---|
| gui_vaso | `fixtures/v0.1-vase/teste.glb` | 0 0 0 | `output/gui_vaso/` | **PASS** |
| gui_caneca | `A_handle_or_hollow` | 0 0 0 | `output/gui_caneca/` | **PASS** |
| gui_assimetrico | `B_asymmetric` | 0 0 0 | `output/gui_assimetrico/` | **PASS** |
| gui_bowl | `C_short_wide` | **X=90** | `output/gui_bowl/` | **PASS** |

`RESULT: 4/4 PASS`  
GUI smoke: `MainWindow` constructs (`CC Studio v0.2 Desktop Prototype`).

Artifacts per run: `sims_ready.blend`, `basecolor.png`, `report.json`, `run.log`.

---

## Known limits

- Prototype only — **not** packaged as `.exe` yet
- No cancel mid-run (deferred)
- No 3D mesh preview inside the app (file name / path only)
- Single decor vase template (auto-detected)
- Still requires manual Sims 4 Studio Diffuse import
- No `.package`, photo→3D, login, cloud, updater, payment
- Overwrite avoided by unique/suffixed output folders (never silent clobber)

---

## Next natural step (not done)

**v0.2.1** — package as a Windows `.exe` (e.g. PyInstaller) so creators open the app without Python/PowerShell.
