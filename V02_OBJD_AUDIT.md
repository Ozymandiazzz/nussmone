# v0.2C — OBJD audit (read-only)

**Context:** After COBJ TGI fix, place still fails **immediately** with script popup and **no ghost/outline**. That ranks as **instantiate / definition**, not footprint.

**No fixes applied.** No mesh/DST/MLOD/`ccstudio.py`/UI changes.  
JSON: `output/v02_objd_audit.json`

---

## Failure-mode ranking (updated)

| Rank | Suspect | Verdict in this audit |
|---|---|---|
| **1** | **Tuning / definition path (`object_light_table`)** | **Primary.** Our package still inherits light-table tuning via COBJ. Decorative S4S clones use `prototype_RetailCompatible`. Immediate popup with no ghost fits definition/script instantiate, not FTPT. |
| **2** | **OBJD field edits we made (not hi/lo remint)** | **Secondary.** OBJD has **zero** stale donor MODL/RIG/SLOT/FTPT instance refs (LE u64 or hi/lo pairs). But we rewrote keys + **u32@16 (1→10)** + f32@90 — possibly corrupting non-price fields. S4S decorative OBJD is also **shorter** (258/246 vs our 282) → S4S rewrites OBJD more deeply than our remint. |
| **3** | SLOT/RIG linkage | Possible via definition components; COBJ now points at reminted RIG/SLOT. No OBJD-embedded instance orphans found. |
| **4** | FTPT | **Downgraded.** No ghost/red outline ⇒ failure before footprint validation. |
| **5** | STBL 18-base split | Still a defect; search works → unlikely sole cause of instant instantiate popup. |

---

## A) Decorative donor recommendation

Local packages under `TheSims4Tool\`:

| Package | COBJ tuning | LITE resource present? |
|---|---|---|
| `Vaso.package` (current light donor) | **`object_light_table`** | yes |
| `NovoVasoTeste2.package` | **`prototype_RetailCompatible`** | yes* |
| `tigela.package` | **`prototype_RetailCompatible`** | yes* |
| `23456.package` / `testenovo.package` | `prototype_RetailCompatible` | yes* |

\*Every inspected S4S clone still **contains a LITE-typed resource**. “Decorative” here means **COBJ tuning ≠ `object_light_table`**, not “no LITE bytes”.

**Prefer next rebuild template:** `NovoVasoTeste2.package` or `tigela.package`  
**Avoid for instantiate tests:** `Vaso.package` / `object_light_table`

---

## B) OBJD read-only findings

### Packages compared

| Label | File | OBJD len | Tuning |
|---|---|---|---|
| Light donor | `Vaso.package` | 282 | `object_light_table` |
| Our (post COBJ fix) | `v02_catalog_cobjfix.package` | 282 | `object_light_table` (unchanged) |
| S4S decor vase | `NovoVasoTeste2.package` | **258** | `prototype_RetailCompatible` |
| S4S decor bowl | `tigela.package` | **246** | `prototype_RetailCompatible` |

### Instance refs inside OBJD?

| Check | Our cobjfix OBJD |
|---|---|
| LE `u64` still naming **donor-only** instances | **none** |
| hi/lo `u32` pairs naming donor-only instances | **none** |
| Contains reminted MODL/RIG instances | **no** (OBJD body does not embed them) |
| Resource-type markers (MODL/FTPT/…) as u32 | **none** in light or decor OBJDs |

**Conclusion:** Unlike COBJ, **OBJD does not need the same hi/lo TGI remint** for MODL/FTPT/SLOT/RIG on this layout. That bug class is **not** reproduced inside OBJD.

### What *did* change in our OBJD (only 12 bytes vs light donor)

| Offset | Donor | Ours | Likely meaning |
|---|---|---|---|
| 8–11 | name key `C66328E0` | `D53CEE7A` | intentional STBL name key |
| 12–15 | desc key `FE8A58A6` | `21479013` | intentional STBL desc key |
| **16** | **`1`** | **`10`** | **price patch side-effect — field unknown; S4S decor has `1300` (`0x514`)** |
| 90–93 | (bytes) | f32 **10.0** | price write at S4S-vase offset |

So OBJD risk is **not orphan instance remint**, but:

1. still bound to **light-table definition** via COBJ tuning, and/or  
2. **unsafe scalar patches** (especially **u32@16**), and/or  
3. never receiving the **S4S-style OBJD rewrite** (length 282→258/246 on decor clones).

### S4S standalone contrast

For decorative clones, S4S changes more than identity keys:

- new OBJD instance  
- **shorter OBJD payload**  
- COBJ tuning → `prototype_RetailCompatible`  
- full internal TGI remint (already seen for COBJ)

Our pipeline kept light-table OBJD **shape** (282 bytes) and light-table tuning.

---

## Smallest fix possible (proposal only — not applied)

1. **Rebuild** mesh+diffuse+catalog remint using **`NovoVasoTeste2.package` or `tigela.package`** as template (decor tuning).  
2. Re-apply **COBJ hi/lo TGI rewrite** (Phase A) on that new package.  
3. On OBJD:  
   - keep name/desc key patches  
   - **do not invent price at u32@16** until that field is identified against S4S of the **same** donor  
   - byte-diff OBJD vs S4S standalone of that donor; only then patch missing structural fields  
4. If still: instant script popup / no ghost → next is **STBL base unify**, then SLOT — **not** FTPT-first.

---

## Stop line

Read-only audit only. Next experimental step requires an explicit go-ahead to **rebuild on a decorative donor** (not a broad remint of OBJD hi/lo — there is nothing of that form to fix in OBJD today).
