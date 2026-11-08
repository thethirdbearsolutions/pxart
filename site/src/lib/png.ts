// A minimal PNG encoder (8-bit RGBA, no filtering), for images the build makes from .px
// sprites: blog posts' preview cards. Node only (it uses zlib).
import { deflateSync } from "node:zlib";
import type { Rgba32, Rgba } from "./px";

const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();

function crc32(bytes: Uint8Array): number {
  let c = 0xffffffff;
  for (const b of bytes) c = CRC_TABLE[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function chunk(type: string, data: Uint8Array): Uint8Array {
  const out = new Uint8Array(12 + data.length);
  const view = new DataView(out.buffer);
  view.setUint32(0, data.length);
  out.set(new TextEncoder().encode(type), 4);
  out.set(data, 8);
  view.setUint32(8 + data.length, crc32(out.subarray(4, 8 + data.length)));
  return out;
}

export function encodePng(img: Rgba32): Uint8Array {
  const { width, height, data } = img;
  const raw = new Uint8Array((width * 4 + 1) * height);
  for (let y = 0; y < height; y++) raw.set(data.subarray(y * width * 4, (y + 1) * width * 4), y * (width * 4 + 1) + 1);
  const ihdr = new Uint8Array(13);
  const v = new DataView(ihdr.buffer);
  v.setUint32(0, width);
  v.setUint32(4, height);
  ihdr.set([8, 6, 0, 0, 0], 8); // 8-bit, RGBA, deflate, no filter, no interlace
  const parts = [new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", ihdr), chunk("IDAT", deflateSync(raw)), chunk("IEND", new Uint8Array(0))];
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let o = 0;
  for (const p of parts) (out.set(p, o), (o += p.length));
  return out;
}

/** A preview card: `art` scaled up by the largest integer that fits, centred on a flat ground. */
export function card(art: Rgba32, opts: { width?: number; height?: number; ground?: Rgba; maxArt?: number } = {}): Rgba32 {
  const W = opts.width ?? 1200;
  const H = opts.height ?? 630;
  const ground = opts.ground ?? [239, 230, 210, 255];
  const room = opts.maxArt ?? 0.72;
  const k = Math.max(1, Math.floor(Math.min((W * room) / Math.max(1, art.width), (H * room) / Math.max(1, art.height))));
  const out = new Uint8ClampedArray(W * H * 4);
  for (let i = 0; i < W * H; i++) out.set(ground, i * 4);
  const ox = Math.floor((W - art.width * k) / 2);
  const oy = Math.floor((H - art.height * k) / 2);
  for (let y = 0; y < art.height; y++)
    for (let x = 0; x < art.width; x++) {
      const si = (y * art.width + x) * 4;
      const a = art.data[si + 3] / 255;
      if (!a) continue;
      for (let dy = 0; dy < k; dy++)
        for (let dx = 0; dx < k; dx++) {
          const di = ((oy + y * k + dy) * W + ox + x * k + dx) * 4;
          for (let c = 0; c < 3; c++) out[di + c] = Math.round(art.data[si + c] * a + out[di + c] * (1 - a));
        }
    }
  return { width: W, height: H, data: out };
}
