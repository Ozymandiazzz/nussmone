# v0.2C — Donor provenance audit

**Trigger:** Manual test of “decor rebuild” still showed **Iluminação**, no ghost, immediate script popup.  
**Scope:** diagnosis only — **no patches**.  
**Packages:**

| Label | Path |
|---|---|
| **Decor donor** | `TheSims4Tool\NovoVasoTeste2.package` |
| **Rebuild** | `output\v02_decor_rebuild.package` |
| **Lamp donor** | `TheSims4Tool\Vaso.package` |
| **Lamp spike** | `output\v02_catalog_cobjfix.package` |

---

## 0) Mods folder check (first — and decisive)

Live Mods tree on this machine:

```text
Documents\Electronic Arts\The Sims 4\Mods\CCStudio\
  v02_catalog_cobjfix.package   ← LAMP spike (518 117 bytes)
  Vaso.package                   ← LAMP donor (1 772 485 bytes)
```

| Expected for the decor test | Present in Mods? | SHA256 prefix |
|---|---|---|
| `v02_decor_rebuild.package` | **NO** | (repo: `6E70B101189439E0…`) |
| `NovoVasoTeste2.package` | **NO** | (repo: `87FA5277C6BD5D86…`) |
| `v02_catalog_cobjfix.package` | **YES** — exact match to repo lamp spike | `D1C7E5DC377AD88D…` |
| `Vaso.package` | **YES** — exact match to lamp donor | `6A00BE0E4C8F24AE…` |

**Conclusion on the manual session:** the game was **not** loading the decorative rebuild. It was loading the **previous lamp package** (`v02_catalog_cobjfix`) plus the lamp donor. That alone explains:

- catalog category **Iluminação**
- same immediate script popup / no ghost
- search name still “CCStudio Test Mug” (lamp spike also reminted that name)

Re-test is invalid until Mods contains **only** `v02_decor_rebuild.package` (and optionally `NovoVasoTeste2` for coexistence), with **both** `v02_catalog_cobjfix.package` and `Vaso.package` removed.

---

## 1) Resource-by-resource provenance

Legend for **source**:

- **A** = derived from `NovoVasoTeste2` (content hash match, or same body after known remint edits)
- **B** = derived from lamp / old spike (`Vaso` / `v02_catalog_cobjfix`)
- **C** = produced by rebuild/remint (mesh, diffuse, STBL rewrite, instance remint, COBJ TGI fix)

| Resource | Rebuild i | Len | vs NovoVasoTeste2 | vs Vaso / lamp spike | Source |
|---|---|---|---|---|---|
| **OBJD** | `F14785768474249F` | **258** | same length; **248/258** bytes identical; only keys + `u32@16` + price byte differ | lamp OBJD is **282**; different shape | **A + C** (catalog key/price only) |
| **COBJ** | same as OBJD | 353 | tuning + **category head `0x0001C354`** identical; TGI block reminted | lamp head is **`0x00003A59`**, tuning `object_light_table` | **A + C** |
| **RIG** | `E207BDF84D7315CE` | 222 | **content SHA identical** | same SHA as Vaso too (shared bone blob) | **A** (payload); i reminted **C** |
| **SLOT** | same as RIG | 132 | **SHA identical** to NovoVaso | **≠** Vaso | **A** |
| **FTPT** | `DC97043EE60B35E9` | 161 | same length; SHA differs (embedded i reminted) | lamp FTPT len **86** | **A + C** |
| **LITE** | `07EEA0079BFB0114` | 228 | **SHA identical** to NovoVaso | **≠** Vaso | **A** (decorative donor still ships LITE bytes) |
| **MODL** | model i | 17256 | same len; SHA differs (embedded DST/model remint) | lamp MODL len **12220** | **A + C** |
| **MLOD** hi | model i | 285134 | replaced mug geometry | ≠ either donor mesh | **C** (mesh spike on **A** template) |
| **MLOD** LODs 1–4 | model i | donor sizes | SHA differs after u64 remint in payload | ≠ lamp sizes | **A + C** |
| **DST** diffuse | reminted | 1398224 | replaced mug Diffuse | ≠ | **C** |
| **DST** normal/spec | reminted | 87536 / 22000 | **SHA identical** to NovoVaso | ≠ Vaso | **A** |
| **STBL** ×18 | new bases | 74 | rewritten name/desc; bases split (known remint debt) | lamp STBL different | **C** |
| **THUM** | reminted | 68 | SHA differs (remint touch) | ≠ | **A shell + C** |

**Instance overlap:** rebuild ∩ lamp donor = **0**; rebuild ∩ lamp spike = **0**; rebuild ∩ NovoVasoTeste2 = **0** (full remint). Layout/type counts match NovoVaso (34 entries), not a mixed splice.

---

## 2) Field register (high-signal)

### COBJ

| Field | NovoVasoTeste2 | v02_decor_rebuild | Vaso / lamp spike |
|---|---|---|---|
| Internal name | `Midas_sculptTableMedium_…vase…` | `CCStudio_TestMug_…` | `Midas_lightTableQA_…` / mug remint |
| Tuning string | `prototype_RetailCompatible` | **same** | `object_light_table` |
| Catalog/category head `u32@rest+0` | **`0x0001C354`** | **`0x0001C354`** | **`0x00003A59`** |
| RIG / SLOT / MODL / FTPT refs | donor ids | reminted ids (COBJ fix) | lamp ids / lamp remint |
| Material variant string | `Set1-materialVariant` | same | same |

Tuning ≠ category: both differ independently. Rebuild keeps **decorative category head**, not the lamp head.

