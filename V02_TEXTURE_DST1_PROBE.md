# v0.2 donor-compatible Diffuse probe

The four-package batch exposed a game crash when browsing `CCStudio 04 Texture` on 2026-10-03. Two new `lastCrash` files have the same category and stack prefix. No new LastException was present. The supplied screenshot shows a red-X thumbnail for `CCStudio 02 Field90`; it does not establish the rendering state of item 04. Results for the other batch items were not reported, so batch coexistence is not yet validated.

The original vase Diffuse is **DST1, 256×256, 9 mipmaps, 43,832 bytes**, stored with zlib compression. The earlier texture spike replaced it with **DST5, 1024×1024, 9 mipmaps, 1,398,224 bytes**, uncompressed. The crash does not prove which difference caused it. This probe removes all four format/layout differences at once while changing only the image blocks.

Build:

```powershell
python experiments/v02_texture_dst1_probe.py
```

- Input: the independently passing `output/v02_catalog_probe.package`
- Image: `output/A_handle_or_hollow_v011/basecolor.png` (JPEG data despite extension)
- Output: `output/texture_dst1_probe/v02_texture_dst1_probe.package`
- Report: `output/texture_dst1_probe/v02_texture_dst1_probe_report.json`

The encoder resizes the image to the donor's 256×256 and produces nine DXT1 mip levels, then shuffles them into DST1. It copies the donor DDS header byte for byte, preserves DBPF compression style, and changes only the Diffuse resource. The generated DST1 was decoded back to a 256×256 bitmap by `@s4tk/images` during verification. Programmatic status: **PASS**.

The mug atlas on the vase geometry will look mismatched; that visual mismatch is expected in this texture-only isolate. The acceptance check is whether selecting and placing the object crashes the game. The source image itself is a valid mug UV atlas.

The crashed batch texture package was moved out of Mods into `output/mods_quarantine_identity_test/texture_batch_crash.package` without modification.
The game's `localthumbcache.package` was also moved to `output/mods_quarantine_identity_test/localthumbcache_20261003.package` so the next launch regenerates catalog thumbnails; it was not deleted.

## In-game result

The user reported that this isolated package worked and supplied screenshots showing `CCStudio Catalog Probe` in the catalog and placed on a countertop. No crash was reported in that run. The black/beige pattern comes from the **mug fixture's UV atlas** applied to the decorative vase mesh; it is the expected visual mismatch for this isolate, not evidence of a missing texture. The image source is `output/A_handle_or_hollow_v011/basecolor.png`.
