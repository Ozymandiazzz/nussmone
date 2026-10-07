# v0.2C — COBJ TGI fix (Phase A)

**Minimal fix only.** STBL not touched. Tuning not touched. Mesh/MLOD/DST payloads unchanged. `ccstudio.py` unchanged.

## Cause addressed

Catalog spike remint rewrote index TGIs and LE `u64` embeds, but **COBJ’s internal TGI block** stores instances as **hi/lo `u32` pairs**. Those still pointed at donor:

| Type | Old (donor) | New (reminted, already in package) |
|---|---|---|
| RIG `8EAF13DE` | `792BF62E1D08E575` | `79F06CAB65BD6BE6` |
| SLOT `D3044521` | `792BF62E1D08E575` | `79F06CAB65BD6BE6` |
| MODL `01661233` | `A325295480E2E835` | `A34D0DE92FE744A1` |
| FTPT `D382BF57` | `A325295480E2E835` | `A34D0DE92FE744A1` |

## Command

```powershell
cd C:\Users\Cliente-TechNew\Desktop\nussmone
python experiments\v02_cobj_fix.py
```

**Input:** `output\v02_catalog_spike.package`  
**Output:** `output\v02_catalog_cobjfix.package`  
**Report:** `output\v02_cobj_fix_report.json`  
**Log:** `output\v02_cobj_fix_run.log`

## Programmatic audit

| Check | Result |
|---|---|
| COBJ orphans before | **4** |
| COBJ orphans after | **0** |
| Changes applied | **4** (RIG/SLOT/MODL/FTPT) |
| DST content SHA set | **unchanged** |
| MLOD g=0 content SHA | **unchanged** |
| OBJD instance | unchanged (`B54973A7C47B7546`) |
| STBL | **not modified** |
| Tuning string | still `object_light_table` |
| Status | **PASS** |

### COBJ refs after

```
00000000:00000000:0000000000000000
8EAF13DE:00000000:79F06CAB65BD6BE6
D3044521:00000000:79F06CAB65BD6BE6
01661233:00000000:A34D0DE92FE744A1
D382BF57:80000000:A34D0DE92FE744A1
```

## Manual acceptance (you)

1. Mods: **donor** `Vaso.package` + **`output\v02_catalog_cobjfix.package`** (prefer this over the old catalog spike)  
2. Search `CCStudio Test Mug`  
3. Try to place  

**PASS parcial:** appears + place does **not** write `lastException` with the prior `NoneType` instantiate crash.  
**If still FAIL:** capture new `lastException`, then Phase B (unify STBL locale bases) only.

## Not done (by design)

- STBL base unification (Phase B)  
- Tuning retarget  
- Thumbnail  
- Mesh / DST / MLOD geometry edits  
- Broad remint rewrite
