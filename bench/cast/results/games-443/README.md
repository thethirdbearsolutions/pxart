# GAMES-443: whole-cast compression (17 Nov 2026)

GAMES-443 asked whether one format could beat recoloured WebP sheets and `.px` + brotli. The
format would exploit what repeats between frames and between variants, and a Web Worker would do
the drawing. This folder holds the raw results. The format, PXC1, is in `../../`.

## Verdict

**PXC1 beats `.px` + brotli everywhere here.** It is smaller, draws first sooner on every cast
and profile, and uses a fraction of the main thread.

**Against sheets, it trades bytes for start-up.**
- It is smaller than recoloured WebP sheets by 61–71%, and it draws first sooner whenever the
  cast has variants: at s300v2 and s650v2, on every profile.
- Plain sheets draw first sooner on a fast desktop link (unthrottled and 100 Mbps) at every
  size. At s300, which has no variants, sheets draw first sooner at 100 Mbps and faster, and are
  even at 20 Mbps.
- On 4G and the phone, PXC1 draws first sooner than every sheet option on every cast.

**Where axes multiply, PXC1 holds its size and switches fastest.** With 12 palettes × 9 damage ×
expression states:
- PXC1 is 33.6 KB for all 108 combinations, up from 32.7 KB for one.
- To have every combination on hand, a game ships 9 MB of WebP sheets (541 files) or 758 KB of
  recoloured sheets.
- A game that shows one combination at a time fetches only that one's sheets. On fast links
  those draw first sooner than PXC1 or level with it: 46–154 against 63–161 ms. On 4G and the
  phone they are slower: 751–810 against 528–612 ms.
- Switching to another time of day, season and state takes PXC1 41–47 ms on the desktop
  profiles and 123 ms on the phone. Sheets take 70–164 ms on fast links and 619–931 ms on 4G and
  the phone, because they fetch new files.

**What made it smaller: raw indices.** The format leaves the compressing to brotli:
- one byte per pixel, in one index space for the cast;
- headers apart from the pixels;
- columns rather than rows.

**Frame deltas are a null result.** Brotli already finds what repeats between frames. Every delta
coding tried made the file bigger than plain `.px`, not smaller:
- XOR with the previous frame: 2.4–2.5× the `.px`;
- row ops against the previous frame and the row above: 1.7–2.2× the `.px`.

**Column order helps a little, and more on copied frames.** It is 5% smaller than row order at
s300 and 10% at s650v2. s650v2's extra facings are exact mirrors and shifts of the down frames,
which columns line up for brotli, so hand-drawn facings would gain less.

**The worker keeps the main thread free.** At s650v2, PXC1's main thread does 112 ms of work
unthrottled and 468 ms on the phone:
| option | main thread, unthrottled | main thread, phone |
|---|---|---|
| PXC1 (worker) | 112 ms | 468 ms |
| sheets, oxipng | 162 ms | 804 ms |
| sheets, WebP | 237 ms | 1,036 ms |
| sheets + recolour, WebP | 350 ms | 1,592 ms |
| `.px` | 754 ms | 3,573 ms |

A whole-cast palette blend takes 146 ms in the worker on the phone, off the main thread, against
611 ms on it for `.px`. Decoding PXC1 on the main thread instead (`pxc.main`) is about as fast
unthrottled (221 against 246 ms at s650v2), but slower on the phone (1,481 against 1,133 ms).

**How the phone was emulated:**
- Chromium's CPU throttle reaches only the page's main thread. It can't throttle a worker at all
  ("Operation is only supported for pages, not workers").
- So on the phone profile, the worker throttles itself. After each of its own synchronous steps
  (decode, palette, painting each sheet) it spins for 3× that step's time. Its paint goes from
  189 ms unthrottled to 508 ms.
- Neither throttle reaches the threads Chromium decodes images or makes `ImageBitmap`s on.
  That flatters sheets as much as it flatters the worker.
- The worker is started, and its code loaded, before the clock starts, as every other option's
  code is.

**Serving it:** PXC1 needs the host to serve it brotli-compressed.
- Chromium 153's DecompressionStream has no brotli.
- Where a host won't compress `.pxc`, ship `cast.pxc.gz`; the worker gunzips it.
- As gzip it is about 3× bigger (190 KB at s650v2) and loses its lead on 4G: 1,510 ms at s650v2.

