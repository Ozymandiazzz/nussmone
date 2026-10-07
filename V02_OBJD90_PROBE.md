# v0.2 OBJD offset 90 probe

The earlier catalog script wrote the requested price as a float at OBJD offset 90. In the decorative vase that successfully places in game, this field contains `8.0` while the known catalog price at OBJD offset 16 is `1300`. The meaning of offset 90 is not established.

This probe starts from the **in-game passing price package**. It changes only OBJD bytes 90–93 from `f32 8.0` to `f32 10.0`.

- Build: `python experiments/v02_objd90_probe.py`
- Output: `output/v02_objd90_probe.package`
- Audit: `output/v02_objd90_probe_report.json`
- Catalog name remains **CCStudio Catalog Probe**; price remains §10.

Programmatic status: `PROGRAMMATIC_PASS`. All TGIs and all other resource payloads remain unchanged. Test it with only this package active in Mods after restarting the game.

Output SHA-256: `41500435b681c4d773fe7ba5f10f067cc697c5f102321dad527fe4fdc3c712fa`.

An in-game PASS would show this unexplained write is not sufficient to cause the placement failure. An in-game FAIL would identify it as the first regression-producing change in the old catalog path.
