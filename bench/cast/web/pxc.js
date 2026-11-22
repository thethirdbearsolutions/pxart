// PXC1 decoder: no DOM, so it runs in a Web Worker, on the main thread or under node. The format is
// described in ../pxc.py. decode(buffer) reads the headers and keeps the index plane as is;
// palette(cast, name) makes a palette (from the axes for a layered cast); renderAtlas(...) paints
// one character's frames, in one palette and one damage x expression combination, into one RGBA
// sheet laid out as the load bench lays out its sheets.

class Reader {
  constructor(buf) { this.b = new Uint8Array(buf); this.i = 0; }
  byte() { return this.b[this.i++]; }
  varint() { let n = 0, s = 0, b; do { b = this.b[this.i++]; n += (b & 0x7f) * 2 ** s; s += 7; } while (b & 0x80); return n; }
  svarint() { const n = this.varint(); return n % 2 ? -(n + 1) / 2 : n / 2; }
  string() { const n = this.varint(); const s = new TextDecoder().decode(this.b.subarray(this.i, this.i + n)); this.i += n; return s; }
}

export function decode(buffer) {
  const r = new Reader(buffer);
  const magic = String.fromCharCode(...r.b.subarray(0, 4));
  r.i = 4;
  if (magic !== 'PXC1') throw new Error(`not a PXC1 file (${magic})`);
  const flags = r.byte();
  if (flags & 4) throw new Error('ops coding is for measuring only; decode reads raw planes');
  const layered = !!(flags & 1), cols = !!(flags & 2);
  const palettes = Array.from({ length: r.varint() }, () => r.string());
  const axes = [];
  if (layered) {
    for (let a = r.varint(); a > 0; a--) {
      const name = r.string();
      const values = new Map();
      for (let v = r.varint(); v > 0; v--) {
        const vname = r.string();
        const mul = [], add = [];
        for (let c = 0; c < 3; c++) { mul.push(r.varint() / 1000); add.push(r.svarint()); }
        values.set(vname, { mul, add });
      }
      axes.push({ name, values });
    }
  }
  const nkeys = r.varint();
  const tables = new Map();
  for (const p of layered ? [''] : palettes) {
    const t = [];
    for (let k = 0; k < nkeys; k++) t.push([r.byte(), r.byte(), r.byte(), r.byte()]);
    tables.set(p, t);
  }
  const characters = [];
  let off = 0;
  for (let c = r.varint(); c > 0; c--) {
    const ch = { name: r.string(), frames: [], overlays: [] };
    for (let f = r.varint(); f > 0; f--) {
      const id = r.string(), w = r.varint(), h = r.varint();
      ch.frames.push({ id, w, h, off });
      off += w * h;
    }
    if (layered) {
      for (let o = r.varint(); o > 0; o--) {
        ch.overlays.push({ name: r.string(), at: r.byte() ? 'body' : 'head', dx: r.svarint(), dy: r.svarint(), w: r.varint(), h: r.varint() });
      }
      for (const f of ch.frames) {
        f.head = [r.varint(), r.varint()];
        f.body = [r.varint(), r.varint()];
        f.mirror = r.byte() === 1;
      }
    }
    characters.push(ch);
  }
  let damage = [''], expression = [''];
  if (layered) {
    damage = Array.from({ length: r.varint() }, () => r.string());
    expression = Array.from({ length: r.varint() }, () => r.string());
  }
  for (const ch of characters) for (const o of ch.overlays) { o.off = off; off += o.w * o.h; }
  const plane = r.b.subarray(r.i, r.i + off);
  if (plane.length !== off) throw new Error(`plane is ${plane.length} bytes, headers say ${off}`);
  return { layered, cols, palettes, axes, tables, nkeys, characters, damage, expression, plane };
}

/** Fetch a .pxc as bytes. Bytes that are still gzip (they start 1f 8b) are gunzipped here
 *  (DecompressionStream), for hosts that won't compress an unknown type and serve cast.pxc.gz as is;
 *  otherwise the host's Content-Encoding (brotli, or gzip) has already done it. The bytes decide,
 *  not the URL: a cache-busting query (cast.pxc.gz?r=2) still gunzips, and a .gz a server already
 *  decoded (sent with Content-Encoding: gzip) isn't gunzipped twice. A .pxc starts 'PXC1'. */
export async function fetchCast(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  return gunzipped(await res.arrayBuffer());
}