**Parity:**
- In node: every frame × palette × combination PXC1 decodes is pixel-identical to pxart's render,
  sizes included (`parity-node.jsonl`). That is 300, 900, 1,935 and 32,400 frames. The last is
  every combination of the axes cast, against pxart's render of the same frames baked.
- In Chromium: all 3 PXC1 options draw every entry as pxart's PNGs (`load/parity.jsonl`).
  Plain lossless WebP draws translucent pixels up to 2 levels off. That is GAMES-427's finding,
  seen here again.

**Caveats:**
- The casts are synthetic and compress better than hand-drawn art.
- The axes cast's overlays and anchors come from its generator. pxart has no layers or anchors to
  export, so a real cast would need them drawn.
- It ran on one machine and one browser: a 4-core 2.1 GHz Xeon cloud VM and Chromium 153
  (`load/machine.json`).
- The code (`.js`, the worker) isn't counted in any option's bytes. The main-thread heap isn't
  reported, because it can't see the worker's heap.

## How it was run

- **Load bench session:** in `load/`, 06:15–06:28 UTC.
  - Command: `uv run bench/load/run.py --out bench/cast/results/games-443/load --keep-work --options pxc,pxc.gzip,pxc.main,render,atlas+.webp,atlas.webp,atlas.oxi`.
  - Load bench casts, its five profiles, 3 cold runs each, 315 page loads, none failed.
  - The casts and images are the ones GAMES-427 built, so their bytes match.
- **Axes runs:** right after, on the same machine and browser.
  - Command: `bench/cast/bench_axes.py`.
  - 60 page loads, none failed.
- **First runs, superseded:** GAMES-427's session timed PXC1 first. Those runs didn't throttle the
  worker and loaded its code inside the timed window. This session replaces them.


#### s650v2: first draw, ms (median of 3)

| option | KB on the wire | desktop | 100 Mbps | 20 Mbps | 4G | phone |
|---|---|---|---|---|---|---|
| PXC1, brotli, worker | 49 | 246 | 282 | 330 | 803 | 1133 |
| PXC1, brotli, main thread | 49 | 221 | 252 | 340 | 776 | 1481 |
| PXC1, gzip, worker | 190 | 241 | 295 | 382 | 1510 | 1854 |
| .px, brotli | 73 | 518 | 574 | 685 | 1175 | 2971 |
| sheets + recolour, WebP | 167 | 314 | 345 | 466 | 1417 | 2323 |
| sheets, WebP | 474 | 158 | 224 | 383 | 2750 | 2824 |
| sheets, oxipng | 656 | 99 | 169 | 398 | 3663 | 3695 |

#### s300v2: first draw, ms (median of 3)

| option | KB on the wire | desktop | 100 Mbps | 20 Mbps | 4G | phone |
|---|---|---|---|---|---|---|
| PXC1, brotli, worker | 34 | 117 | 169 | 224 | 596 | 742 |
| PXC1, brotli, main thread | 34 | 120 | 155 | 206 | 591 | 948 |
| PXC1, gzip, worker | 96 | 119 | 164 | 242 | 899 | 1076 |
| .px, brotli | 41 | 259 | 304 | 345 | 748 | 1535 |
| sheets + recolour, WebP | 88 | 173 | 214 | 272 | 906 | 1407 |
| sheets, WebP | 254 | 92 | 153 | 256 | 1838 | 1694 |
| sheets, oxipng | 294 | 73 | 123 | 245 | 1888 | 1879 |

#### s300: first draw, ms (median of 3)

| option | KB on the wire | desktop | 100 Mbps | 20 Mbps | 4G | phone |
|---|---|---|---|---|---|---|
| PXC1, brotli, worker | 32 | 60 | 104 | 160 | 521 | 599 |
| PXC1, brotli, main thread | 32 | 79 | 110 | 160 | 513 | 720 |
| PXC1, gzip, worker | 92 | 63 | 107 | 180 | 817 | 911 |
| .px, brotli | 39 | 172 | 235 | 257 | 666 | 1113 |
| sheets + recolour, WebP | 85 | 43 | 85 | 156 | 762 | 808 |
| sheets, WebP | 85 | 41 | 87 | 152 | 771 | 812 |
| sheets, oxipng | 99 | 36 | 85 | 153 | 837 | 864 |

