# v0.2 mesh-only probe

This package starts from the **in-game passing** `v02_catalog_probe.package` and replaces only its highest-detail MLOD with the mug geometry from `output/A_handle_or_hollow_v011/sims_ready.blend`. It does not include the pending price or OBJD@90 probes, and it keeps the decorative vase's original textures.

Build with the existing private Blender/S4S-addon spike:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 4.4\blender.exe' --background --python experiments/v02_headless_mesh_spike.py -- --blend output/A_handle_or_hollow_v011/sims_ready.blend --template output/v02_catalog_probe.package --output output/mesh_probe/v02_mesh_probe.package
python experiments/v02_mesh_probe_audit.py
```

- Package: `output/mesh_probe/v02_mesh_probe.package`
- Export details: `output/mesh_probe/v02_mesh_spike_report.json`
- Differential audit: `output/mesh_probe/v02_mesh_probe_audit.json`

Programmatic audit: `PROGRAMMATIC_PASS`. The 34 TGIs are unchanged. Exactly one payload differs: `MLOD 01D10F34:00000000:F7BB289836AF6288`, increasing from 35,640 to 285,134 uncompressed bytes. All other stored resource bytes remain identical. COBJ references still resolve, and no donor IDs reappeared. The exported high-detail MLOD contains the mug geometry (5,999 triangles in the main mesh); the other LODs remain the original vase.

Output SHA-256: `6b3370f0f62ae89bdf13b14bff1086c23f654a620b31004010dd6197e0846431`.

This is **not staged in Mods** and has no in-game result. Test only after recording the price probe result. In Build/Buy search **CCStudio Catalog Probe**, select, observe the ghost, and place. The mesh may display the vase texture on the mug until the separate texture probe is tested. A placement PASS shows the high-detail MLOD replacement alone is not the instantiation regression.

The local Sims 4 Studio addon is used for a private technical spike and is not copied into this repo or product code.
