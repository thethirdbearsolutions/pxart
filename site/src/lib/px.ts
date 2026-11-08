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
