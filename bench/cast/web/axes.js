// The axes scenario in a page: show the cast in one combination (base palette, no damage, neutral
// face: 300 frames), then switch to another (dusk-winter, wounded, angry) and draw it, the way a
// game changes time of day, season and a character's state. Served by bench/load's server.
//   axes.html?sc=axes/s300ax&opt=sheets|recolour|px|pxc&cpu=N
// Every option draws only the shown combination:
// - sheets: that palette's and combination's WebP sheets (one per character);
// - recolour: that combination's base sheets, recoloured for the new palette on the switch;
// - px: every .px (all combinations baked in as frames), only the shown combination painted;
// - pxc: one PXC1 file, decoded and painted in a worker (started before the clock, as every
//   option's code is loaded before it; cpu=N is emulated in it, as Chromium can't throttle it).
import { paletteFor, resolvePx } from '/px.js';
import { recolor } from '/runtime.js';
import { loadPxc, startWorker } from './pxc-client.js';
import { shelf } from './pxc.js';

const q = new URLSearchParams(location.search);
const sc = q.get('sc'), opt = q.get('opt'), throttle = Number(q.get('cpu') ?? 1);
const base = `/sc/${sc}/out-${opt}/`;
const FIRST = { palette: '', combo: ['none', 'neutral'] }, NEXT = { palette: 'dusk-winter', combo: ['wounded', 'angry'] };
const comboName = (c) => `${c[0]}-${c[1]}`;
const r = { sc, opt };
const raf = () => new Promise((res) => requestAnimationFrame(() => res(null)));

async function image(url) { const i = new Image(); i.src = url; await i.decode(); return i; }

/** Draw every frame of the shown combination once, and read back to flush. */
function drawAll(m, get) {
  const off = document.createElement('canvas');
  off.width = off.height = 256;
  const c = off.getContext('2d');
  let n = 0;
  for (const [stem, ch] of Object.entries(m.characters)) {
    for (const id of Object.keys(ch.rects)) {
      const [img, [x, y, w, h]] = get(stem, id);
      c.drawImage(img, x, y, w, h, 0, 0, w, h);
      n++;
    }
  }
  c.getImageData(0, 0, 1, 1);
  return n;
}

function firstFrame(m, get) {
  const [stem, ch] = Object.entries(m.characters)[0];
  const [img, [x, y, w, h]] = get(stem, Object.keys(ch.rects)[0]);
  const ctx = document.getElementById('game').getContext('2d');
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(img, x, y, w, h, 200, 100, w * 3, h * 3);
}

async function main() {
  const worker = opt === 'pxc' ? await startWorker() : undefined;
  const t0 = performance.now();
  const m = await (await fetch(base + 'manifest.json')).json();
  let get, next;
  const sheets = new Map();
  let bitmapBytes = 0;
  const keep = (k, img) => { sheets.set(k, img); bitmapBytes += img.width * img.height * 4; };
  if (opt === 'sheets' || opt === 'recolour') {
    const at = (pal, combo) => Promise.all(Object.keys(m.characters).map(async (s) => {
      const k = `${pal || 'base'}/${comboName(combo)}/${s}`;
      keep(k, opt === 'sheets' || !pal ? await image(`${base}${k}.webp`)
        : recolor(await image(`${base}base/${comboName(combo)}/${s}.webp`), m.recolor[pal]));
    }));
    let shown = FIRST;
    await at(shown.palette, shown.combo);
    get = (s, id) => [sheets.get(`${shown.palette || 'base'}/${comboName(shown.combo)}/${s}`), m.characters[s].rects[id]];
    next = async () => { await at(NEXT.palette, NEXT.combo); shown = NEXT; };
  } else if (opt === 'px') {
    const texts = new Map();
    await Promise.all(m.sources.map(async (n) => texts.set(n, await (await fetch(base + 'pxart/' + n)).text())));
    r.fetch = performance.now() - t0;
    const t1 = performance.now();
    const docs = new Map(Object.keys(m.characters).map((s) => [s, resolvePx(s + '.px', (p) => texts.get(p) ?? null)]));
    r.parse = performance.now() - t1;
    // paint one combination's frames, in one palette, into one sheet per character
    const paint = ({ palette, combo }) => {
      const prefix = comboName(combo) + '/';
      for (const [s, doc] of docs) {
        const frames = doc.frames.filter((f) => f.id.startsWith(prefix));
        const { at, size: [W, H] } = shelf(new Map(frames.map((f) => [f.id, [f.rows[0].length, f.rows.length]])));
        const data = new Uint8ClampedArray(W * H * 4), u32 = new Uint32Array(data.buffer);
        const lut = new Map();
        for (const [k, c] of paletteFor(doc, palette || undefined)) if (k !== '.' && c[3]) lut.set(k, ((c[3] << 24) | (c[2] << 16) | (c[1] << 8) | c[0]) >>> 0);
        for (const f of frames) {
          const [x0, y0] = at.get(f.id);
          f.rows.forEach((row, y) => { let i = (y0 + y) * W + x0; for (let x = 0; x < row.length; x++, i++) { const v = lut.get(row[x]); if (v !== undefined) u32[i] = v; } });
        }
        const cv = document.createElement('canvas');
        cv.width = W; cv.height = H;
        cv.getContext('2d').putImageData(new ImageData(data, W, H), 0, 0);
        keep(s, cv);
        for (const f of frames) sheets.set(`${s}:${f.id.slice(prefix.length)}`, [...at.get(f.id), f.rows[0].length, f.rows.length]);
      }
    };
    const t2 = performance.now();
    paint(FIRST);
    r.paint = performance.now() - t2;
    get = (s, id) => [sheets.get(s), sheets.get(`${s}:${id}`)];
    next = async () => paint(NEXT);
  } else if (opt === 'pxc') {
    const c = await loadPxc(base + m.pxc, { palettes: [FIRST.palette], combo: FIRST.combo, worker, throttle });
    r.worker = c.timings;
    for (const b of c.sheets.values()) bitmapBytes += b.width * b.height * 4;
    let shown = FIRST;
    get = (s, id) => [c.sheets.get(shown.palette ? `${shown.palette}/${s}` : s), c.rects.get(`${s}:${comboName(shown.combo)}/${id}`)];
    next = async () => {
      r.workerSwitch = await c.paint({ palette: NEXT.palette }, NEXT.combo);
      for (const b of [...c.sheets.entries()].filter(([k]) => k.startsWith(NEXT.palette + '/')).map(([, b]) => b)) bitmapBytes += b.width * b.height * 4;
      shown = NEXT;
    };
  }
  r.ready = performance.now() - t0;
  firstFrame(m, get);
  await raf();
  r.firstDraw = performance.now() - t0;
  r.drawn = drawAll(m, get);
  r.full = performance.now() - t0;
  const t3 = performance.now();
  await next();
  r.drawnAfterSwitch = drawAll(m, get);
  r.switch = performance.now() - t3;
  r.bitmapBytes = bitmapBytes;
  r.jsHeap = performance.memory?.usedJSHeapSize ?? null;
  window.__results = r;
}

main().catch((e) => { window.__results = { sc, opt, error: String((e && e.stack) || e) }; });