/** buf gunzipped if it is gzip (magic 1f 8b), else buf itself. */
export async function gunzipped(buf) {
  const b = new Uint8Array(buf);
  if (b.length < 2 || b[0] !== 0x1f || b[1] !== 0x8b) return buf;
  return new Response(new Response(b).body.pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
}

const axis = (c, mul, add) => Math.max(0, Math.min(255, Math.floor(c * mul + add + 0.5)));

/** A palette as packed RGBA (little-endian u32, index 0 transparent). Layered: name is
 *  "<value>-<value>" over the axes, applied in the file's axis order; "" is the base. */
export function palette(cast, name) {
  let table = cast.tables.get(cast.layered ? '' : name);
  if (!table) throw new Error(`no palette '${name}'`);
  if (cast.layered && name) {
    const parts = name.split('-');
    table = table.map(([r, g, b, a]) => {
      let rgb = [r, g, b];
      for (const ax of cast.axes) {
        const v = parts.map((p) => ax.values.get(p)).find(Boolean);
        if (v) rgb = rgb.map((c, i) => axis(c, v.mul[i], v.add[i]));
      }
      return [...rgb, a];
    });
  }
  return u32(table);
}

/** Packed RGBA for a table of [r, g, b, a], with index 0 left transparent. */
export function u32(table) {
  const lut = new Uint32Array(table.length + 1);
  table.forEach(([r, g, b, a], i) => { lut[i + 1] = a ? ((a << 24) | (b << 16) | (g << 8) | r) >>> 0 : 0; });
  return lut;
}

/** The bench's sheet layout: tallest first, rows 1024 wide, 1 px gaps (bench/load/web/runtime.js). */
export function shelf(sizes) {
  const order = [...sizes.keys()].sort((a, b) => sizes.get(b)[1] - sizes.get(a)[1] || sizes.get(b)[0] - sizes.get(a)[0] || (a < b ? -1 : 1));
  let x = 0, y = 0, rowH = 0, usedW = 0;
  const at = new Map();
  for (const k of order) {
    const [w, h] = sizes.get(k);
    if (x && x + w > 1024) { y += rowH + 1; x = 0; rowH = 0; }
    at.set(k, [x, y]);
    x += w + 1;
    rowH = Math.max(rowH, h);
    usedW = Math.max(usedW, x - 1);
  }
  return { at, size: [usedW, y + rowH] };
}

/** Frame ids a combination draws: the base ids, or "<damage>-<expression>/<id>" for a layered cast. */
export const comboId = (cast, id, combo) => (cast.layered ? `${combo[0]}-${combo[1]}/${id}` : id);

function stamp(cast, out, W, x0, y0, f, o, lut) {
  const [ax, ay] = o.at === 'head' ? f.head : f.body;
  const { plane, cols } = cast;
  for (let y = 0; y < o.h; y++) {
    for (let x = 0; x < o.w; x++) {
      const k = plane[o.off + (cols ? x * o.h + y : y * o.w + x)];
      if (!k) continue;
      const dx = f.mirror ? -(o.dx + o.w - 1) + (o.w - 1 - x) : o.dx + x;
      const X = ax + dx, Y = ay + o.dy + y;
      if (X < 0 || Y < 0 || X >= f.w || Y >= f.h) continue;
      out[(y0 + Y) * W + x0 + X] = lut[k];
    }
  }
}

/** One character's frames in one palette (a packed LUT) and one combination, as one RGBA sheet:
 *  { width, height, data: Uint8ClampedArray, rects: Map<frame id, [x, y, w, h]> }. */
export function renderAtlas(cast, ch, lut, combo = ['none', 'neutral']) {
  const sizes = new Map(ch.frames.map((f) => [comboId(cast, f.id, combo), [f.w, f.h]]));
  const { at, size: [W, H] } = shelf(sizes);
  const data = new Uint8ClampedArray(W * H * 4);
  const out = new Uint32Array(data.buffer);
  const { plane, cols } = cast;
  const ovs = new Map(ch.overlays.map((o) => [o.name, o]));
  const rects = new Map();
  for (const f of ch.frames) {
    const id = comboId(cast, f.id, combo);
    const [x0, y0] = at.get(id);
    rects.set(id, [x0, y0, f.w, f.h]);
    if (cols) {
      for (let x = 0; x < f.w; x++) {
        let i = f.off + x * f.h, o = y0 * W + x0 + x;
        for (let y = 0; y < f.h; y++, i++, o += W) { const k = plane[i]; if (k) out[o] = lut[k]; }
      }
    } else {
      for (let y = 0; y < f.h; y++) {
        let i = f.off + y * f.w, o = (y0 + y) * W + x0;
        for (let x = 0; x < f.w; x++, i++, o++) { const k = plane[i]; if (k) out[o] = lut[k]; }
      }
    }
    if (cast.layered) {
      const facing = f.id.split('/')[1];
      const d = ovs.get(`damage:${combo[0]}`);
      if (d) stamp(cast, out, W, x0, y0, f, d, lut);
      if (facing !== 'up') {
        const e = ovs.get(`expression:${combo[1]}:${facing === 'down' ? 'front' : 'side'}`);
        if (e) stamp(cast, out, W, x0, y0, f, e, lut);
      }
    }
  }
  return { width: W, height: H, data, rects };
}

/** A packed palette `amount` of the way from palette a to palette b (0..1): a continuous blend. */
export function blend(a, b, amount) {
  const out = new Uint32Array(a.length);
  for (let i = 1; i < a.length; i++) {
    let v = 0;
    for (let s = 0; s < 32; s += 8) {
      const x = (a[i] >>> s) & 255, y = (b[i] >>> s) & 255;
      v |= Math.round(x + (y - x) * amount) << s;
    }
    out[i] = v >>> 0;
  }
  return out;
}