### OBJD

| Field | NovoVasoTeste2 | rebuild | lamp spike |
|---|---|---|---|
| Uncompressed size | **258** | **258** | **282** |
| nameKey @8 | `2C03EE43` | `D53CEE7A` (remint) | `D53CEE7A` (same hash of same name) |
| descKey @12 | `C62136A0` | `21479013` | `21479013` |
| u32@16 | `1300` | `10` (price patch side-effect) | `10` |
| f32@90 | `8.0` | `10.0` | `10.0` |
| Body after masking keys+price fields | — | **byte-identical to NovoVaso** | byte-identical to **Vaso** |

So OBJD of the rebuild is **NovoVasoTeste2 with catalog remint patches**, not the lamp OBJD.

### STBL (locale 0)

| | Name | Desc |
|---|---|---|
| NovoVasoTeste2 | `Vaso Ornamental Real\|M` | decorative blurb |
| rebuild | `CCStudio Test Mug` | `Generated by CC Studio` |
| Vaso | `Kyko` | luminária / jellyfish lamp story |
| lamp spike | `CCStudio Test Mug` | same remint strings |

---

## 3) Objective answers

### A) Is rebuild COBJ really from NovoVasoTeste2?

**YES.** Same tuning `prototype_RetailCompatible`, same category head `0x0001C354`, same TGI *types/groups* and material-variant tail shape; only name, length, and reminted instance fields differ. Lamp COBJ head is `0x00003A59` / `object_light_table` — **not** present in rebuild.

### B) Is rebuild OBJD really from NovoVasoTeste2?

**YES.** Length **258** (not lamp **282**). After zeroing reminted key/price bytes, payload is **identical** to NovoVaso. Masked rebuild ≠ masked lamp spike.

### C) What still matches the lamp donor?

Essentially **nothing catalog-semantic** in rebuild:

- Not COBJ category head  
- Not COBJ tuning  
- Not OBJD length/body  
- Not SLOT/LITE/DST normal-spec content  

Shared with lamp only where donors historically share assets (e.g. RIG content SHA happens to match Vaso too) or where remint used the **same display name** (same nameKey/descKey as lamp spike). That is not proof of lamp COBJ/OBJD reuse.

### D) Why did the item still appear under “Iluminação”?

**Because Mods still had the lamp spike installed**, not `v02_decor_rebuild`. The game was almost certainly showing `v02_catalog_cobjfix.package` (tuning `object_light_table`, category head `0x00003A59`).

Binary evidence: if the decor rebuild *had* been loaded, its COBJ category head would already differ from the lamp’s.

### E) Is NovoVasoTeste2 itself décor or lighting?

Binary/STBL evidence (no S4S UI run in this step):

- STBL name: **“Vaso Ornamental Real”** (decorative), not lamp lore  
- COBJ tuning: `prototype_RetailCompatible`  
- COBJ category head: `0x0001C354` ≠ lamp `0x00003A59`  
- Still contains a **LITE** resource (common on these S4S clones) — **not** the same as “catalog = Iluminação”

**In-game category of NovoVasoTeste2 alone was not verified this session** (it is not in Mods). Expect décor/sculpt-adjacent, not Iluminação — confirm by installing **only** NovoVasoTeste2 once Mods is cleaned.

---

## 4–5) Structured COBJ / OBJD diffs

### COBJ: NovoVasoTeste2 vs rebuild

| Region | Match? | Notes |
|---|---|---|
| Tuning string | yes | `prototype_RetailCompatible` |
| Category head `u32` | yes | `0x0001C354` |
| TGI type/group slots | yes | RIG/SLOT/MODL/FTPT |
| TGI instances | reminted | expected COBJ fix |
| Internal name | changed | remint |
| Tail after TGIs | mostly same; embedded DST ids reminted | expected |

### COBJ: rebuild vs lamp spike

| Region | Match? |
|---|---|
| Category head | **NO** (`1C354` vs `3A59`) |
| Tuning | **NO** |
| OBJD/COBJ length class | **NO** (rebuild OBJD 258 vs 282) |

### OBJD: NovoVasoTeste2 vs rebuild

Differing bytes only at:

- `8–15` nameKey / descKey  
- `16–17` (`1300` → `10`)  
- `92` (price f32@90 region)

Everything else identical → **real donor swap for OBJD**.

---

## Mandatory conclusion

1. **The decorative donor swap for COBJ/OBJD was REAL** in `output/v02_decor_rebuild.package`. The pipeline did **not** keep the lamp COBJ/OBJD carcass; it reminted NovoVasoTeste2’s catalog shell (tuning + category head + 258-byte OBJD).

2. **The manual FAIL does not invalidate that**, because **Mods never had the decor rebuild**. It still served `v02_catalog_cobjfix.package` (lamp) + `Vaso.package`.

3. **Do not patch OBJD yet.** First re-run acceptance with a clean Mods folder:

```text
REMOVE:  Mods\CCStudio\v02_catalog_cobjfix.package
REMOVE:  Mods\CCStudio\Vaso.package
COPY:    output\v02_decor_rebuild.package  → Mods\CCStudio\
OPTIONAL coexistence: NovoVasoTeste2.package
```

Then re-check: category, ghost, place.

4. Only if **that** clean test still lands in Iluminação / same popup does category/`0x0001C354` vs S4S décor become the next binary question — still without inventing OBJD hi/lo patches.

---

## Stop line

Provenance audit complete. No package changes applied. Next action is **Mods hygiene + retest**, not a new code fix.
