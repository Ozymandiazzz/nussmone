# v0.2C — S4S standalone golden diff

**No patches applied.** `ccstudio.py`, mesh, MLOD geometry, DST, UV, thumbnail, and UI were not modified.

## Result

**Package B was not created.** There is no second S4S standalone to diff against `output/v02_decor_rebuild.package`.

| | File | Status |
|---|---|---|
| A donor | `TheSims4Tool\NovoVasoTeste2.package` | opened in S4S |
| B golden | — | **not saved** |
| C CCStudio | `output/v02_decor_rebuild.package` | unchanged |

Machine notes: `output/v02_standalone_golden_diff.json` (`status: GOLDEN_NOT_GENERATED`).

### Why B does not exist

Sims 4 Studio **3.2.6.4 (Star)** was opened on this machine. Menus on the open donor package:

| Menu | What is actually there |
|---|---|
| File | Main Menu, Save, Save As, Exit |
| Tools | Extract Tuning, Game File Cruiser, Hash Generator, Create Empty Package, … |
| Tools → Modding | Renumber Rig and Slot, copy string tables, embed CAS resources, … |
| Content Management | Merge / Un-merge, Batch Fixes |

There is **no** “Create Standalone” for an object package that is already saved. Save As keeps the same instance IDs, so it is not a remint oracle.

The command that mints a new object package is on the **main screen**: Object → **Create 3D Mesh** (or Selective Clone), and it clones from the **EA catalog**, not from `NovoVasoTeste2.package`.

That catalog cannot be used as an oracle right now. `Documents\Sims 4 Studio\S4Studio_v3.6.sqlite` has **3** `Game` rows and **0** `ObjectContentMetadata` rows. The UI had been sitting on “Indexing The Sims 4 (SimulationDeltaBuild0) (100%)”. A fresh EA clone was not saved, so a wrong object was not written into the repo.

S4S is still open on the main window. No package was written by Studio in this step.

---

## What S4S does show for this donor

The donor **was** opened in the object editor. That file is already an S4S-authored package. The Catalog tab reads:

| S4S control | Value |
|---|---|
| Name | `Vaso Ornamental Real\|M` |
| Description | `Um vaso elegante e certamente bem caro.` |
| **Price** | **1300** |
| Styles | Vintage, Neorrenascentista\|M |
| Tooltip tags | Ambience Happy, EP 17: Heirloom |
| Tuning tab | `prototype_RetailCompatible` |
| Mesh | 828 vertices, 798 polygons (Phong + dropshadow) |

**Price 1300 is OBJD `u32` at offset 16** (`0x514`). It is **not** the float at offset 90. That float is **8.0** on the donor, and the Price box does not display 8.

Checked/unchecked state of the Tags tab (Function “Vase”, Lights, etc.) is not exposed as selection in UI Automation, so those flags are **not** claimed here.

---

## OBJD byte diff (A vs C)

Both resources are **258 bytes**. Differing offsets only: **8, 10, 11, 12, 13, 14, 15, 16, 17, 92**. Byte 9 matches by chance (`0xEE` in both name keys).

`S4S_standalone` is empty because B was not generated. `matches_S4S` is therefore unknown. `matches_donor` is the byte compare against the S4S-authored donor.

| offset | field_if_known | donor | S4S_standalone | CCStudio | matches_S4S? | suspected_role |
|---|---|---|---|---|---|---|
| 0 | header u32 | 26 (`0x1A`) | — | 26 | unknown | unchanged |
| 4 | header u32 | 11 (`0x0B`) | — | 11 | unknown | unchanged |
| 8 | nameKey | `0x2C03EE43` | — | `0xD53CEE7A` | unknown | STBL name key (expected remint) |
| 12 | descKey | `0xC62136A0` | — | `0x21479013` | unknown | STBL description key (expected remint) |
| **16** | **catalog price u32** | **1300** | — | **10** | **no, vs the open S4S Price box** | **S4S Price textbox. Spike wrote `--price` here.** |
| 20 | u32 | unchanged | — | same as donor | unknown | not touched |
| **90** | **f32** | **8.0** | — | **10.0** | **not the Price box** | **Spike assumed this was catalog price. S4S Price is offset 16.** |
| 135 | u32 | unchanged | — | same as donor | unknown | spike’s third price site did not fire |

