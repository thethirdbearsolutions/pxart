// Every frame of each .px named, in the base palette and every variant, as px.ts draws it: one
// RGBA blob and an index, for tests/test_px_ts.py to compare with pxart.py byte for byte.
//   node js/px-dump.ts OUT_DIR FILE.px...   -> OUT_DIR/index.json + OUT_DIR/rgba.bin
// A file px.ts can't read gets {file, error} in the index instead of frames.
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { frameRgba, paletteFor, resolvePx } from './px.ts';

const [out, ...files] = process.argv.slice(2);
const read = (p: string): string | null => (existsSync(p) ? readFileSync(p, 'utf8') : null);
const index: { file: string; frame?: string; variant?: string; pick?: string; w?: number; h?: number; offset?: number; error?: string }[] = [];
const chunks: Uint8Array[] = [];
let offset = 0;
for (const file of files) {
  let doc;
  try {
    doc = resolvePx(file, read);
  } catch (e) {
    index.push({ file, error: String(e) });
    continue;
  }
  // the base palette, then each slot color picked alone (k=i, i >= 1), keys in order; in each variant
  const picks: [string, Record<string, number> | undefined][] = [['', undefined]];
  for (const k of [...doc.slots.keys()].sort())
    for (let i = 1; i < doc.slots.get(k)!.length; i++) picks.push([`${k}=${i}`, { [k]: i }]);
  for (const variant of ['', ...doc.variants.keys()]) {
    for (const [pick, chosen] of picks) {
      const pal = paletteFor(doc, variant || undefined, chosen);
      for (const f of doc.frames) {
        const { width, height, data } = frameRgba(f, pal);
        index.push({ file, frame: f.id, variant, pick, w: width, h: height, offset });
        chunks.push(new Uint8Array(data.buffer, data.byteOffset, data.byteLength));
        offset += data.byteLength;
      }
    }
  }
}
const blob = new Uint8Array(offset);
let at = 0;
for (const c of chunks) {
  blob.set(c, at);
  at += c.byteLength;
}
writeFileSync(join(out, 'rgba.bin'), blob);
writeFileSync(join(out, 'index.json'), JSON.stringify(index));
