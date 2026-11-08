// A small reader for the .px format, enough to draw what the docs show: palette lines
// (slots too, drawn in their base color), @variant blocks, @frame grids and comments.
// It is not pxart: it doesn't check, report error codes or follow @palette by itself
// (pass `imports` for that). pxart.py is the reference.

export type Rgba = [number, number, number, number];

export interface PxFrame {
  id: string;
  rows: string[];
  ms?: number;
}

export interface PxDoc {
  palette: Map<string, Rgba>;
  variants: Map<string, Map<string, Rgba>>;
  imports: string[];
  frames: PxFrame[];
  anims: Map<string, { ms?: number }>;
  unknown: Set<string>;
}

// A key line as pxart reads one: a key, whitespace, a color or a slot list (`#a | #b`).
const KEY_LINE = /^(\S)\s+(\S+(?:\s*\|\s*\S*)*)$/;

export function parseColor(text: string): Rgba | null {
  const c = text.split("|")[0].trim(); // a slot list: the first is the key's color
  if (c === "transparent") return [0, 0, 0, 0];
  const m = /^#([0-9a-fA-F]{6})([0-9a-fA-F]{2})?$/.exec(c);
  if (!m) return null;
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255, m[2] ? parseInt(m[2], 16) : 255];
}

/**
 * Read a .px file as pxart.py reads it (checked against pxart's own renders of every example by
 * tests/test_site.py): lines are trimmed; `#` lines are comments; `pxart N` is skipped as the first
 * line; a `@variant`'s key lines run to the next blank or `@` line; `@anim`/`@still` lines don't end
 * a frame; an unknown `@section`'s lines are its own; bare rows with no `@frame` are one grid, blank
 * lines and all. `imports` are the palettes of the file's `@palette` lines, in order.
 */
export function parsePx(text: string, imports: Map<string, Rgba>[] = []): PxDoc {
  const doc: PxDoc = {
    palette: new Map(),
    variants: new Map(),
    imports: [],
    frames: [],
    anims: new Map(),
    unknown: new Set(),
  };
  for (const pal of imports) for (const [k, v] of pal) doc.palette.set(k, v);
  const own = new Map<string, Rgba>();
  let state: "header" | "variant" | "frame" | "ext" = "header";
  let variant: Map<string, Rgba> | null = null;
  let frame: PxFrame | null = null;
  let started = false;

  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) {
      if (!line && state === "variant") state = "header";
      continue;
    }
    if (!started && /^pxart\s+\S+$/.test(line)) {
      started = true;
      continue;
    }
    started = true;
    if (line.startsWith("@")) {
      const [word, arg = "", ...rest] = line.split(/\s+/);
      const ms = rest.map((r) => /^ms=(\d+)$/.exec(r)).find(Boolean);
      if (word === "@frame") {
        frame = { id: arg, rows: [], ms: ms ? Number(ms[1]) : undefined };
        doc.frames.push(frame);
        state = "frame";
      } else if (word === "@palette") {
        doc.imports.push(line.slice(word.length).trim());
        state = "header";
      } else if (word === "@variant") {
        variant = doc.variants.get(arg) ?? new Map();
        doc.variants.set(arg, variant);
        state = "variant";
      } else if (word === "@anim" || word === "@still") {
        if (word === "@anim") doc.anims.set(arg, { ms: ms ? Number(ms[1]) : undefined });
        if (!doc.frames.length) state = "header";
      } else state = "ext";
      continue;
    }
    if (state === "ext") continue;
    const key = KEY_LINE.exec(line);
    if (key) {
      const color = parseColor(key[2]);
      if (color) (state === "variant" ? variant! : own).set(key[1], color);
      continue;
    }
    if (!frame) {
      frame = { id: "", rows: [] }; // a file with one unnamed grid
      doc.frames.push(frame);
    }
    state = "frame";
    frame.rows.push(line);
  }
  for (const [k, v] of own) doc.palette.set(k, v); // a file's own keys win over its imports'
  doc.frames = doc.frames.filter((f) => f.rows.length);
  for (const f of doc.frames)
    for (const row of f.rows) for (const ch of row) if (ch !== "." && !doc.palette.has(ch)) doc.unknown.add(ch);
  return doc;
}

/**
 * Read a file and the palette files it imports, through `read` (a path in, its text out, or null),
 * with paths relative to the importing file as pxart resolves them. A variant renders the base
 * palette, then the imports' keys for that variant, then the file's own; a key the variant never
 * names keeps its base color.
 */
