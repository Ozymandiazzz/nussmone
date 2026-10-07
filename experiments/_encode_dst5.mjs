import fs from "fs";
import { createRequire } from "module";
const require = createRequire(import.meta.url);
const { DdsImage } = require("@s4tk/images");

const pngPath = process.argv[2];
const outPath = process.argv[3];
const maxMipMaps = Number(process.argv[4] || 12);

const png = fs.readFileSync(pngPath);
const img = await DdsImage.fromImageAsync(png, { shuffle: true, maxMipMaps });
const dst = img.toShuffled();
fs.writeFileSync(outPath, dst.buffer);
const fourcc = dst.buffer.slice(84, 88).toString("ascii");
console.log(JSON.stringify({
  bytes: dst.buffer.length,
  width: dst.header.width,
  height: dst.header.height,
  fourcc,
  isShuffled: dst.isShuffled,
  encoder: "@s4tk/images",
}));
