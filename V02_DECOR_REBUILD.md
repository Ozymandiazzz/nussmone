# v0.2C — Decorative donor rebuild

**Goal:** eliminate `object_light_table` from the placement path by rebuilding the mug standalone on a decorative donor (`prototype_RetailCompatible`), using only the already-validated pipeline (mesh → Diffuse → remint → COBJ TGI fix). **No new OBJD structural patches.**

**Output:** `output/v02_decor_rebuild.package`  
**Donor:** `TheSims4Tool\NovoVasoTeste2.package`  
**Mug inputs:** `output/A_handle_or_hollow_v011/sims_ready.blend` + `basecolor.png`

Untouched: `ccstudio.py`, UI, mesh/DST exporter product code.

---

## Pre-flight (donor snapshot)

| Field | Value |
|---|---|
| COBJ tuning | **`prototype_RetailCompatible`** (not `object_light_table`) |
| OBJD size | **258** bytes uncompressed |
| COBJ size | **388** bytes uncompressed |
| OBJD/COBJ instance | `F13A5ECB24971854` |
| Entries | 34 (26 unique instances) |
| Layout | STBL×18, RIG, SLOT, DST×3, MLOD×5, LITE (`03B4C61D`), MODL, FTPT, COBJ, OBJD, THUM (`81CA1A10`) |
| LITE present? | yes (resource exists) — but **tuning is not light-table** |
| Diffuse TGI used | `00B2D882:80000000:B2FB5984DC8F5D06` (~43 KB; primary color map per prior research / size class) |

### Resources / IDs reminted (donor → rebuild)

| Kind | Donor instance | Rebuild instance |
|---|---|---|
| OBJD / COBJ | `F13A5ECB24971854` | `F14785768474249F` |
| Model group (MODL/MLOD/LITE) | `072A47629547059E` | `07EEA0079BFB0114` |
| RIG / SLOT | `E27844EF7D505A41` | `E207BDF84D7315CE` |
| FTPT | `DC95702B704D5B01` | `DC97043EE60B35E9` |
| Diffuse DST | `B2FB5984DC8F5D06` | `B27248858F17EA75` |
| Normal DST | `A39BA409748D8424` | `A39FD4BE3296379B` |
| Spec DST | `EA837D2267CD09B5` | `EA1BBB1E8D7ABE07` |
| THUM | `F3E61AE402E31F71` | `F3738F7D1F5D2956` |
| STBL×18 | shared base `7222DC92` | **18 distinct bases** (known remint debt; unchanged this step) |

Full map size: **26** unique instances (catalog report `remap_size`).

---

## Pipeline executed

| Step | Script | Input → Output | Result |
|---|---|---|---|
| 1 Mesh | `v02_headless_mesh_spike.py` | NovoVasoTeste2 + mug blend → `v02_decor_mesh.package` | PASS — hi MLOD replaced (`35640` → `285134` bytes) |
| 2 Diffuse | `v02_texture_spike.py` | mesh pkg + mug basecolor → `v02_decor_texture.package` | PASS — Diffuse replaced (`43832` → `1398224` DST5) |
| 3 Remint | `v02_catalog_spike.py` / `.cjs` | texture pkg → `v02_decor_catalog.package` | PASS — name `CCStudio Test Mug`, price 10 |
| 4 COBJ TGI | `v02_cobj_fix.py` | catalog → **`v02_decor_rebuild.package`** | PASS — 4 hi/lo orphans rewritten, 0 remain |

### What was **not** done

- No new OBJD structural patches (no `u32@16` experiments, no shape edits beyond existing catalog key/price writes).
- No tuning rewrite — **inherited** `prototype_RetailCompatible` from donor.
- No STBL base unification.
- No SLOT/RIG content edits.

### COBJ internal TGI fix (this rebuild)

| Ref | Before (donor orphan) | After (reminted) |
|---|---|---|
| RIG | `E27844EF7D505A41` | `E207BDF84D7315CE` |
| SLOT | `E27844EF7D505A41` | `E207BDF84D7315CE` |
| MODL | `072A47629547059E` | `07EEA0079BFB0114` |
| FTPT | `DC95702B704D5B01` | `DC97043EE60B35E9` |

After fix: orphan count **0**. DST/MLOD content hashes unchanged by COBJ step. OBJD instance unchanged by COBJ step.

Final package:

| | |
|---|---|
| Path | `output/v02_decor_rebuild.package` |
| Size | 550 766 bytes |
| OBJD/COBJ i | `F14785768474249F` |
| OBJD mem | **258** (same as donor decor) |
| COBJ tuning | **`prototype_RetailCompatible`** |
| Search name (STBL) | `CCStudio Test Mug` |
| Catalog nameKey / descKey | `0xd53cee7a` / `0x21479013` |

Reports: `output/v02_decor_catalog_report.json`, `output/v02_decor_cobj_fix_report.json`.

---

## Manual acceptance (you)

Install **only** `output/v02_decor_rebuild.package` (and optionally keep donor out of Mods to test coexistence separately).

| Check | Expected |
|---|---|
| Search | appears as **CCStudio Test Mug** |
| Coexistence | can sit next to donor package without crashing catalog |
| Select | **no** immediate script popup |
| Ghost | appears |
| Place | object places |
| Visual | mug mesh + mug diffuse |

### Interpretation

| Result | Conclusion |
|---|---|
| **PASS** | Blocker was the **lamp donor / `object_light_table` definition path**. Decor donor + existing remint + COBJ TGI fix is enough for place. |
| **FAIL** | Re-open OBJD as a real suspect: compare this package’s OBJD/COBJ to an S4S standalone from the **same** decorative donor, focusing on structural scalars (`u32@16`, size 282 vs 258/246). Still do **not** apply lamp-style OBJD hi/lo remends (none exist). |

---

## Stop line

Rebuild package and this note are ready. Waiting on **manual place test** before any further OBJD or STBL work.
