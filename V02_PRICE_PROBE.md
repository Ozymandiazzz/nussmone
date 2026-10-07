# v0.2 price probe

This is the next differential test after the in-game PASS of `v02_catalog_probe.package`.

- Input: `output/v02_catalog_probe.package`
- Output: `output/v02_price_probe.package`
- Audit: `output/v02_price_probe_report.json`
- Rebuild: `python experiments/v02_price_probe.py`

Only the four bytes at OBJD offset 16 change: price **§1,300 → §10**. All 34 resource TGIs remain unchanged; all other resource payloads are byte-identical to the passing catalog probe. Name, description, COBJ, mesh, texture, tuning, category, and internal references are unchanged. The older catalog script's writes at OBJD offsets 90 and 135 are excluded.

Programmatic audit: `PROGRAMMATIC_PASS`; the output DBPF reopens, and exactly one OBJD payload differs at the expected field. Output SHA-256: `204c96c43a8eb048de863fc248a727ab36ac32c4790ffe0b67f2212302a6d7e4`.

## In-game acceptance: PASS

The user tested with `v02_price_probe.package` active. The screenshot shows **CCStudio Catalog Probe** at **§10**, and the user confirmed the vase could be placed in the room without problems. No LastException check was reported for this run.

The known price field at OBJD offset 16 does not reproduce the instantiation failure. Next, test the old script's unexplained write at OBJD offset 90 independently. The old script's conditional write at offset 135 did not apply to this donor because the original u32 there exceeds its threshold.
