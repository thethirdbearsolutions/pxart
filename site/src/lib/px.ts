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

const KEY_LINE = /^(\S)\s+(#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?|transparent)\b(.*)$/;

export function parseColor(text: string): Rgba | null {
  if (text === "transparent") return [0, 0, 0, 0];
  const m = /^#([0-9a-fA-F]{6})([0-9a-fA-F]{2})?$/.exec(text);
  if (!m) return null;
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255, m[2] ? parseInt(m[2], 16) : 255];
}

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
  let variant: Map<string, Rgba> | null = null;
  let frame: PxFrame | null = null;

  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trimEnd();
    if (!line.trim() || line.startsWith("#")) {
      if (frame && frame.rows.length) frame = frame.id ? frame : null;
      continue;
    }
    if (/^pxart\s+\d+$/.test(line)) continue;
    if (line.startsWith("@")) {
      const [word, arg = "", ...rest] = line.split(/\s+/);
      variant = null;
      if (word === "@palette") doc.imports.push(line.slice(word.length).trim());
      else if (word === "@variant") {
        variant = doc.variants.get(arg) ?? new Map();
        doc.variants.set(arg, variant);
      } else if (word === "@frame") {
        const ms = rest.map((r) => /^ms=(\d+)$/.exec(r)).find(Boolean);
        frame = { id: arg, rows: [], ms: ms ? Number(ms[1]) : undefined };
        doc.frames.push(frame);
      } else if (word === "@anim") {
        const ms = rest.map((r) => /^ms=(\d+)$/.exec(r)).find(Boolean);
        doc.anims.set(arg, { ms: ms ? Number(ms[1]) : undefined });
      }
      continue;
    }
    const key = KEY_LINE.exec(line);
    if (key && !(frame && frame.rows.length)) {
      const color = parseColor(key[2]);
      if (color) (variant ?? doc.palette).set(key[1], color);
      continue;
    }
    if (/^\S+$/.test(line)) {
      variant = null;
      if (!frame) {
        frame = { id: "", rows: [] };
        doc.frames.push(frame);
      }
      frame.rows.push(line);
    }
  }
  doc.frames = doc.frames.filter((f) => f.rows.length);
  for (const f of doc.frames)
    for (const row of f.rows) for (const ch of row) if (ch !== "." && !doc.palette.has(ch)) doc.unknown.add(ch);
  return doc;
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