#### s650v2: main-thread task time, worker paint and palette blend (median of 3)

| option | main thread ms, desktop | main thread ms, phone | paint ms, desktop / phone | whole-cast palette blend ms, desktop / phone |
|---|---|---|---|---|
| PXC1, brotli, worker | 112 | 468 | 189 / 508 | 58 / 146 |
| PXC1, brotli, main thread | 341 | 1646 | 157 / 760 | 50 / 233 |
| PXC1, gzip, worker | 100 | 421 | 194 / 516 | 56 / 149 |
| .px, brotli | 754 | 3573 | 285 / 1303 | 137 / 611 |
| sheets + recolour, WebP | 350 | 1592 | — | — |
| sheets, WebP | 237 | 1036 | — | — |
| sheets, oxipng | 162 | 804 | — | — |

#### Bytes as the axes multiply (KB: images as they are, text and .pxc brotli; every file the option needs for every combination)

| combinations | palettes | overlay states | frames pxart renders | sheets, WebP | sheets + recolour, WebP | .px | PXC1 |
|---|---|---|---|---|---|---|---|
| 1 | 1 | 1 | 300 | 85 (6 files) | 85 (6 files) | 39.2 | 32.7 |
| 3 | 3 | 1 | 900 | 253 (16 files) | 86 (6 files) | 39.6 | 32.7 |
| 12 | 12 | 1 | 3,600 | 1,007 (61 files) | 87 (6 files) | 40.8 | 32.8 |
| 36 | 12 | 3 | 10,800 | 3,010 (181 files) | 254 (16 files) | 52.2 | 33.2 |
| 108 | 12 | 9 | 32,400 | 9,051 (541 files) | 758 (46 files) | 67.7 | 33.6 |

#### All 108 combinations: first draw / switch, ms (median of 3)

| option | desktop | 100 Mbps | 20 Mbps | 4G | phone | main thread ms, phone | KB fetched (both views) |
|---|---|---|---|---|---|---|---|
| PXC1, worker | 63 / 42 | 111 / 41 | 161 / 42 | 528 / 47 | 612 / 123 | 259 | 34 |
| .px | 1050 / 53 | 966 / 47 | 1024 / 48 | 1518 / 47 | 4448 / 216 | 4390 | 68 |
| sheets + recolour, WebP | 47 / 112 | 87 / 121 | 153 / 164 | 771 / 628 | 810 / 931 | 790 | 171 |
| sheets, WebP | 46 / 70 | 90 / 89 | 154 / 127 | 751 / 619 | 796 / 726 | 539 | 169 |

#### What each coding is worth after brotli (KB; pixels only, except the .px and PXC1 rows)

| coding | s300 | s300v2 | s650v2 |
|---|---|---|---|
| .px, a file per character (as served) | 37.7 | 38.1 | 67.2 |
| .px, one file for the cast | 36.4 | 36.6 | 65.5 |
| palette indices, rows | 31.7 | 31.7 | 46.5 |
| palette indices, columns | 30.3 | 30.3 | 41.6 |
| palette indices, rows, an index space per character | 31.9 | 31.9 | 46.6 |
| each frame XOR the previous frame | 95.8 | 95.8 | 162.0 |
| row ops with frame deltas, rows | 70.4 | 70.4 | 124.3 |
| row ops with frame deltas, columns | 83.2 | 83.2 | 112.7 |
| row ops without frame deltas | 55.6 | 55.6 | 99.4 |
| PXC1 file (columns) | 30.8 | 31.2 | 42.8 |
| PXC1 file (rows) | 32.3 | 32.8 | 47.8 |

## Files

| file | what it is |
|---|---|
| `load/` | the load bench session: `bench.jsonl` (one line per page load), `sizes.json`, `parity.jsonl`, `bench-summary.md`, `machine.json` |
| `axes-bench.jsonl` | the 108-combination cast in Chromium: load, draw, switch, draw, 3 runs per option per profile (`../../bench_axes.py`) |
| `axes-bytes.jsonl` | the axes casts' bytes per option, from 1 combination to 108 (`../../build_axes.py`) |
| `ablation.jsonl` | bytes after brotli for each coding idea, per cast (`../../ablation.py`) |
| `parity-node.jsonl` | PXC1 against pxart, every frame × palette (× combination), per cast (`../../parity.py`) |
