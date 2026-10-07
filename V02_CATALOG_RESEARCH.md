# v0.2C — Catalog identity research (read-only)

**Goal:** learn what makes a Build/Buy object a *new* catalog item vs an override of the donor.  
**Not product. No push. `ccstudio.py` untouched.**

Packages compared:

| Label | File | Role |
|---|---|---|
| **A** | `TheSims4Tool\Vaso.package` | Donor / template |
| **B** | `TheSims4Tool\NovoVasoTeste2.package` | S4S-saved standalone-style clone (vase) |
| **C** | `output\v02_texture_spike.package` | Our v0.2B mesh+diffuse spike |

Inventory tool: `experiments/v02_catalog_inventory.py` + `@s4tk/models` STBL dump.

---

## Resource map (identity / catalog)

All three packages share the **same type layout** (34 entries):

| Type | Tag | Role for catalog identity |
|---|---|---|
| `0x319E4F1D` | **OBJD** | Object definition / catalog product body (name keys, flags, categories, model refs) |
| `0xC0DB5AE7` | **COBJ** | Catalog wrapper: internal clone name + **tuning name** + TGI block |
| `0x220557DA` | **STBL** ×18 | Localized name + description strings (locale in high byte of instance) |
| `0x01661233` | MODL | Model root (shared instance with MLOD/LITE/FTPT) |
| `0x01D10F34` | MLOD | LODs (same model instance) |
| `0x00B2D882` | DST | Diffuse / Normal / Spec |
| `0xD382BF57` | FTPT | Footprint |
| `0xD3044521` | SLOT | Slots |
| `0x8EAF13DE` | RIG | Rig |
| `0x03B4C61D` | LITE | Light (present because donor is a lamp) |
| `0x81CA1A10` | THUM_META | Thumbnail helper |
| `0x0166038C` | NMAP | empty / unused in these files |

**Not present** as top-level resources in these clones: separate Tuning XML / SimData. Tuning is referenced **by name string inside COBJ** (e.g. `object_light_table`).

---

## Concrete diff: A vs B (what S4S changes for standalone)

### Instance IDs

| | A donor | B S4S standalone |
|---|---|---|
| OBJD instance | `B57A549C2C92F687` | `F13A5ECB24971854` **new** |
| COBJ instance | **same as OBJD** | **same as new OBJD** |
| MODL/MLOD/LITE/FTPT instance | `A325295480E2E835` | `072A47629547059E` **new** |
| DST instances | 3 donor IDs | 3 **new** IDs |
| STBL base (low 56 bits) | `D6DBE9F3` | `7222DC92` **new** |
| Locales (high byte) | same set | same set |
| **Shared instances A∩B** | | **0** |

S4S does **not** change one GUID. It remints **every** instance so the package cannot collide with the donor under Mods.

### Strings / catalog text (STBL locale 0 via `@s4tk/models`)

| | A / C (donor identity) | B (S4S) |
|---|---|---|
| Name key → value | `0xC66328E0` → `Kyko` | `0x2C03EE43` → `Vaso Ornamental Real\|M` |
| Desc key → value | `0xFE8A58A6` → lamp story (luminária) | `0xC62136A0` → vase blurb |

OBJD stores those keys as **u32 at offsets 8 and 12** (validated on A and B).

### COBJ semantics

| | A / C | B |
|---|---|---|
| Internal name | `Midas_lightTableQA_…_set1` | `Midas_sculptTableMedium_EP21ORNATEvase_…_set1` |
| Tuning string | **`object_light_table`** | **`prototype_RetailCompatible`** |

So a “real” S4S standalone vase clone also **retargets tuning** away from the lamp. Identity ≠ only STBL rename.

### C (our texture spike) vs A

| Check | Result |
|---|---|
| OBJD instance | **identical to donor** |
| COBJ instance / name / tuning | **identical to donor** |
| STBL base + strings | **identical to donor** (`Kyko` / lamp text) |
| Shared instances A∩C | **25** (everything) |
| Content changes | Diffuse DST + high MLOD only |

**Conclusion:** v0.2B package is still the donor catalog row with new mesh/texture → Mods **override**, not a new searchable item.

---

## Answers

### 1. What makes an object appear in the catalog?

Minimum observed set:

1. **OBJD** (`0x319E4F1D`) with category/flags and string keys  
2. **COBJ** (`0xC0DB5AE7`) with the **same instance** as OBJD  
3. **STBL** entries whose keys match OBJD name/desc keys  
4. Model chain reachable from OBJD/COBJ (MODL/MLOD/DST/…)  
5. Tuning name inside COBJ that the game accepts  

Search uses the STBL **name** string (e.g. `CCStudio Test Mug`).

### 2. What makes it coexist with the donor (not overwrite)?

**No shared DBPF instances** with the donor for catalog, strings, mesh, textures, footprint, slots, etc.

A vs B: `shared_count = 0`.  
A vs C: `shared_count = 25` → override.

Changing only an “object GUID” while keeping MODL/DST/STBL/OBJD instances is **not** enough.

### 3. Which instance IDs must be new?

From the S4S remint (A→B), **all of them**, grouped as:

- Catalog pair: OBJD + COBJ (shared new id)  
- Model group: MODL + all MLOD + LITE + FTPT (shared new id)  
- Each DST  
- RIG + SLOT (shared new id on donor; reminted together on B)  
- STBL base (locale byte preserved)  
- THUM_META  

### 4. Which references must be updated when IDs change?

- DBPF index TGI for every reminted resource  
- **Embedded u64 instance fields** inside payloads (esp. MLOD material DiffuseMap/NormalMap TGIs, COBJ TGI block, MODL links)  
- OBJD name/desc **keys** if STBL keys change  
- STBL instance bases (per locale)  

DST **pixel bytes** can stay identical; their **index instance** must still be new or they override the donor’s textures.

### 5. What does S4S change for Standalone / Create 3D Mesh?

Observed on B vs A:

- Full instance remint (0 shared)  
- New STBL base + new name/desc keys + new text  
- New COBJ internal name  
- **Tuning string changed** (`object_light_table` → `prototype_RetailCompatible`)  
- OBJD binary rewritten (size 282→258) with new keys / fields  
- New mesh/texture instances (content differs because it is a different object)

### 6. Can we inherit donor tuning/footprint and still have own identity?

**Identity / coexistence:** yes — if all *instances* are reminted, footprint/slot/tuning *content* can be copied.

**Semantics:** inheriting `object_light_table` keeps **lamp behavior** (light component present). S4S vase standalone moved to `prototype_RetailCompatible`.  

So: safe for “appears as its own catalog row”; **not** equivalent to a clean decor-only object until a later tuning spike (v0.2D+).

---

## Implication for v0.2C spike

Must, at minimum:

1. Remint **all** instances (S4S-grade)  
2. New STBL name/description keys + strings  
3. Patch OBJD keys (+ price)  
4. Rename COBJ internal name  
5. Keep mesh/diffuse payloads (remap embedded TGIs only)  
6. Document inherited `object_light_table` semantics  

Tooling: open-source `@s4tk/models` / `@s4tk/hashing` (MIT). No S4S source vendored.
