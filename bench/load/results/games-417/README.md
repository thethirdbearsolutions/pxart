# GAMES-417: the first load bench (14 Nov 2026)

Raw results of the first run, published as they were recorded. Each line of `bench.jsonl` is one
page load.

- **Cast:** a private cast of five characters (elsabunny, hootison, knight, mage, sivouette) and a
  shared `palette.px`, in three scenarios: s300 (299 frames, no variants), s300v2 (the same with
  dawn and dusk variants) and s650v2 (639 frames, with up, left and right facings added to the
  four one-facing actions, plus dawn and dusk). The art is not published. `../../make_cast.py`
  builds a synthetic cast of the same shape, but its numbers are its own: don't compare them
  with these.
- **Code:** a private earlier version of this bench. It built each option with the games
  platform's own publish code and loaded it with that platform's sprite runtime. The public bench
  in `../../` reimplements both with pxart.py, Pillow and `js/px.ts` alone.
- **Machine:** an Apple Silicon Mac (Chrome for Testing, mac-arm64). The model, CPU and memory
  weren't recorded.
- **Browser:** Chromium 156.0.8078.4, headless, through Playwright.
- **Profiles:**
  - `desktop`: no throttling;
  - `desktop-4g`: Lighthouse's mobile network (1.6 Mbps down, 750 kbps up, 150 ms RTT), desktop CPU;
  - `mobile`: Playwright's Pixel 7 on that network, with the CPU throttled 4×.
- **Runs:** 3 cold-cache runs per option, scenario and profile, over HTTP/2 + TLS with brotli for text.
- **Options:** four of them.
  - `frames`: one PNG per frame, as Pillow saves them;
  - `atlas`: sheets, one per character per palette;
  - `atlas+`: base sheets, recoloured at load;
  - `render`: the `.px` sources, drawn with px.ts.

## Files

- `bench.jsonl`: one line per page load. The first line is the browser version.
- `sizes.json`: bytes per option. It covers the files as built, PNGs re-encoded as palette PNGs,
  and PNGs through oxipng. Each is given raw, gzip -9 and brotli -q 11.
- `bench-summary.md`: the run's own summary table.
- `builds/<scenario>/<option>.json`, `builds.log`: build timings and the files each option ships.
  The per-frame option's file list is replaced by its count, because its names are the private
  cast's frame ids.
