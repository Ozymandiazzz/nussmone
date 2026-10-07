import json
from collections import Counter
from pathlib import Path

inv = json.loads(Path("output/catalog_inv_NovoVasoTeste2.package.json").read_text(encoding="utf-8"))
print("A counts", inv["packages"]["A_donor"]["by_type_counts"])
print("B counts", inv["packages"]["B_s4s"]["by_type_counts"])
print("C counts", inv["packages"]["C_spike"]["by_type_counts"])
print("A OBJD", inv["packages"]["A_donor"]["OBJD"])
print("A COBJ", inv["packages"]["A_donor"]["COBJ"])
print("A MODL", inv["packages"]["A_donor"]["MODL"])
print("B OBJD", inv["packages"]["B_s4s"]["OBJD"])
print("B COBJ", inv["packages"]["B_s4s"]["COBJ"])
print("B MODL", inv["packages"]["B_s4s"]["MODL"])
print("C OBJD", inv["packages"]["C_spike"]["OBJD"])
print("C COBJ", inv["packages"]["C_spike"]["COBJ"])
print("C MODL", inv["packages"]["C_spike"]["MODL"])
print("A MLOD", [hex(x) for x in inv["packages"]["A_donor"]["MLOD_instances"]])
print("B MLOD", [hex(x) for x in inv["packages"]["B_s4s"]["MLOD_instances"]])
print("A DST", [hex(x) for x in inv["packages"]["A_donor"]["DST_instances"]])
print("B DST", [hex(x) for x in inv["packages"]["B_s4s"]["DST_instances"]])
print(
    "shared A-B",
    inv["diff_A_vs_B_instances"]["shared_count"],
    "only_b",
    len(inv["diff_A_vs_B_instances"]["only_b"]),
    "only_a",
    len(inv["diff_A_vs_B_instances"]["only_a"]),
)
c = Counter(x["type"] for x in inv["shared_instances_A_C_detail"])
print("shared A-C types", dict(c))
print("sha_match shared A-C", sum(1 for x in inv["shared_instances_A_C_detail"] if x["sha_match_donor"]))
print("shared A-C detail")
for x in inv["shared_instances_A_C_detail"]:
    print(" ", x)

def locales(xs):
    return sorted({(i >> 56) & 0xFF for i in xs})

print("A STBL locales", locales(inv["packages"]["A_donor"]["STBL_instances"]))
print("B STBL locales", locales(inv["packages"]["B_s4s"]["STBL_instances"]))
print("A STBL bases", sorted({hex(i & ((1 << 56) - 1)) for i in inv["packages"]["A_donor"]["STBL_instances"]}))
print("B STBL bases", sorted({hex(i & ((1 << 56) - 1)) for i in inv["packages"]["B_s4s"]["STBL_instances"]}))
print("C STBL bases", sorted({hex(i & ((1 << 56) - 1)) for i in inv["packages"]["C_spike"]["STBL_instances"]}))
