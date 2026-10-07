# v0.2 texture-only probe

This package starts from the **in-game passing** `v02_catalog_probe.package` and replaces only the Diffuse DST with the mug's basecolor. It does not include the pending price or OBJD@90 probes; mesh remains the original decorative vase.

Build:

```powershell
python experiments/v02_texture_spike.py --package output/v02_catalog_probe.package --png output/A_handle_or_hollow_v011/basecolor.png --output output/texture_probe/v02_texture_probe.package --diffuse-i 0xE85CC651F486CD25
python experiments/v02_texture_probe_audit.py
```

- Package: `output/texture_probe/v02_texture_probe.package`
- Encoder details: `output/texture_probe/v02_texture_spike_report.json`
- Differential audit: `output/texture_probe/v02_texture_probe_audit.json`

The basecolor file has JPEG bytes despite its `.png` name, so the existing spike converts it to PNG before `@s4tk/images` encodes DST5. Programmatic audit: `PROGRAMMATIC_PASS`. All 34 TGIs are unchanged, and exactly one resource payload differs: `DST 00B2D882:80000000:E85CC651F486CD25`, increasing from 43,832 to 1,398,224 bytes. Every other stored resource byte remains identical.

Output SHA-256: `a1608da4c354701cf204174d758947aef932b2e68091435a69ef6b92d35defc0`.

This is **not staged in Mods** and has no in-game result. Test separately after recording the price probe result. Search **CCStudio Catalog Probe**, select, observe the ghost, and place. The vase will carry the mug's texture; visual alignment is not the acceptance criterion for this isolate. A placement PASS shows Diffuse replacement alone is not the instantiation regression.