export function resolvePx(path: string, read: (path: string) => string | null, seen: Set<string> = new Set()): PxDoc {
  const text = read(path);
  if (text === null) throw new Error(`${path}: no such file`);
  const dir = path.includes("/") ? path.slice(0, path.lastIndexOf("/") + 1) : "";
  const imported = parsePx(text).imports.map((rel) => {
    const p = normalize(dir + rel);
    if (seen.has(p) || p === path) throw new Error(`${path}: @palette ${rel} imports itself`);
    return resolvePx(p, read, new Set([...seen, path]));
  });
  const doc = parsePx(text, imported.map((d) => d.palette));
  const own = doc.variants;
  doc.variants = new Map();
  for (const d of imported)
    for (const [name, keys] of d.variants) {
      const v = doc.variants.get(name) ?? new Map();
      for (const [k, c] of keys) v.set(k, c);
      doc.variants.set(name, v);
    }
  for (const [name, keys] of own) {
    const v = doc.variants.get(name) ?? new Map();
    for (const [k, c] of keys) v.set(k, c);
    doc.variants.set(name, v);
  }
  return doc;
}

function normalize(p: string): string {
  const out: string[] = [];
  for (const part of p.split("/")) {
    if (part === ".." && out.length && out[out.length - 1] !== "..") out.pop();
    else if (part === "..") out.push(part);
    else if (part && part !== ".") out.push(part);
  }
  return (p.startsWith("/") ? "/" : "") + out.join("/");
}

/** A frame as RGBA bytes, row by row (transparent pixels all zero). */
export function frameRgba(frame: PxFrame, pal: Map<string, Rgba>): { width: number; height: number; data: Uint8ClampedArray } {
  const width = Math.max(0, ...frame.rows.map((r) => r.length));
  const height = frame.rows.length;
  const data = new Uint8ClampedArray(width * height * 4);
  frame.rows.forEach((row, y) => {
    for (let x = 0; x < row.length; x++) {
      const c = pal.get(row[x]);
      if (row[x] === "." || !c || c[3] === 0) continue;
      data.set(c, (y * width + x) * 4);
    }
  });
  return { width, height, data };
}

/** The palette a variant renders: the base, with the variant's keys over it. */
export function paletteFor(doc: PxDoc, variant?: string): Map<string, Rgba> {
  const pal = new Map(doc.palette);
  if (variant) for (const [k, v] of doc.variants.get(variant) ?? []) pal.set(k, v);
  return pal;
}

export function hex([r, g, b, a]: Rgba): string {
  const h = (n: number) => n.toString(16).padStart(2, "0");
  return `#${h(r)}${h(g)}${h(b)}${a < 255 ? h(a) : ""}`;
}

/** An SVG of one frame, one <rect> per horizontal run of a color, at 1 unit per pixel. */
export function frameSvg(frame: PxFrame, pal: Map<string, Rgba>, opts: { title?: string; cls?: string; fit?: number } = {}): string {
  const w = Math.max(...frame.rows.map((r) => r.length));
  const h = frame.rows.length;
  // an integer scale that brings the larger side near `fit` px, so pixels stay square and crisp
  const k = opts.fit ? Math.max(1, Math.floor(opts.fit / Math.max(w, h))) : 1;
  const rects: string[] = [];
  frame.rows.forEach((row, y) => {
    let x = 0;
    while (x < row.length) {
      const ch = row[x];
      let end = x + 1;
      while (end < row.length && row[end] === ch) end++;
      const c = pal.get(ch);
      if (ch !== "." && c && c[3] > 0) {
        const op = c[3] < 255 ? ` fill-opacity="${(c[3] / 255).toFixed(3)}"` : "";
        rects.push(`<rect x="${x}" y="${y}" width="${end - x}" height="1" fill="${hex([c[0], c[1], c[2], 255])}"${op}/>`);
      }
      x = end;
    }
  });
  const title = opts.title ? `<title>${escapeHtml(opts.title)}</title>` : "";
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" width="${w * k}" height="${h * k}" ` +
    `shape-rendering="crispEdges" class="${opts.cls ?? "px-svg"}" role="img">${title}${rects.join("")}</svg>`
  );
}

