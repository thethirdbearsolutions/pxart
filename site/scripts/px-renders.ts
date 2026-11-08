// Render .px files with the site's reader (src/lib/px.ts): for each file, each frame in the base
// palette and every variant, print {file: {variant: {frameId: [w, h, sha256 of RGBA]}}} as JSON.
// tests/test_site.py compares that with pxart.py's own renders, so the site draws what pxart draws.
//   node scripts/px-renders.ts FILE.px...
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { resolvePx, paletteFor, frameRgba } from "../src/lib/px.ts";

const out: Record<string, Record<string, Record<string, [number, number, string] | string>>> = {};
for (const file of process.argv.slice(2)) {
  try {
    const doc = resolvePx(file, (p) => (existsSync(p) ? readFileSync(p, "utf8") : null));
    const byVariant: Record<string, Record<string, [number, number, string]>> = {};
    for (const variant of ["", ...doc.variants.keys()]) {
      const pal = paletteFor(doc, variant || undefined);
      const frames: Record<string, [number, number, string]> = {};
      for (const f of doc.frames) {
        const { width, height, data } = frameRgba(f, pal);
        frames[f.id] = [width, height, createHash("sha256").update(data).digest("hex")];
      }
      byVariant[variant] = frames;
    }
    out[file] = byVariant;
  } catch (e) {
    out[file] = { error: String(e) } as never;
  }
}
console.log(JSON.stringify(out));
