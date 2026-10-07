# v0.2C — Reference audit (placement failure)

**Scope:** diagnosis only. No remint rewrite, no mesh/DST/MLOD/UV/`ccstudio.py` changes.  
**Input:** `Vaso.package` (donor) vs `output/v02_catalog_spike.package`  
**Control:** `NovoVasoTeste2.package` (S4S standalone)  
**Machine JSON:** `output/v02_reference_audit.json`

---

## lastException (confirmed)

```
TypeError: 'NoneType' object is not iterable
  c_api_create_object
  → create_object → create_script_object
  → definition.instantiate
  → game_object / client_object_mixin / reservation_mixin / script_object
  → base_object.__init__  (line 84)
```

| Arg | Value | Meaning |
|---|---|---|
| arg0 | `0524172EC4E9144A` | definition id passed into create (not proven = light tuning alone) |
| arg1 | `B54973A7C47B7546` | **matches spike OBJD/COBJ instance** |

Catalog appearance works; crash is on **structural instantiate**. Treat as **object definition / reference graph** failure until proven otherwise. Tuning string `object_light_table` is still inherited, but is **not** sufficient evidence as the sole root cause.

---

## Remap graph (index TGIs)

Remint assigned new instances for all 25 unique IDs (OBJD/COBJ pair, model group, DST×3, RIG/SLOT, STBL×18, THUM).  
Full old→new map: see `output/v02_reference_audit.json` → `remap_graph`.

Important: **index remint ≠ internal ref rewrite**. Several payloads still name **donor** instances.

---

## Critical defects found

### 1) COBJ internal TGI block still points at donor (first orphan)

COBJ body (after name/tuning) stores TGIs as:

`code=4 | instance_hi u32 | instance_lo u32 | type u32 LE | group u32`

The catalog spike remint only walked **little-endian u64** byte patterns. It **did not** rewrite this hi/lo encoding.

| COBJ internal ref | Spike still has | Spike index actually has |
|---|---|---|
| RIG `8EAF13DE:0:792BF62E1D08E575` | **donor instance** | reminted RIG `79F06CAB65BD6BE6` |
| SLOT `D3044521:0:792BF62E1D08E575` | **donor instance** | reminted SLOT same new id |
| MODL `01661233:0:A325295480E2E835` | **donor instance** | reminted MODL `A34D0DE92FE744A1` |
| FTPT `D382BF57:80000000:A325295480E2E835` | **donor instance** | reminted FTPT same new model id |

**S4S standalone (`NovoVasoTeste2`)** updates those same COBJ fields to its **new** RIG/SLOT/MODL/FTPT instances.

So relative to the spike package alone, these are **orphans** (donor-only). With donor also in Mods they may “resolve” to the **wrong package’s** RIG/MODL/FTPT — a mixed graph — which fits a `NoneType` during component wiring better than a simple “missing string”.

### 2) STBL locale bases split (structural)

| Package | Unique STBL bases (low 56 bits) |
|---|---|
| Donor | **1** (`D6DBE9F3`) |
| S4S standalone | **1** (`7222DC92`) |
| Catalog spike | **18** (one random base per locale) |

Remint treated each STBL instance as independent. Game expects **one shared base**, locale only in the high byte. Search can still work off locale 0 while definition/string linkage stays inconsistent.

---

## Audit table (non-STBL resources)

| resource | old_tgi | new_tgi | internal_refs_before | internal_refs_after | resolved? | orphan? | notes |
|---|---|---|---|---|---|---|---|
| OBJD | `319E4F1D:80000000:B57A549C2C92F687` | `…:B54973A7C47B7546` | no package-instance u64s in body | name/desc keys + price bytes patched | yes (no donor i left in body) | no | Not the first orphan; price@16/90 also rewritten |
| COBJ | `C0DB5AE7:80000000:B57A549C2C92F687` | `…:B54973A7C47B7546` | TGI→ donor RIG/SLOT/MODL/FTPT | **same donor instances** | **no** | **yes** | **First orphan / critical** |
| RIG | `8EAF13DE:0:792BF62E1D08E575` | `…:79F06CAB65BD6BE6` | none meaningful | payload identical | index ok | no | Content unchanged |
| SLOT | `D3044521:0:792BF62E1D08E575` | `…:79F06CAB65BD6BE6` | embedded model/rig bits | partially reminted (7 bytes) | mostly | no | Index reminted; COBJ still points at old id |
| MODL | `01661233:0:A325295480E2E835` | `…:A34D0DE92FE744A1` | LE refs to DST etc. | LE reminted | index ok | no | COBJ still names **old** MODL |
| MLOD ×5 | same model i | new model i | LE DST refs | LE reminted | index ok | no | Geometry path OK at index level |
| LITE | model i | new model i | — | payload identical | index ok | no | Reminted with model group |
| FTPT | model i | new model i | u32-pair model i | reminted to new model i | index ok | no | COBJ still names **old** FTPT i |
| DST ×3 | 3 donor i | 3 new i | — | content hashes unchanged | index ok | no | — |
| THUM | donor i | new i | — | — | index ok | no | Invalid thumb is separate UI issue |
| STBL ×18 | shared base `D6DBE9F3` | **18 distinct bases** | shared locale set | **split** | **broken** | structural | Must be one shared base |

STBL detail and full remap: `output/v02_reference_audit.json`.

---

## Expected vs found

| Link | Expected after remint (like S4S) | Found in spike |
|---|---|---|
| COBJ → RIG/SLOT | new `79F06CAB65BD6BE6` | old `792BF62E1D08E575` |
| COBJ → MODL | new `A34D0DE92FE744A1` | old `A325295480E2E835` |
| COBJ → FTPT | new model instance | old `A325295480E2E835` |
| STBL locales | one base, locale in high byte | 18 independent bases |

---

## Smallest possible correction (proposal only — not applied)

**Do not** retarget `object_light_table` yet.

**Minimal fix #1 (addresses first orphan):**  
Rewrite the **COBJ TGI block** instances (hi/lo u32 pairs) from donor RIG/SLOT/MODL/FTPT ids → the reminted ids already present in the spike index. Match what S4S writes for standalone.

**Minimal fix #2 (same class of remint bug):**  
Re-issue STBL instances so all 18 locales share **one** new base (locale byte only differs), and keep the new name/desc keys.

Suggested order: fix COBJ graph first (directly ties catalog row to RIG/MODL/FTPT); then unify STBL bases; retest place. Only if instantiate still throws, revisit definition id `0524172EC4E9144A` / tuning as a follow-on.

---

## Stop line

Diagnosis complete. No package rewrite performed in this step. Next action requires an explicit go-ahead to patch COBJ internal TGIs (and optionally STBL bases) only.
