// How a game page loads a pack in each option, and gets a drawable for every manifest entry.
//   load(manifestUrl, base, kind) -> { manifest, images: Map<path, CanvasImageSource>, timings, bitmapBytes, px? }
// kind: 'frames' (one image per entry, under frames/), 'atlas' (sheets, entries point at rects),
// 'atlas+' (base sheets, variant entries recolored at load), 'render' (.px sources drawn with
// pxart's px.ts into one sheet per character per palette), 'pxc' (the whole cast as one PXC1 file,
// decoded and painted in a Web Worker; 'pxc.main' does it on the main thread).
import { paletteFor, resolvePx } from './px.js';
import { loadPxc, startWorker } from '/pxc/pxc-client.js';

export { startWorker };

async function image(url) {
  const img = new Image();
  img.src = url;
  await img.decode();
  return img;
}

/** Every distinct image path the manifest names, fetched and decoded in parallel. */
async function images(manifest, base) {
  const paths = [...new Set(manifest.sprites.map((s) => s.path))];
  const out = new Map();
  await Promise.all(paths.map(async (p) => out.set(p, await image(base + p))));
  return out;
}

// ---- atlas+: recolor a base sheet through a color map ----------------------------------------

const hexToRgba = (h) => [1, 3, 5, 7].map((i) => parseInt(h.slice(i, i + 2) || 'ff', 16));

// The browser hands back premultiplied-then-unpremultiplied colors for translucent pixels, so
// each map key is round-tripped through a canvas first.
function roundTripKey(rgba) {
  const c = document.createElement('canvas');
  c.width = c.height = 1;
  const ctx = c.getContext('2d', { willReadFrequently: true });
  ctx.putImageData(new ImageData(new Uint8ClampedArray(rgba), 1, 1), 0, 0);
  const d = ctx.getImageData(0, 0, 1, 1).data;
  return ((d[3] << 24) | (d[2] << 16) | (d[1] << 8) | d[0]) >>> 0;
}

export function recolor(img, map) {
  const lut = new Map();
  for (const [from, to] of Object.entries(map)) {
    const t = hexToRgba(to);
    lut.set(roundTripKey(hexToRgba(from)), ((t[3] << 24) | (t[2] << 16) | (t[1] << 8) | t[0]) >>> 0);
  }
  const c = document.createElement('canvas');
  c.width = img.width;
  c.height = img.height;
  const ctx = c.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(img, 0, 0);
  const id = ctx.getImageData(0, 0, c.width, c.height);
  const u32 = new Uint32Array(id.data.buffer);
  for (let i = 0; i < u32.length; i++) {
    if (!u32[i]) continue;
    const v = lut.get(u32[i] >>> 0);
    if (v !== undefined) u32[i] = v;
  }
  ctx.putImageData(id, 0, 0);
  return c;
}

// ---- render: .px -> one sheet per character per palette ---------------------------------------

const GAP = 1;
const WIDTH = 1024;

function shelf(sizes) {
  const order = [...sizes.keys()].sort((a, b) => sizes.get(b)[1] - sizes.get(a)[1] || sizes.get(b)[0] - sizes.get(a)[0] || (a < b ? -1 : 1));
  let x = 0, y = 0, rowH = 0, usedW = 0;
  const at = new Map();
  for (const k of order) {
    const [w, h] = sizes.get(k);
    if (x && x + w > WIDTH) { y += rowH + GAP; x = 0; rowH = 0; }
    at.set(k, [x, y]);
    x += w + GAP;
    rowH = Math.max(rowH, h);
    usedW = Math.max(usedW, x - GAP);
  }
  return { at, size: [usedW, y + rowH] };
}

/** One palette's frames into one RGBA buffer, then one putImageData. */
function paint(frames, at, size, pal) {
  const [W, H] = size;
  const data = new Uint8ClampedArray(W * H * 4);
  const lut = new Map();
  for (const [k, c] of pal) if (k !== '.' && c[3]) lut.set(k, ((c[3] << 24) | (c[2] << 16) | (c[1] << 8) | c[0]) >>> 0);
  const u32 = new Uint32Array(data.buffer);
  for (const [fid, f] of frames) {
    const [x0, y0] = at.get(fid);
    f.rows.forEach((row, y) => {
      let i = (y0 + y) * W + x0;
      for (let x = 0; x < row.length; x++, i++) {
        const v = lut.get(row[x]);
        if (v !== undefined) u32[i] = v;
      }
    });
  }
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, W);
  canvas.height = Math.max(1, H);
  if (W && H) canvas.getContext('2d').putImageData(new ImageData(data, W, H), 0, 0);
  return canvas;
}

