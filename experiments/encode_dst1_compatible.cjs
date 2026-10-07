/** Encode an image into a DST1 matching a supplied donor DDS header and mip layout. */
const fs = require('fs');
const Jimp = require('@s4tk/images/lib/jimp').default;
const dxt = require('silent-dxt-js');
const { DdsImage } = require('@s4tk/images');

async function main() {
  const [sourcePath, donorPath, outputPath] = process.argv.slice(2);
  if (!sourcePath || !donorPath || !outputPath) throw new Error('Usage: node encode_dst1_compatible.cjs image donor.dst output.dst');
  const donor = fs.readFileSync(donorPath);
  if (donor.subarray(0, 4).toString('ascii') !== 'DDS ' || donor.subarray(84, 88).toString('ascii') !== 'DST1') {
    throw new Error('Expected donor DDS with DST1 FourCC');
  }
  const height = donor.readUInt32LE(12);
  const width = donor.readUInt32LE(16);
  const mipCount = donor.readUInt32LE(28);
  if (!width || !height || mipCount < 1 || mipCount > 15) throw new Error('Unsupported donor dimensions/mips');
  const image = await Jimp.read(fs.readFileSync(sourcePath));
  const mipBuffers = [];
  let w = width, h = height;
  for (let i = 0; i < mipCount; i++) {
    const pw = Math.max(4, w), ph = Math.max(4, h);
    const mip = image.clone().resize(pw, ph);
    const compressed = Buffer.from(dxt.compress(mip.bitmap.data, pw, ph, dxt.flags.DXT1));
    const expected = Math.ceil(w / 4) * Math.ceil(h / 4) * 8;
    if (compressed.length !== expected) throw new Error(`Mip ${i}: ${compressed.length} != ${expected}`);
    mipBuffers.push(compressed);
    w = Math.max(1, Math.floor(w / 2));
    h = Math.max(1, Math.floor(h / 2));
  }
  const dxt1Header = Buffer.from(donor.subarray(0, DdsImage.DATA_OFFSET));
  dxt1Header.write('DXT1', 84, 'ascii');
  const unshuffled = Buffer.concat([dxt1Header, ...mipBuffers]);
  if (unshuffled.length !== donor.length) throw new Error(`DDS length changed: ${unshuffled.length} != ${donor.length}`);
  const dst1 = DdsImage.from(unshuffled).toShuffled();
  if (dst1.buffer.length !== donor.length || dst1.buffer.subarray(84, 88).toString('ascii') !== 'DST1') {
    throw new Error('DST1 conversion failed');
  }
  // Independent decode via the same library's read path catches malformed block layout.
  const bitmap = DdsImage.from(dst1.buffer).toBitmap();
  if (bitmap.width !== width || bitmap.height !== height) throw new Error('Decoded dimensions mismatch');
  fs.writeFileSync(outputPath, dst1.buffer);
  process.stdout.write(JSON.stringify({ width, height, mipCount, bytes: dst1.buffer.length,
    fourcc: 'DST1', decoded: true, sourceWidth: image.bitmap.width, sourceHeight: image.bitmap.height }) + '\n');
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
