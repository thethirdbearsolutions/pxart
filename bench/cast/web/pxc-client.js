// The page's side of PXC1: load a cast in a Web Worker (or, for comparison, on the main thread)
// and get drawables for it.
//   const w = await startWorker();          // optional: start the worker (and load its code) early
//   const c = await loadPxc(url, { palettes, combo, worker: w | true | false, throttle });
//   c.sheets: Map<"<palette>/<character>" ("<character>" for the base), ImageBitmap | canvas>
//   c.rects:  Map<"<character>:<frame id>", [x, y, w, h]>
//   await c.paint({ palette } | { blend: { from, to, amount } }, combo): repaint every sheet
//   c.bytes:  the decoded PXC1's size (after any gunzip), not the bytes on the wire
// workerUrl defaults to pxc-worker.js beside this file. throttle is a bench setting (see the worker).
import { blend, decode, fetchCast, palette, renderAtlas } from './pxc.js';

const key = (p, ch) => (p ? `${p}/${ch}` : ch);

function collect(target, sheets) {
  for (const s of sheets) {
    target.sheets.set(key(s.palette, s.character), s.bitmap);
    for (const [id, r] of s.rects) target.rects.set(`${s.character}:${id}`, r);
  }
}

/** A started worker, once it has loaded its code: { worker, call(msg) -> Promise<reply> }. */
export function startWorker(workerUrl) {
  const worker = new Worker(workerUrl ?? new URL('./pxc-worker.js', import.meta.url), { type: 'module' });
  const pending = new Map();
  let next = 1;
  return new Promise((ready, fail) => {
    worker.onerror = (e) => fail(new Error(`pxc worker: ${e.message ?? e}`));
    worker.onmessage = ({ data }) => {
      if (data.type === 'ready') return ready({ worker, call });
      const p = pending.get(data.id);
      pending.delete(data.id);
      if (p) (data.type === 'error' ? p.reject(new Error(data.error)) : p.resolve(data));
    };
    function call(msg) {
      const id = next++;
      return new Promise((resolve, reject) => {
        pending.set(id, { resolve, reject });
        worker.postMessage({ ...msg, id });
      });
    }
  });
}

export async function loadPxc(url, { palettes = [''], combo, worker = true, workerUrl, throttle = 1 } = {}) {
  const out = { sheets: new Map(), rects: new Map(), timings: {} };
  if (worker) {
    const w = worker === true ? await startWorker(workerUrl) : worker;
    const r = await w.call({ type: 'load', url: new URL(url, location.href).href, palettes, combo, throttle });
    collect(out, r.sheets);
    out.timings = r.timings;
    out.bytes = r.bytes;
    out.paint = async (how, c) => {
      const p = await w.call({ type: 'paint', ...how, combo: c });
      collect(out, p.sheets);
      return p.timings;
    };
    out.worker = w.worker;
    return out;
  }
  // the same work on the main thread, painted into canvases
  const t0 = performance.now();
  const buf = await fetchCast(url);
  out.timings.fetch = performance.now() - t0;
  const t1 = performance.now();
  const cast = decode(buf);
  out.timings.decode = performance.now() - t1;
  const paint = (lut, name, c) => {
    for (const ch of cast.characters) {
      const a = renderAtlas(cast, ch, lut, c);
      const canvas = document.createElement('canvas');
      canvas.width = Math.max(1, a.width);
      canvas.height = Math.max(1, a.height);
      if (a.width && a.height) canvas.getContext('2d').putImageData(new ImageData(a.data, a.width, a.height), 0, 0);
      collect(out, [{ palette: name, character: ch.name, bitmap: canvas, rects: a.rects }]);
    }
  };
  const t2 = performance.now();
  for (const p of palettes) paint(palette(cast, p), p, combo);
  out.timings.paint = performance.now() - t2;
  out.timings.total = performance.now() - t0;
  out.bytes = buf.byteLength;
  out.paint = async (how, c) => {
    const t = performance.now();
    paint(how.blend ? blend(palette(cast, how.blend.from), palette(cast, how.blend.to), how.blend.amount) : palette(cast, how.palette), how.palette ?? 'blend', c);
    return { paint: performance.now() - t };
  };
  return out;
}
