/**
 * Dump STBL + package identity using open-source @s4tk/models (MIT).
 */
const fs = require("fs");
const path = require("path");
const { Package, StringTableResource } = require("@s4tk/models");
const { fnv64, fnv32 } = require("@s4tk/hashing");

function getBuf(value) {
  if (!value) return Buffer.alloc(0);
  if (Buffer.isBuffer(value)) return value;
  if (value.getBuffer) return Buffer.from(value.getBuffer());
  if (value.buffer) return Buffer.from(value.buffer);
  if (value instanceof Uint8Array) return Buffer.from(value);
  return Buffer.from(value);
}

function dumpPkg(label, file) {
  const buf = fs.readFileSync(file);
  const pkg = Package.from(buf);
  console.log("====", label, path.basename(file), "entries", pkg.size, "====");
  for (const entry of pkg.entries) {
    const t = Number(entry.key.type);
    const g = Number(entry.key.group);
    const i = BigInt(entry.key.instance);
    const tgi = `${t.toString(16)}:${g.toString(16)}:${i.toString(16)}`;
    if (t === 0x220557da) {
      try {
        const raw = getBuf(entry.value);
        const model = StringTableResource.from(raw);
        const locale = Number(i >> 56n);
        if (locale === 0) {
          const pairs = [];
          for (const e of model.entries) {
            pairs.push({ key: "0x" + (Number(e.key) >>> 0).toString(16), value: e.value });
          }
          console.log("STBL locale0", JSON.stringify(pairs, null, 2));
        }
      } catch (e) {
        console.log("STBL parse fail", tgi, e.message);
      }
    }
    if (t === 0x319e4f1d) {
      console.log("OBJD", tgi, "bytes", getBuf(entry.value).length);
    }
    if (t === 0xc0db5ae7) {
      const raw = getBuf(entry.value);
      const nlen = raw.readUInt32LE(6);
      const name = raw.slice(10, 10 + nlen).toString("ascii");
      const tlen = raw.readUInt32LE(10 + nlen);
      const tuning = raw.slice(14 + nlen, 14 + nlen + tlen).toString("ascii");
      console.log("COBJ", tgi, "name=", name, "tuning=", tuning, "bytes", raw.length);
    }
  }
  console.log("fnv32", "0x" + (fnv32("CCStudio Test Mug") >>> 0).toString(16));
  console.log("fnv64", "0x" + fnv64("CCStudio Test Mug").toString(16));
}

const root = path.resolve(__dirname, "..");
dumpPkg("A", path.join("C:/Users/Cliente-TechNew/Desktop/TheSims4Tool", "Vaso.package"));
dumpPkg("B", path.join("C:/Users/Cliente-TechNew/Desktop/TheSims4Tool", "NovoVasoTeste2.package"));
dumpPkg("C", path.join(root, "output", "v02_texture_spike.package"));