The write is in `experiments/v02_catalog_spike.cjs`: float at 90, then `u32@16` if the existing value is `<= 100000`. The comment says NovoVaso stores price at offset 90. The live Price box contradicts that. Offset 16 is the price. Offset 90 is a different field that got overwritten anyway.

Header, length 258, and the other 248 bytes match the donor. This is not the lamp OBJD (282 bytes).

---

## COBJ (A vs C)

| | Donor (S4S file) | CCStudio |
|---|---|---|
| Length | 388 | 353 (shorter internal name) |
| Tuning | `prototype_RetailCompatible` | same |
| Category head `u32` | `0x0001C354` | **same** |
| Internal name | `Midas_sculptTableMedium_EP21ORNATEvase_…_set1` | `CCStudio_TestMug_…_set1` |
| RIG/SLOT/MODL/FTPT | donor instances | reminted instances (COBJ TGI fix) |

Tuning and category head already match the decorative donor. They are not the lamp head `0x00003A59` / `object_light_table`.

---

## Inventory (type / group / instances)

B’s instance column is empty. Full list is in the JSON (34 entries).

| type | group | instance donor | instance S4S | instance CCStudio | content vs donor |
|---|---|---|---|---|---|
| OBJD / COBJ `319E4F1D` / `C0DB5AE7` | `80000000` | `F13A5ECB24971854` | — | `F14785768474249F` | same OBJD body except keys/price; COBJ name+TGI remint |
| MODL / MLOD / LITE | `00000000` (+ LOD groups) | `072A47629547059E` | — | `07EEA0079BFB0114` | hi MLOD replaced (mug); LITE bytes identical to donor |
| RIG / SLOT | `00000000` | `E27844EF7D505A41` | — | `E207BDF84D7315CE` | RIG and SLOT payloads identical to donor |
| FTPT | `80000000` | `DC95702B704D5B01` | — | `DC97043EE60B35E9` | same length; embedded ids reminted |
| DST diffuse | `80000000` | `B2FB5984DC8F5D06` | — | `B27248858F17EA75` | mug diffuse, not donor bytes |
| DST normal / spec | `80000000` | donor ids | — | reminted | payloads identical to donor |
| STBL ×18 | `80000000` | one base `7222DC92` | — | **18 different bases** | strings replaced; shared-base layout not reproduced |
| THUM | `80000000` | `F3E61AE402E31F71` | — | `F3738F7D1F5D2956` | reminted |

No index instance is shared with the donor. Internal COBJ refs point at the reminted RIG/SLOT/MODL/FTPT, not at the donor ids.

---

## First relevant difference

Against a **second** S4S remint: **unknown** — that file does not exist.

Against the S4S-authored donor that Studio is editing, ignoring expected identity edits (name, description, new instances, mug mesh, mug diffuse):

1. **OBJD offset 16:** catalog price **1300 → 10**. This is the field the S4S Price box shows.
2. **OBJD offset 90:** float **8.0 → 10.0**. The Price box does not use this field. The spike wrote it because of a wrong comment.
3. **STBL:** donor keeps one base for all locales (`7222DC92`). The remint issues 18 independent bases. S4S did not do that on this donor.

COBJ tuning and category head are already the donor’s. They are not the remaining lamp marker.

---

## Stop

No correction was applied. Next golden file, if you want the missing column filled, has to be a package **S4S itself saves** after the catalog index actually contains objects (Object → Create 3D Mesh of this vase, no mesh import), or an explicit remint command if a newer Studio build has one. This 3.2.6.4 build does not remint an open package from the menus above.
