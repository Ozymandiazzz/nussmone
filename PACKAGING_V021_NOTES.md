# CC Studio v0.2.1 — Windows packaging notes

**Goal:** double-clickable `CCStudio.exe` over the frozen v0.1 motor.  
**Motor:** `ccstudio.py` **unchanged**.  
**UI logic:** only path/runtime handling for frozen vs. repo.

---

## Build command

From the repo root:

```powershell
.\build_desktop.ps1
```

Equivalent:

```powershell
python -m pip install -r requirements-desktop.txt pyinstaller
python -m PyInstaller --noconfirm --clean CCStudio.spec
```

Output:

```text
dist/CCStudio/
  CCStudio.exe
  _internal/
    ccstudio.py
    templates/decor_vase/template.blend
    … (Python + PySide6 runtime)
```

---

## Size

| Item | Size |
|---|---|
| `dist/CCStudio/` (full onedir) | **~110.7 MB** (116 061 502 bytes) |
| `CCStudio.exe` (launcher) | ~1.7 MB |

Requires **Blender 4.4.x installed separately** (not bundled).

---

## Included files (product)

- `CCStudio.exe` — windowed (`console=False`), PySide6 GUI
- `_internal/ccstudio.py` — frozen motor script (Blender `--python` target)
- `_internal/templates/decor_vase/template.blend` — validated decor template
- PySide6 / Python runtime (QtWidgets/Gui/Core only — lean collect)

Not included: fixtures, demo shots, research spikes, installer, updater.

---

## Runtime path handling

| What | Dev (`python app/main.py`) | Packaged (`.exe`) |
|---|---|---|
| Resources | repo root | `sys._MEIPASS` (`_internal/`) |
| Template | `templates/decor_vase/…` (+ fixtures fallback) | bundled template (optional override next to `.exe`) |
| Motor | `./ccstudio.py` | `_internal/ccstudio.py` |
| Output | `./output/` | **`%USERPROFILE%\Documents\CCStudio\output\`** |
| Blender | external 4.4.x under Program Files | same external detection |

Environment failures (missing Blender / template / motor) surface in the GUI status + log panel.

Unique output folders; never silent overwrite (suffix `_2`, `_3`, …).

---

## Validation (this build)

1. Clean rebuild via `build_desktop.ps1` — OK  
2. Double-click / `Start-Process dist\CCStudio\CCStudio.exe` — GUI started  
3. Four fixtures via the packaged entrypoint (same `pipeline_runner` as GUI):

```powershell
.\dist\CCStudio\CCStudio.exe --batch-fixtures --fixtures-root "C:\Users\Cliente-TechNew\Desktop\nussmone"
```

| Case | Rotate | Output | Result |
|---|---|---|---|
| exe_vaso | 0 0 0 | `Documents\CCStudio\output\exe_vaso\` | **PASS** |
| exe_caneca | 0 0 0 | `…\exe_caneca\` | **PASS** |
| exe_assimetrico | 0 0 0 | `…\exe_assimetrico\` | **PASS** |
| exe_bowl | **X=90** | `…\exe_bowl\` | **PASS** |

**RESULT: 4/4 PASS** (artifacts: `sims_ready.blend`, `basecolor.png`, `report.json`, `run.log`)

---

## How to use (end user)

1. Install **Blender 4.4.x**  
2. Copy/keep the whole `dist\CCStudio\` folder (exe + `_internal`)  
3. Double-click `CCStudio.exe`  
4. Drop a `.glb` → set rotation if needed → **Processar**  
5. Open `Documents\CCStudio\output\<run>\` → import blend + Diffuse in Sims 4 Studio  

---

## Known limits

- Onedir only — keep `_internal` beside the exe (not a single-file zip of just the exe)
- No installer / Start Menu shortcut / auto-update
- Still needs Blender 4.4.x on the machine
- Still manual S4S Diffuse + package step
- No photo→3D, no `.package` automation, no multi-template
- Windowed exe: `--batch-fixtures` is for validation (console attach best-effort); GUI is the product path
- Bundle ~111 MB (Qt lean); first fat `collect_all` build was ~655 MB and was discarded