/** Draw a frame onto a canvas at an integer scale. */
export function drawFrame(canvas: HTMLCanvasElement, frame: PxFrame, pal: Map<string, Rgba>, scale: number) {
  const w = Math.max(1, ...frame.rows.map((r) => r.length));
  const h = Math.max(1, frame.rows.length);
  canvas.width = w * scale;
  canvas.height = h * scale;
  const ctx = canvas.getContext("2d")!;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  frame.rows.forEach((row, y) => {
    for (let x = 0; x < row.length; x++) {
      const c = pal.get(row[x]);
      if (row[x] === "." || !c || c[3] === 0) continue;
      ctx.fillStyle = `rgba(${c[0]},${c[1]},${c[2]},${c[3] / 255})`;
      ctx.fillRect(x * scale, y * scale, scale, scale);
    }
  });
}

export function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ---- selectors: FILE.px:walk/down/0%dusk ----------------------------------------------------

export interface Selection {
  frames: PxFrame[];
  variant?: string;
  error?: string;
}

/** The frames and variant a selector names: `walk/down` (a group), `walk/down/0` (a frame), `*` or
 *  nothing (every frame), each optionally after `FILE.px:` and before `%variant`. */
export function select(doc: PxDoc, selector: string): Selection {
  let sel = selector.trim();
  const colon = sel.indexOf(":");
  if (colon >= 0 && /\.px$/i.test(sel.slice(0, colon))) sel = sel.slice(colon + 1);
  let variant: string | undefined;
  const pct = sel.lastIndexOf("%");
  if (pct >= 0) {
    variant = sel.slice(pct + 1) || undefined;
    sel = sel.slice(0, pct);
  }
  if (variant === "base") variant = undefined;
  if (variant && !doc.variants.has(variant))
    return { frames: [], error: `unknown variant '${variant}'${doc.variants.size ? `; variants: ${[...doc.variants.keys()].join(", ")}` : ""}` };
  if (!sel || sel === "*") return { frames: doc.frames, variant };
  const exact = doc.frames.filter((f) => f.id === sel);
  const group = doc.frames.filter((f) => f.id.startsWith(sel.replace(/\/$/, "") + "/"));
  const frames = exact.length ? exact : group;
  if (!frames.length) {
    const groups = [...new Set(doc.frames.map((f) => f.id.split("/").slice(0, -1).join("/")).filter(Boolean))];
    return { frames, error: `no frame or group '${sel}'${groups.length ? `; groups: ${groups.join(", ")}` : ""}` };
  }
  return { frames, variant };
}

// ---- maps: a legend, rows of legend characters, layers ------------------------------------

export interface MapItem {
  path: string;
  frame?: string;
  variant?: string;
  h: boolean;
  v: boolean;
  bottom: boolean;
  /** a variant list ('g grass.px:a grass.px:b grass.px:c'): each cell draws one, by cellHash */
  picks?: MapItem[];
}
export interface PxMap {
  legend: Map<string, MapItem>;
  layers: string[][];
}

/** Read a .map as pxart's scene --map does: legend lines `<char> <FILE[:frame][%variant][+h|+v|+b]>`
 *  (the rest of the line is the path; quotes optional), `#` comments before the first row, then
 *  rows of legend characters (`.` empty), with `---` starting another layer. */
export function parseMap(text: string): PxMap {
  const legend = new Map<string, MapItem>();
  const layers: string[][] = [[]];
  let inRows = false;
  let sawBlank = false;
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!inRows) {
      if (!line) {
        if (legend.size) sawBlank = true;
        continue;
      }
      if (line.startsWith("#")) continue;
      const m = /^(\S)\s+(.+)$/.exec(line);
      if (m && !sawBlank) {
        const picks = variantList(m[2]);
        legend.set(m[1], picks ? { ...picks[0], picks } : parseItem(m[2]));
        continue;
      }
      inRows = true;
    }
    if (!line) continue;
    if (line === "---") {
      layers.push([]);
      continue;
    }
    layers[layers.length - 1].push(line);
  }
  return { legend, layers: layers.filter((l) => l.length) };
}

// a legend token that names a tile, as pxart's MAP_TOKEN_RE: FILE.px[:frame] or FILE.png, then %variant and +flags
const MAP_TOKEN = /^.+\.(px(:[A-Za-z0-9_\-./]+)?|png)(%[A-Za-z0-9_\-]+)?(\+[hvb]{1,3})?(%[A-Za-z0-9_\-]+)?$/;

/** A legend line's rest as a variant list, when it is two or more tokens and every one names a tile
 *  (pxart's variant_list); else null: the rest is one path, spaces and all. */
