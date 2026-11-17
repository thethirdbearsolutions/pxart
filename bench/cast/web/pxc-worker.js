// The PXC1 worker: fetches and decodes a cast and paints its sheets off the main thread, handing
// back ImageBitmaps (transferred, not copied). Every message carries an id; the reply has the same.
//   { id, type: 'load', url, palettes: [name...], combo?: [damage, expression], throttle? }
//     -> { id, type: 'loaded', sheets: [{ palette, character, bitmap, rects: [[id, [x, y, w, h]]...] }], timings, bytes }
//   { id, type: 'paint', palette?: name, blend?: { from, to, amount }, combo? }   (after a load)
//     -> { id, type: 'painted', sheets, timings }
// On start it posts { type: 'ready' }, so a page can start the worker before it needs it.
// timings are the worker's own clock: fetch (bytes in hand), decode (headers), paint, total.
//
// throttle (a bench setting, 1 by default): Chromium can't CPU-throttle a worker from DevTools, so
// to emulate a slower core the worker spins for (throttle - 1) x the time each of its own
// synchronous steps took, as DevTools throttling pauses the page's main thread.
import { blend, decode, fetchCast, palette, renderAtlas } from './pxc.js';

let cast = null;
let throttle = 1;

function step(fn) {
  const t = performance.now();
  const out = fn();
  if (throttle > 1) {
    const until = performance.now() + (performance.now() - t) * (throttle - 1);
    while (performance.now() < until);
  }
  return out;
}

async function sheets(lut, name, combo) {
  const out = [];
  for (const ch of cast.characters) {
    const a = step(() => renderAtlas(cast, ch, lut, combo));
    const bitmap = await createImageBitmap(new ImageData(a.data, Math.max(1, a.width), Math.max(1, a.height)));
    out.push({ palette: name, character: ch.name, bitmap, rects: [...a.rects] });
  }
  return out;
}

self.onmessage = async ({ data: m }) => {
  try {
    const t = {};
    const t0 = performance.now();
    if (m.type === 'load') {
      throttle = m.throttle ?? 1;
      const buf = await fetchCast(m.url);
      t.fetch = performance.now() - t0;
      const t1 = performance.now();
      cast = step(() => decode(buf));
      t.decode = performance.now() - t1;
      const t2 = performance.now();
      const all = [];
      for (const p of m.palettes) all.push(...await sheets(step(() => palette(cast, p)), p, m.combo));
      t.paint = performance.now() - t2;
      t.total = performance.now() - t0;
      self.postMessage({ id: m.id, type: 'loaded', sheets: all, timings: t, bytes: buf.byteLength }, all.map((s) => s.bitmap));
    } else if (m.type === 'paint') {
      const lut = step(() => (m.blend ? blend(palette(cast, m.blend.from), palette(cast, m.blend.to), m.blend.amount) : palette(cast, m.palette)));
      const all = await sheets(lut, m.palette ?? 'blend', m.combo);
      t.paint = t.total = performance.now() - t0;
      self.postMessage({ id: m.id, type: 'painted', sheets: all, timings: t }, all.map((s) => s.bitmap));
    }
  } catch (e) {
    self.postMessage({ id: m.id, type: 'error', error: String((e && e.stack) || e) });
  }
};

self.postMessage({ type: 'ready' });
