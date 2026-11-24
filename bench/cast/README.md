# Whole-cast compression: a spike

The question: how small and how fast can a whole cast get if one format exploits what repeats
between frames and between variants, and a Web Worker does the drawing? The spike tried four
ideas:
- frame deltas;
- layered overlays instead of baked combinations;
- palette axes as data;
- one file for the whole cast.

It measured them on [the load bench](../load/README.md), against that bench's options.

This folder is the format (PXC1), its encoder, its decoder, and a browser build of the decoder.
The browser build is plain ES modules, nothing to compile:

| file | what it is |
|---|---|
| `pxc.py` | the encoder: a cast's `.px` files (and a layered cast's `layers.json`) to one `.pxc` |
| `web/pxc.js` | the decoder: no DOM, so it runs in a worker, on the main thread or under node |
| `web/pxc-worker.js` | the worker: fetches, decodes and paints sheets, and hands back `ImageBitmap`s |
| `web/pxc-client.js` | the page's side: `loadPxc(url, { palettes, combo, worker })`, `paint(...)` |
| `parity.py`, `web/pxc-dump.mjs` | every frame × palette (× combination) decoded under node, against pxart's render |
| `make_axes.py` | the load bench's cast in 3 times of day × 4 seasons × 3 damage states × 3 expressions |
| `build_axes.py`, `bench_axes.py`, `web/axes.*` | that cast built four ways, its bytes, and a page that loads and switches combinations |
| `build_pxc.py` | the `pxc`, `pxc.gzip` and `pxc.main` options for the load bench |

To make a cast, put one `.px` file per character in a flat folder, each named after its character
(`fox.px` is the character `fox`; subfolders aren't read, and a palette-only file, such as a shared
`palette.px` the characters import, is skipped), then:

```
python3 bench/cast/pxc.py CAST_DIR cast.pxc
```

A folder with no character files directly in it (empty, or the files one level down) is an error, not an
empty cast.
A cast has one palette:
- every key the cast draws has one color in every file that has it, in the base and in each variant;
- every file has every variant, its own or through `@palette`.

The simplest way is one shared palette file that every character imports. A file needn't list keys it
doesn't draw, so `pxart check`'s unused-key advice (`palette --remove`) is safe to follow. A key colored
two ways, or a variant one file lacks, stops the encoder with a message naming the key and the files:
`PXC1 needs one palette for the whole cast: key 'k' in the base differs between files (fox.px #1b1420,
owl.px #2b1d32); give it one color in every file that has it`.

To load a cast in a page, put the three `web/pxc*.js` files beside it:

```js
import { loadPxc } from './pxc-client.js';

const cast = await loadPxc('cast.pxc', { palettes: ['', 'dusk'] });  // decoded in a worker
const sheet = cast.sheets.get('dusk/fox');                            // an ImageBitmap
const [x, y, w, h] = cast.rects.get('fox:walk/down/0');
ctx.drawImage(sheet, x, y, w, h, 100, 100, w, h);
await cast.paint({ blend: { from: '', to: 'dusk', amount: 0.3 } });  // any blend, repainted in the worker
```

Serve the `.pxc` brotli-compressed, as you would `.px`: the format leaves the byte-level
compression to brotli. Hosts compress only the types they know. Where a host won't compress
`.pxc`, gzip it yourself (`gzip -9 -k cast.pxc`) and load `cast.pxc.gz`: the worker gunzips it
with DecompressionStream. `cast.bytes` is the size of the decoded PXC1 (after any gunzip), not the bytes
on the wire; for those, read the response size (the load bench records it per run). It goes by the bytes, not the URL: what arrives still gzipped (it starts
`1f 8b`) is gunzipped, so `cast.pxc.gz?r=2` works, and a `.gz` a server has already decoded isn't
gunzipped twice. Chromium's DecompressionStream has no brotli. The gzip file is about 3×
the brotli size.

## PXC1

`pxc.py`'s docstring has the layout. In short:
- headers first;
- then every frame's pixels as raw palette indices, one byte each, column by column, in one
  plane for the whole cast;
- one palette for the cast: a table per variant, or, for a layered cast, the base table and the
  axes as numbers (each axis value is a multiply and an add per channel);
- a layered cast stores its damage and expression overlays once per character, with each frame's
  head and body anchors.

## Results

[`results/games-443/`](results/games-443/README.md) has the verdict, the tables and the raw
results. In short:
- PXC1 beats `.px` + brotli everywhere here: 17–33% smaller, first to draw sooner on every cast
  and profile, and a fraction of its main-thread time.
- It is 61–71% smaller than recoloured WebP sheets.
  - With variants, it draws first sooner than them on every profile.
  - On 4G and the emulated phone, it draws first sooner than every sheet option.
  - Plain sheets still draw first sooner on a fast desktop link.
- Frame deltas are a null result. Brotli already finds what repeats between frames, and delta
  coding made files bigger.
- The gains come from three things: raw indices, palettes as data, and overlays drawn instead of
  baked. All 108 combinations of a 12-palette, 9-state cast are 33.6 KB, against 68 KB of `.px`
  and 9 MB of WebP sheets. It switches combination in 41–123 ms.
