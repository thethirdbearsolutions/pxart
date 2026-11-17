# GAMES-427: desktop broadband, beside 4G and the phone (17 Nov 2026)

GAMES-417 and GAMES-422 timed three profiles: an unthrottled desktop, a desktop on Lighthouse's
4G, and an emulated phone. Typical desktop broadband falls between the first two, so this run adds
two profiles in between: 20 Mbps and 100 Mbps. It times all five profiles again in one session,
on a different machine and a different cast from the earlier runs. **Compare numbers only within
this run.**

- **Machine:** a cloud VM.
  - CPU: Intel Xeon @ 2.10 GHz, 4 cores;
  - memory: 15.7 GB;
  - OS: Ubuntu 24.04 (Linux 6.18, x86_64).

  It is slower than the Apple Silicon Mac the earlier runs used. Drawing `.px` at s650v2 took
  545 ms here unthrottled, against 265 ms there, though the casts differ too.
- **Software:**
  - Chromium 153.0.8010.12 (headless, Playwright 1.63.0);
  - node 22.23.4, Python 3.13.18;
  - Pillow 13.0.0 (libwebp 1.6.0), pyoxipng 9.1.1.
- **Cast:** the synthetic one from `../../make_cast.py` (s300, s300v2, s650v2), not the private
  cast of GAMES-417 and GAMES-422.
- **Profiles:**

  | profile | network | CPU |
  |---|---|---|
  | `desktop` | none | desktop |
  | `desktop-100mbps` | 100 Mbps down / 20 up, 20 ms RTT | desktop |
  | `desktop-20mbps` | 20 Mbps down / 5 up, 40 ms RTT | desktop |
  | `desktop-4g` | 1.6 Mbps / 750 kbps, 150 ms | desktop |
  | `mobile` | the same 4G | Pixel 7, CPU throttled 4× |
- **Throttling:** Chrome's CPU throttle slows the page's main thread only. Chromium decodes
  images on other threads, which it doesn't reach, in this run as in GAMES-417 and GAMES-422. So
  on the phone profile, options that decode images (per-frame, sheets) are flattered against
  options that do their work in JavaScript on the main thread (`.px`, recolouring).
- **Options:** GAMES-422's 11. The session also timed GAMES-443's three PXC1 options, but those
  rows are superseded: their worker wasn't throttled on the phone profile and loaded its code
  inside the timed window. GAMES-443 timed them again in a session of its own
  (`../../../cast/results/games-443/`). The tables below leave them out.
- **Runs:** 3 cold-cache runs of each, 630 page loads in 35 minutes (05:01–05:36 UTC), none failed.
- **Commands:**
  - this folder: `uv run bench/load/run.py --out bench/load/results/games-427 --options <the 11, and pxc,pxc.gzip,pxc.main>`;
  - the casts and optimised images were built earlier in the same session, so it ran with
    `--keep-work`;
  - `optimize.jsonl` is that earlier build's log.

## What changed the order

**At 20 and 100 Mbps, sheets draw first among GAMES-422's 11 options, in every scenario.**
`.px` brotli is behind every sheet option.
- At s650v2: 616 ms at 20 Mbps against 393–451 ms for the sheets, and 567 ms at 100 Mbps against
  164–349 ms.
- On 4G it is the other way round, in every scenario: `.px` brotli beats every image option.
  At s650v2 that is 1,196 ms against 1,397 ms for the best image option, sheets + recolour as WebP.
- So the crossover is somewhere between 1.6 and 20 Mbps. Nothing in between was run.

**On the phone profile, `.px` brotli isn't first here.**
- At s650v2, four sheet options beat it (2,969 ms): sheets + recolour as WebP (2,287 ms), as
  oxipng (2,508 ms) and as Pillow PNG (2,717 ms), and plain WebP sheets (2,838 ms).