/** A palette `amount` of the way from base to variant `v` (0..1): a continuous dawn or dusk. */
export function blendPalette(doc, v, amount) {
  const a = paletteFor(doc), b = paletteFor(doc, v);
  const out = new Map();
  for (const [k, c] of a) {
    const d = b.get(k) ?? c;
    out.set(k, [0, 1, 2, 3].map((i) => Math.round(c[i] + (d[i] - c[i]) * amount)));
  }
  return out;
}

async function loadPx(manifest, base, t) {
  const t0 = performance.now();
  const texts = new Map();
  await Promise.all(manifest.pack.sources.map(async (n) => texts.set(n, await (await fetch(base + 'pxart/' + n)).text())));
  t.fetch = performance.now() - t0;
  const t1 = performance.now();
  const stems = [...new Set(manifest.sprites.map((s) => s.character))];
  const docs = new Map(stems.map((s) => [s, resolvePx(s + '.px', (p) => texts.get(p) ?? null)]));
  t.parse = performance.now() - t1;
  const t2 = performance.now();
  const layout = new Map();
  for (const [stem, doc] of docs) {
    const frames = new Map(doc.frames.map((f) => [f.id, f]));
    const sizes = new Map([...frames].map(([id, f]) => [id, [Math.max(0, ...f.rows.map((r) => r.length)), f.rows.length]]));
    layout.set(stem, { ...shelf(sizes), frames });
  }
  const renderAtlas = (stem, pal) => { const l = layout.get(stem); return paint(l.frames, l.at, l.size, pal); };
  const out = new Map();
  for (const v of [undefined, ...manifest.pack.variants])
    for (const [stem, doc] of docs) out.set(`${v ? v + '/' : ''}${stem}.atlas`, renderAtlas(stem, paletteFor(doc, v)));
  t.render = performance.now() - t2;
  for (const s of manifest.sprites) {
    const [x, y] = layout.get(s.character).at.get(s.frame);
    s.path = `${s.variant ? s.variant + '/' : ''}${s.character}.atlas`;
    s.src = { rect: [x, y, s.px[0], s.px[1]] };
  }
  return { images: out, px: { docs, renderAtlas } };
}

async function loadPxcPack(manifest, base, worker, throttle, t) {
  const c = await loadPxc(base + manifest.pack.pxc, { palettes: ['', ...manifest.pack.variants], worker, throttle });
  Object.assign(t, c.timings);
  const out = new Map();
  for (const s of manifest.sprites) {
    const key = `${s.variant ? s.variant + '/' : ''}${s.character}`;
    out.set(key, c.sheets.get(key));
    s.path = key;
    s.src = { rect: c.rects.get(`${s.character}:${s.frame}`) };
  }
  return { images: out, pxc: c };
}

/** opts.worker: a started PXC1 worker (startWorker) for the 'pxc' options; opts.throttle: the
 *  CPU slow-down the bench emulates in that worker (Chromium can't throttle workers itself). */
export async function load(manifestUrl, base, opt, opts = {}) {
  const kind = opt.split('.')[0];
  const timings = {};
  const t0 = performance.now();
  const manifest = await (await fetch(manifestUrl)).json();
  let imgs, px = null, pxc = null;
  if (kind === 'render') ({ images: imgs, px } = await loadPx(manifest, base, timings));
  else if (kind === 'pxc') ({ images: imgs, pxc } = await loadPxcPack(manifest, base, opt.endsWith('.main') ? false : (opts.worker ?? true), opts.throttle ?? 1, timings));
  else {
    imgs = await images(manifest, kind === 'frames' ? base + 'frames/' : base);
    timings.fetchDecode = performance.now() - t0;
    if (kind === 'atlas+') {
      const t1 = performance.now();
      for (const s of manifest.sprites) {
        const v = s.src?.recolor;
        if (!v) continue;
        const key = `${v}/${s.path}`;
        if (!imgs.has(key)) imgs.set(key, recolor(imgs.get(s.path), manifest.pack.recolor[v]));
        s.path = key;
      }
      timings.recolor = performance.now() - t1;
    }
  }
  timings.total = performance.now() - t0;
  let bitmapBytes = 0;
  for (const c of imgs.values()) bitmapBytes += c.width * c.height * 4;
  return { manifest, images: imgs, timings, bitmapBytes, px, pxc };
}

/** The image and rect an entry draws from. */
export function source(pack, s) {
  const img = pack.images.get(s.path);
  return [img, s.src?.rect ?? [0, 0, img.width, img.height]];
}
