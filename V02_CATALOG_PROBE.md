# v0.2 catalog probe

This is the first differential test after the in-game PASS of `v02_identity_clone.package`.

## Package

- Input: `output/v02_identity_clone.package` (the placed, passing clone)
- Output: `output/v02_catalog_probe.package`
- Audit: `output/v02_catalog_probe_report.json`
- Rebuild: `python experiments/v02_catalog_probe.py`

The probe changes only:

1. Name and description entries in all 18 STBL locale resources.
2. The matching name and description key fields at OBJD offsets 8 and 12.

New catalog name: **CCStudio Catalog Probe**. The price remains §1,300. COBJ internal name and tuning, resource TGIs, mesh, texture, footprint, rig, slots, category, and all other payloads are unchanged. In particular, the earlier catalog spike's writes to OBJD offsets 16, 90, and 135 are not included.

## Programmatic audit

`PROGRAMMATIC_PASS`: 34 TGIs unchanged; only OBJD and 18 STBL payloads changed. DBPF output reopens successfully. The STBL and its FNV-1 key were also parsed independently with `@s4tk/models` and `@s4tk/hashing`.

Output SHA-256: `7c2e26fef29d80b4e07cd7282b73f455c503160a53f0b5afeccd166b0159d754`.

## In-game acceptance: PASS

Tested with only `v02_catalog_probe.package` active in `Mods/CCStudio`. The catalog search found **CCStudio Catalog Probe**. The screenshot showed a green placement ghost, and the user confirmed the vase could be placed. No placement failure was reported.

The name/description key and STBL edits do not reproduce the regression. The next controlled test isolates the verified price field at OBJD offset 16. The old catalog spike also wrote to OBJD offsets 90 and 135; those remain untested and are deliberately excluded from the next package.

Do not integrate this spike into `ccstudio.py` before the in-game result.