- On GAMES-422's machine and cast, `.px` was first (1,824 against 1,893 ms).
- Here, parsing and drawing the `.px` costs about twice the CPU, and the 4× throttle multiplies
  that. So the phone result depends on the CPU, and this machine is slow.

**Per-frame files stay last everywhere.** On the desktop profiles, the best sheet option draws first 2.8× sooner than the best per-frame option (s300 at 20 Mbps), rising to 26× sooner (s650v2 unthrottled).

**Two stalls:**
- Two runs of s300 per-frame WebP at 100 Mbps stalled for about 40 s in fetching. The third
  took 412 ms. That cell was run again: `rerun-s300-frames-webp-100mbps.jsonl`, 383–405 ms.
- One run of s300v2 per-frame PNG at 100 Mbps stalled the same way. Its median is unaffected.
- Both are left in `bench.jsonl` as recorded.

**Parity:** in the browser, every option draws every entry exactly as pxart's PNGs, except
per-frame WebP and plain WebP sheets. Chromium draws their translucent pixels up to 2 levels
off per channel. Recoloured WebP sheets are identical, because the recolour rewrites those
pixels from the map.
- That is 60 of 900 entries at s300v2 and 240 of 1,935 at s650v2: the frames with a 50% alpha
  glow, in the dawn and dusk variants.
- Pillow decodes the same files to identical RGBA (`optimize.jsonl`).
- See `parity.jsonl`.


### s650v2: first draw, ms (median [min–max] of 3 cold runs)

| option | KB | requests | desktop, no throttle | 100 Mbps / 20 ms | 20 Mbps / 40 ms | 4G (1.6 Mbps / 150 ms) | phone (Pixel 7, 4× CPU, 4G) |
|---|---|---|---|---|---|---|---|
| sheets, WebP | 474 | 16 | 152 [139–162] | 217 | 393 | 2752 | 2838 [2805–2991] |
| sheets, oxipng | 656 | 16 | 86 [83–101] | 164 | 401 | 3657 | 3894 [3697–3902] |
| sheets, Pillow PNG | 782 | 16 | 90 | 175 [162–178] | 444 | 4309 | 4359 |
| sheets + recolour, oxipng | 227 | 6 | 254 | 305 [300–330] | 445 [422–458] | 1689 | 2508 |
| sheets + recolour, WebP | 167 | 6 | 300 [296–316] | 349 [328–358] | 450 | 1397 | 2287 [2262–2487] |
| sheets + recolour, Pillow PNG | 270 | 6 | 263 [244–263] | 317 | 451 | 1927 | 2717 |
| .px, brotli | 73 | 7 | 545 | 567 | 616 | 1196 | 2969 [2921–3077] |
| .px, gzip | 259 | 7 | 549 [498–622] | 551 | 727 [669–741] | 2100 | 3802 [3610–3930] |
| per-frame WebP | 1635 | 1936 | 2246 | 2364 | 2260 [2024–2547] | 16336 | 17814 [17140–18845] |
| per-frame PNG, oxipng | 1729 | 1936 | 2342 [2193–2536] | 2503 | 2534 | 18227 [16091–19629] | 18076 |
| per-frame PNG, Pillow | 4286 | 1936 | 2263 [2248–2422] | 2445 [2124–2703] | 2739 [2665–2894] | 30061 | 30830 |

### s300v2: first draw, ms (median [min–max] of 3 cold runs)

