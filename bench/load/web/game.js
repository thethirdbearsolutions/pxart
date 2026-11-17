// A game page that loads one scenario in one option, then reports when it could first draw and
// when every sprite had been drawn once.   game.html?sc=s650v2&opt=atlas+.webp
// opt: frames | atlas | atlas+ | render | pxc, each optionally .oxi or .webp (images), .gzip (render,
// pxc) or .main (pxc decoded on the main thread).
import { blendPalette, load, source, startWorker } from './runtime.js';

const q = new URLSearchParams(location.search);
const sc = q.get('sc');
const opt = q.get('opt');
const base = `/sc/${sc}/out-${opt}/`;
const r = { sc, opt };
const raf = () => new Promise((res) => requestAnimationFrame(() => res(null)));

// cpu: the profile's CPU throttle, which the PXC1 worker emulates (Chromium throttles only the page)
const throttle = Number(q.get('cpu') ?? 1);

async function main() {
  // the worker is started, and its code loaded, before the clock starts, as every option's code is
  const worker = opt.startsWith('pxc') && !opt.endsWith('.main') ? await startWorker() : undefined;
  const t0 = performance.now();
  const pack = await load(base + 'manifest.json', base, opt, { worker, throttle });
  r.ready = performance.now() - t0;
  r.runtime = pack.timings;
  r.bitmapBytes = pack.bitmapBytes;

  // first draw: the cast's first frame, at 3x, on the game canvas
  const ctx = document.getElementById('game').getContext('2d');
  ctx.imageSmoothingEnabled = false;
  const first = pack.manifest.sprites[0];
  const [img, [sx, sy, sw, sh]] = source(pack, first);
  ctx.drawImage(img, sx, sy, sw, sh, 200, 100, sw * 3, sh * 3);
  await raf();
  r.firstDraw = performance.now() - t0;

  // every sprite drawn once (forces every image's decode), then a read-back to flush the canvas
  const off = document.createElement('canvas');
  off.width = off.height = 256;
  const octx = off.getContext('2d');
  const t1 = performance.now();
  for (const s of pack.manifest.sprites) {
    const [im, [x, y, w, h]] = source(pack, s);
    octx.drawImage(im, x, y, w, h, 0, 0, w, h);
  }
  octx.getImageData(0, 0, 1, 1);
  r.drawAll = performance.now() - t1;
  r.full = performance.now() - t0;

  // a palette change at runtime: .px renders one character's sheet, then the cast's, in a blend
  const variants = pack.manifest.pack.variants;
  if (pack.px && variants.length) {
    const [stem, doc] = [...pack.px.docs][0];
    const t2 = performance.now();
    pack.px.renderAtlas(stem, blendPalette(doc, variants[0], 0.3));
    r.paletteChangeOneCharacter = performance.now() - t2;
    const t3 = performance.now();
    for (const [s, d] of pack.px.docs) pack.px.renderAtlas(s, blendPalette(d, variants[0], 0.6));
    r.paletteChangeWholeCast = performance.now() - t3;
  }
  if (pack.pxc && variants.length) {  // PXC1 repaints the whole cast, in its worker for 'pxc'
    const t3 = performance.now();
    const w = await pack.pxc.paint({ blend: { from: '', to: variants[0], amount: 0.6 } });
    r.paletteChangeWholeCast = performance.now() - t3;
    r.paletteChangeWorker = w.paint;
  }
  r.jsHeap = performance.memory?.usedJSHeapSize ?? null;
  r.sprites = pack.manifest.sprites.length;
  window.__results = r;
}

main().catch((e) => { window.__results = { sc, opt, error: String((e && e.stack) || e) }; });
