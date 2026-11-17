# The load bench: how fast a web game can load a cast

This bench measures how long a browser game takes to load and draw a cast of sprites. It compares
shipping the cast as PNGs or WebPs (one file per frame, or one sheet per character) with shipping
the `.px` sources and drawing them with [`js/px.ts`](../../js/px.ts). It runs in Chromium, under
throttled networks and an emulated phone.

```
uv run bench/load/run.py --out bench/load/results/my-run
```

That one command does everything:
- draws a synthetic cast (`make_cast.py`);
- builds it in each option (`build.py`) and optimises the images (`optimize.py`);
- checks that every option draws the same pixels as pxart's render (`bench.py --parity`);
- loads every option three times per profile with a cold cache (`bench.py`);
- writes a summary (`summarize.py`).

It needs:
- [uv](https://docs.astral.sh/uv/), which installs Pillow, pyoxipng, brotli and Playwright for the run;
- node 22.18 or newer;
- openssl;
- a Chromium for Playwright. If you have none, run
  `uv run --with playwright==1.63.0 playwright install chromium` once.

A full run took about an hour and a half on a 4-core cloud VM. About an hour of that is zopfli on
every per-frame PNG; the 495 page loads of the 11 options take about half an hour. To narrow it:

```
uv run bench/load/run.py --out bench/load/results/quick --scenarios s300 --profiles desktop,desktop-20mbps --runs 1
```

## The cast

`make_cast.py` draws five characters from code: a fox, an owl, a knight, a wizard and a sprite. It
works from fixed seeds, so every run builds the same files. They share one `palette.px`.

| scenario | frames | palette variants | what it is |
|---|---|---|---|
| s300 | 300 | none | 60 frames each: idle and walk in four facings, then hurt, sit, attack-with-light, eat, jump and make-a-slash facing down |
| s300v2 | 300 (900 drawn) | dawn, dusk | the same, with two palette variants |
| s650v2 | 645 (1,935 drawn) | dawn, dusk | the four one-facing actions gain up, left and right facings (mirrored or shifted copies of down) |

The art is simple: shaded ellipses and rectangles, outlined, with a little texture. It compresses
better than hand-drawn art. The first runs of this bench used a private cast of the same shape:
the `.px` text was 3.0 MB at s300, 58 KB under brotli, where this one is 36 KB. So compare options
within one run, not numbers across casts or machines.

## The options

Each option is built from the same cast. Every option's manifest lists the same entries in the
same order.

| option | what a game fetches |
|---|---|
| `frames` | one PNG per frame per palette, as Pillow saves them |
| `frames.oxi` | the same, as palette PNGs through oxipng `-o6` with zopfli |
| `frames.webp` | the same, as lossless WebP (libwebp through Pillow: quality 100, method 6) |
| `atlas`, `.oxi`, `.webp` | one sheet per character per palette (1 px gaps, rows 1,024 wide) |
| `atlas+`, `.oxi`, `.webp` | the base palette's sheets only, recoloured in the page for each variant |
| `render` | the `.px` files, drawn by `js/px.ts` into one sheet per character per palette |
| `render.gzip` | the same, served gzip only |

`optimize.py` decodes every optimised image and checks it against the original's RGBA, byte for
byte. The parity page then draws every entry from every option in Chromium and compares the
pixels with pxart's per-frame PNGs.

## How a run loads

`web/server.mjs` serves over HTTP/2 and TLS the way a CDN does: text is brotli (quality 11), images
go as they are, and nothing is cached. The page (`web/game.html`) loads the pack and records four
things:
- when it could first draw a sprite;
- when it had drawn every sprite once;
- the runtime's own timings and the decoded bitmap bytes;
- the JS heap.

The driver adds:
- the page's main-thread task and script time, from Chrome's metrics;
- the requests and bytes received.

| profile | network | CPU |
|---|---|---|
| desktop | none | desktop |
| desktop-100mbps | 100 Mbps down, 20 up, 20 ms RTT | desktop |
| desktop-20mbps | 20 Mbps down, 5 up, 40 ms RTT | desktop |
| desktop-4g | Lighthouse's 4G: 1.6 Mbps down, 750 kbps up, 150 ms RTT | desktop |
| mobile | the same 4G | Playwright's Pixel 7, CPU throttled 4× |

Chrome's CPU throttle slows only the page's main thread. Chromium decodes images on other threads,
and the throttle doesn't reach them, so on the phone profile options that decode images are
flattered against options that work in JavaScript on the main thread. It can't throttle a Web
Worker either, so the PXC1 options (`bench/cast/`) pass the rate to their worker, which emulates it.

## Results

[`results/`](results/) has every run published so far, raw, each with a README naming its
machine, browser, cast and profiles:
- `games-417/` and `games-422/` used the private cast;
- `games-427/` used this one.
