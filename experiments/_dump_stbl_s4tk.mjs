/**
 * Dump STBL + package identity using open-source @s4tk/models (MIT).
 */
const fs = require("fs");
const path = require("path");
const { Package, StringTableResource, BinaryResourceType } = require("@s4tk/models");
const { fnv64, fnv32 } = require("@s4tk/hashing");

function dumpPkg(label, file) {
  const buf = fs.readFileSync(file);
  const pkg = Package.from(buf);
  console.log("====", label, path.basename(file), "entries", pkg.size, "====");
  const stb = [];
  const objd = [];
  const cobj = [];
  for (const entry of pkg.entries) {
    const t = entry.key.type;
    const g = entry.key.group;
    const i = entry.key.instance;
    const tgi = `${t.toString(16)}:${g.toString(16)}:${i.toString(16)}`;
    if (t === 0x220557da) {
      try {
        const stbl = entry.value; // may already be StringTableResource
        const model =
          stbl instanceof StringTableResource
            ? stbl
            : StringTableResource.from(entry.value.getBuffer ? entry.value.getBuffer() : entry.value);
        const locale = Number(i >> 56n);
        if (locale === 0) {
          const pairs = [...model.entries].map((e) => ({
            key: "0x" + (e.key >>> 0).toString(16),
            value: e.value,
          }));
          console.log("STBL locale0", pairs);
        }
        stb.push({ locale, instance: "0x" + i.toString(16), count: model.size });
      } catch (e) {
        console.log("STBL parse fail", tgi, e.message);
      }
    }
    if (t === 0x319e4f1d) {
      const raw = Buffer.from(entry.value.getBuffer ? entry.value.getBuffer() : entry.value);
      console.log("OBJD", tgi, "bytes", raw.length);
      objd.push(tgi);
    }
    if (t === 0xc0db5ae7) {
      const raw = Buffer.from(entry.value.getBuffer ? entry.value.getBuffer() : entry.value);
      // peel name/tuning ascii
      const nlen = raw.readUInt32LE(6);
      const name = raw.slice(10, 10 + nlen).toString("ascii");
      const tlen = raw.readUInt32LE(10 + nlen);
      const tuning = raw.slice(14 + nlen, 14 + nlen + tlen).toString("ascii");
      console.log("COBJ", tgi, "name=", name, "tuning=", tuning, "bytes", raw.length);
      cobj.push({ tgi, name, tuning });
    }
  }
  console.log("STBL locales", stb.length, "OBJD", objd.length, "COBJ", cobj.length);
  // hash helpers
  console.log("fnv32 name sample", "0x" + (fnv32("CCStudio Test Mug") >>> 0).toString(16));
  console.log("fnv64 name sample", "0x" + fnv64("CCStudio Test Mug").toString(16));
}

const root = path.resolve(__dirname, "..");
dumpPkg("A", path.join("C:/Users/Cliente-TechNew/Desktop/TheSims4Tool", "Vaso.package"));
dumpPkg("B", path.join("C:/Users/Cliente-TechNew/Desktop/TheSims4Tool", "NovoVasoTeste2.package"));
dumpPkg("C", path.join(root, "output", "v02_texture_spike.package"));