| option | KB | requests | desktop, no throttle | 100 Mbps / 20 ms | 20 Mbps / 40 ms | 4G (1.6 Mbps / 150 ms) | phone (Pixel 7, 4× CPU, 4G) |
|---|---|---|---|---|---|---|---|
| sheets, oxipng | 294 | 16 | 64 [60–78] | 119 | 246 | 1857 | 1978 [1879–2098] |
| sheets, WebP | 254 | 16 | 102 | 145 | 258 | 1668 | 1710 [1695–1988] |
| sheets, Pillow PNG | 354 | 16 | 61 [58–72] | 119 | 264 | 2139 | 2174 |
| sheets + recolour, Pillow PNG | 122 | 6 | 149 | 195 | 273 [273–298] | 1055 | 1538 |
| sheets + recolour, oxipng | 102 | 6 | 152 | 205 [198–213] | 275 [264–294] | 969 | 1399 |
| sheets + recolour, WebP | 88 | 6 | 162 [161–182] | 207 | 281 | 923 | 1392 |
| .px, brotli | 41 | 7 | 246 [240–260] | 290 | 333 | 754 [746–912] | 1533 |
| .px, gzip | 117 | 7 | 272 [244–282] | 295 [285–335] | 350 [339–402] | 1161 | 1919 |
| per-frame WebP | 746 | 901 | 1069 [1020–1103] | 1135 [1036–1170] | 1120 | 7638 [7621–8315] | 9127 [8710–9856] |
| per-frame PNG, oxipng | 791 | 901 | 1083 [996–1100] | 1056 [1008–1071] | 1218 [1094–1262] | 8506 [8466–9026] | 9828 [8983–10610] |
| per-frame PNG, Pillow | 1942 | 901 | 1099 [995–1107] | 1247 [1068–40510] | 1396 [1364–1440] | 14281 | 14957 [14589–15486] |

### s300: first draw, ms (median [min–max] of 3 cold runs)

| option | KB | requests | desktop, no throttle | 100 Mbps / 20 ms | 20 Mbps / 40 ms | 4G (1.6 Mbps / 150 ms) | phone (Pixel 7, 4× CPU, 4G) |
|---|---|---|---|---|---|---|---|
| sheets, oxipng | 99 | 6 | 40 [32–40] | 83 [76–86] | 152 | 839 | 864 [858–962] |
| sheets, Pillow PNG | 119 | 6 | 33 [28–39] | 80 [76–89] | 154 | 936 | 951 |
| sheets + recolour, oxipng | 99 | 6 | 41 [38–49] | 86 [72–87] | 154 | 843 | 859 |
| sheets + recolour, WebP | 85 | 6 | 56 [50–66] | 91 | 156 | 766 | 796 |
| sheets, WebP | 85 | 6 | 45 | 90 | 159 | 765 [758–990] | 802 |
| sheets + recolour, Pillow PNG | 119 | 6 | 38 | 79 | 159 | 929 | 960 |
| .px, brotli | 39 | 7 | 181 [168–204] | 239 [206–259] | 267 | 658 | 1142 |
| .px, gzip | 113 | 7 | 180 | 214 [214–230] | 290 [279–321] | 1039 [1027–1243] | 1479 |
| per-frame WebP | 249 | 301 | 379 [367–422] | 39682 [412–39841] | 417 [372–464] | 2776 [2718–3220] | 3066 [3026–3540] |
| per-frame PNG, oxipng | 264 | 301 | 376 [358–402] | 416 | 448 | 2995 [2721–3222] | 3013 [2842–3166] |
| per-frame PNG, Pillow | 646 | 301 | 381 [372–420] | 437 [422–449] | 520 [506–544] | 5032 | 5384 [5181–5596] |

## Files

| file | what it is |
|---|---|
| `bench.jsonl` | one line per page load (the first is the browser version). It covers first draw, full load, the runtime's timings, main-thread task and script ms, JS heap, decoded bitmap bytes, and the requests and bytes received |
| `bench-summary.md` | a table per profile and scenario, with full load, main thread and memory |
| `sizes.json` | bytes on the wire per option, from the files served |
| `optimize.jsonl` | the optimiser's file counts, bytes, RGBA checks and seconds |
| `parity.jsonl` | drawn parity in Chromium, per scenario and option |
| `machine.json` | the machine and software |
| `rerun-s300-frames-webp-100mbps.jsonl` | the stalled cell, run again |