function variantList(rest: string): MapItem[] | null {
  const toks = (rest.match(/"[^"]*"|\S+/g) ?? []).map((t) => t.replace(/^"(.*)"$/, "$1"));
  return toks.length > 1 && toks.every((t) => MAP_TOKEN.test(t)) ? toks.map(parseItem) : null;
}

/** pxart's cell_hash: which of a variant list's tiles cell x,y of a room draws. FNV-1a over the
 *  room's name (its file name without .map), mixed with the cell, then two xorshift-multiplies;
 *  unsigned 32-bit. scene --map, compose --map and export --tiled all pick with it. */
export function cellHash(room: string, x: number, y: number): number {
  let h = 2166136261;
  for (const b of new TextEncoder().encode(room)) h = Math.imul(h ^ b, 16777619) >>> 0;
  h = (h ^ (Math.imul(x, 73856093) >>> 0) ^ (Math.imul(y, 19349663) >>> 0)) >>> 0;
  h = Math.imul(h ^ (h >>> 13), 0x5bd1e995) >>> 0;
  return (h ^ (h >>> 15)) >>> 0;
}

function parseItem(spec: string): MapItem {
  let s = spec.trim();
  let flags = "";
  const f = /\+([hvb]+)$/.exec(s);
  if (f) {
    flags = f[1];
    s = s.slice(0, f.index);
  }
  let variant: string | undefined;
  const pct = s.lastIndexOf("%");
  if (pct > s.lastIndexOf("/")) {
    variant = s.slice(pct + 1);
    s = s.slice(0, pct);
  }
  let frame: string | undefined;
  const m = /^(.*\.(?:px|png))(?::(.+))?$/i.exec(s.replace(/^"(.*)"$/, "$1"));
  let path = s.replace(/^"(.*)"$/, "$1");
  if (m) {
    path = m[1];
    frame = m[2];
  }
  return { path: path.replace(/^"(.*)"$/, "$1"), frame, variant, h: flags.includes("h"), v: flags.includes("v"), bottom: flags.includes("b") };
}

export interface Rgba32 {
  width: number;
  height: number;
  data: Uint8ClampedArray;
}

/** Lay `src` over `dst` at x,y (straight alpha, "over"), clipped to dst. */
function over(dst: Rgba32, src: Rgba32, x0: number, y0: number, flipH = false, flipV = false) {
  for (let y = 0; y < src.height; y++) {
    const dy = y0 + y;
    if (dy < 0 || dy >= dst.height) continue;
    for (let x = 0; x < src.width; x++) {
      const dx = x0 + x;
      if (dx < 0 || dx >= dst.width) continue;
      const sx = flipH ? src.width - 1 - x : x;
      const sy = flipV ? src.height - 1 - y : y;
      const si = (sy * src.width + sx) * 4;
      const sa = src.data[si + 3];
      if (!sa) continue;
      const di = (dy * dst.width + dx) * 4;
      if (sa === 255) {
        dst.data.set(src.data.subarray(si, si + 4), di);
        continue;
      }
      const da = dst.data[di + 3] / 255;
      const a = sa / 255;
      const outA = a + da * (1 - a);
      for (let c = 0; c < 3; c++) dst.data[di + c] = Math.round((src.data[si + c] * a + dst.data[di + c] * da * (1 - a)) / outA);
      dst.data[di + 3] = Math.round(outA * 255);
    }
  }
}

/** Draw a map, its paths read relative to the map through `read`, on tiles of `tile` px. */
export function renderMap(mapPath: string, read: (path: string) => string | null, opts: { tile?: [number, number]; variant?: string } = {}): Rgba32 & { notes: string[] } {
  const [tw, th] = opts.tile ?? [16, 16];
  const text = read(mapPath);
  if (text === null) throw new Error(`${mapPath}: no such file`);
  const map = parseMap(text);
  const dir = mapPath.includes("/") ? mapPath.slice(0, mapPath.lastIndexOf("/") + 1) : "";
  const cols = Math.max(0, ...map.layers.flatMap((l) => l.map((r) => r.length)));
  const rows = Math.max(0, ...map.layers.map((l) => l.length));
  const out: Rgba32 & { notes: string[] } = { width: cols * tw, height: rows * th, data: new Uint8ClampedArray(cols * tw * rows * th * 4), notes: [] };
  const docs = new Map<string, PxDoc>();
  const room = mapPath.replace(/^.*\//, "").replace(/\.map$/i, "");
  const items = new Map<string, Rgba32 | null>();
  const imageOf = (ch: string, it: MapItem): Rgba32 | null => {
    const key = JSON.stringify([it.path, it.frame, it.variant]);
    if (items.has(key)) return items.get(key)!;
    let img: Rgba32 | null = null;
    if (/\.png$/i.test(it.path)) out.notes.push(`${it.path}: PNG items aren't drawn here (pxart draws them)`);
    else {
      try {
        const p = normalize(dir + it.path);
        if (!docs.has(p)) docs.set(p, resolvePx(p, read));
        const doc = docs.get(p)!;
        const sel = select(doc, it.frame ?? "");
        const wanted = it.variant ?? opts.variant;
        const variant = wanted === "base" ? undefined : wanted;
        if (variant && !doc.variants.has(variant))
          // pxart's scene stops here (E_SELECT); this draws the item in its base colors and says so
          out.notes.push(`legend '${ch}': ${it.path} has no variant '${variant}' (give it ${it.path}%base to keep its base colors)`);
        if (sel.error || !sel.frames.length) out.notes.push(`legend '${ch}': ${it.path}: ${sel.error ?? "no frames"}`);
        else if (sel.frames.length > 1)
          // as pxart: a legend entry is one frame (an animated tile names its first frame, water/0)
          out.notes.push(`legend '${ch}': '${it.path}${it.frame ? ":" + it.frame : ""}' is ${sel.frames.length} frames; pick one with FILE:frame-id`);
        else img = frameRgba(sel.frames[0], paletteFor(doc, variant && doc.variants.has(variant) ? variant : undefined));
      } catch (e) {
        out.notes.push(String((e as Error).message ?? e));
      }
    }
    items.set(key, img);
    return img;
  };
  const missing = new Set<string>();
  for (const layer of map.layers)
    layer.forEach((row, r) => {
      [...row].forEach((ch, c) => {
        if (ch === ".") return;
        const entry = map.legend.get(ch);
        if (!entry) {
          if (!missing.has(ch)) out.notes.push(`'${ch}' isn't in the legend`);
          missing.add(ch);
          return;
        }
        const it = entry.picks ? entry.picks[cellHash(room, c, r) % entry.picks.length] : entry;
        const img = imageOf(ch, it);
        if (!img) return;
        const x = it.bottom ? c * tw + Math.floor((tw - img.width) / 2) : c * tw;
        const y = it.bottom ? r * th + th - img.height : r * th;
        over(out, img, x, y, it.h, it.v);
      });
    });
  return out;
}

/** Draw RGBA onto a canvas at an integer scale. */
export function drawRgba(canvas: HTMLCanvasElement, img: Rgba32, scale: number) {
  canvas.width = Math.max(1, img.width) * scale;
  canvas.height = Math.max(1, img.height) * scale;
  const ctx = canvas.getContext("2d")!;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!img.width || !img.height) return;
  const tmp = new ImageData(new Uint8ClampedArray(img.data), img.width, img.height);
  const off = document.createElement("canvas");
  off.width = img.width;
  off.height = img.height;
  off.getContext("2d")!.putImageData(tmp, 0, 0);
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(off, 0, 0, canvas.width, canvas.height);
}

/** Several frames side by side, bottom-aligned, with `gap` px between: a sheet, as one image. */
export function sheetRgba(frames: Rgba32[], gap = 4, maxWidth = 200): Rgba32 {
  const rowsOf: Rgba32[][] = [[]];
  let w = 0;
  for (const f of frames) {
    if (rowsOf[rowsOf.length - 1].length && w + gap + f.width > maxWidth) {
      rowsOf.push([]);
      w = 0;
    }
    w += (rowsOf[rowsOf.length - 1].length ? gap : 0) + f.width;
    rowsOf[rowsOf.length - 1].push(f);
  }
  const rowW = rowsOf.map((r) => r.reduce((s, f) => s + f.width, 0) + gap * Math.max(0, r.length - 1));
  const rowH = rowsOf.map((r) => Math.max(0, ...r.map((f) => f.height)));
  const out: Rgba32 = { width: Math.max(0, ...rowW), height: rowH.reduce((a, b) => a + b, 0) + gap * Math.max(0, rowsOf.length - 1), data: new Uint8ClampedArray(0) };
  out.data = new Uint8ClampedArray(out.width * out.height * 4);
  let y = 0;
  rowsOf.forEach((r, i) => {
    let x = 0;
    for (const f of r) {
      over(out, f, x, y + rowH[i] - f.height);
      x += f.width + gap;
    }
    y += rowH[i] + gap;
  });
  return out;
}
