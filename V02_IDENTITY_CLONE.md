# v0.2 identity clone

## Scope

This experiment clones `NovoVasoTeste2.package` by reminting resource instances and rewriting embedded references to those instances. It does not replace mesh, texture, tuning, catalog text, price, category, footprint, slots, rig, or thumbnail content. It does not modify `ccstudio.py` or the CLI.

Run:

```powershell
python experiments/v02_identity_clone.py
```

Inputs and outputs:

- Donor: `C:\Users\Cliente-TechNew\Desktop\TheSims4Tool\NovoVasoTeste2.package`
- Clone: `output/v02_identity_clone.package`
- Full audit: `output/v02_identity_clone_report.json`

The script accepts `--donor`, `--output`, `--report`, and `--salt`. Its default salt gives reproducible IDs for this experiment. Use a different salt for another clone meant to coexist with this one.

## Programmatic result

`PROGRAMMATIC_PASS`: the output reopens as DBPF with 34 resources and 26 reminted unique instances. There are no remaining donor instance patterns in decompressed resources, no unresolved COBJ TGI references, and all 18 STBL locale instances retain a single shared base. The output has 120,498 bytes. The donor SHA-256 before the run was `87fa5277c6bd5d86767100bfab94617ef830e0a2caeed0cf69dd46acd02ecdd3`.

Nine resource payloads changed, exclusively at matched instance-reference bytes: five MLODs, MODL, FTPT, COBJ, and THUM. The other 25 decompressed payloads are byte-identical. In particular, OBJD is 258 bytes before and after with **zero changed bytes**; COBJ is 388 bytes before and after with 31 changed bytes across four internal TGI references. DST, STBL, RIG, SLOT, and LITE payloads are unchanged. All resource lengths are unchanged. The report contains every old → new TGI, reference offset and encoding, resource hash, and changed-byte count.

The writer copies compressed raw payload bytes when their decompressed content is unchanged. It recompresses only the nine resources with reminted internal references. This deliberately limits the experiment to identity and reference changes.

## Manual game acceptance: PASS

Tested on 2026-09-29 with only `v02_identity_clone.package` active in
`Mods/CCStudio`; `v02_catalog_cobjfix.package` and
`v02_decor_rebuild.package` were moved outside the Mods tree.

1. The decorative vase appeared in catalog search: **PASS**.
2. A vase cloned from this package was placed and visible on the lot: **PASS**.
3. No immediate “Falha na chamada do script” popup was visible: **PASS**.
4. The capture did not show the ghost frame directly, but successful placement
   proves that the object passed definition instantiation and placement.

No `LastException`, `lastUIException`, or `lastCrash` file was created during
this test. The newest files found are from 2026-09-22 and belong to earlier
failed tests.

**Conclusion:** basic DBPF writing, identity remint, shared STBL base, and
internal reference rewriting work for `NovoVasoTeste2`. The failure in
`v02_decor_rebuild.package` was introduced after the identity-clone stage.
The next differential test must add exactly one later operation at a time:
catalog edits, mesh replacement, then texture replacement (or another explicit
order), always starting from the passing identity clone.

This remains a private format experiment. No Sims 4 Studio code is bundled.
