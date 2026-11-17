// Every frame a .pxc holds, in every palette (and, layered, every damage x expression combination),
// as the decoder draws it: one line per frame, "<character>.px:<frame id>%<palette or base> <w> <h> <sha256 of RGBA>".
//   node bench/cast/web/pxc-dump.mjs CAST.pxc > dump.txt
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { decode, palette, renderAtlas } from './pxc.js';

const cast = decode(readFileSync(process.argv[2]).buffer);
const combos = cast.layered ? cast.damage.flatMap((d) => cast.expression.map((e) => [d, e])) : [['none', 'neutral']];
const lines = [];
for (const p of cast.palettes) {
  const lut = palette(cast, p);
  for (const ch of cast.characters) {
    for (const combo of combos) {
      const a = renderAtlas(cast, ch, lut, combo);
      const src = new Uint32Array(a.data.buffer);
      for (const [id, [x, y, w, h]] of a.rects) {
        const px = new Uint32Array(w * h);
        for (let r = 0; r < h; r++) px.set(src.subarray((y + r) * a.width + x, (y + r) * a.width + x + w), r * w);
        const sha = createHash('sha256').update(new Uint8Array(px.buffer)).digest('hex');
        lines.push(`${ch.name}.px:${id}%${p || 'base'} ${w} ${h} ${sha}`);
      }
    }
  }
}
process.stdout.write(lines.join('\n') + '\n');
