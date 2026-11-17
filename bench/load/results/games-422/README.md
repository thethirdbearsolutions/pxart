# GAMES-422: a fair PNG comparison (14 Nov 2026)

Raw results of the second run, published as they were recorded. It added optimised images to
GAMES-417's four options, and timed all 11 options side by side in one session.

- **Cast, code, machine, browser and profiles:** the same as GAMES-417 (see `../games-417/README.md`).
  That is the private cast (s300, s300v2, s650v2), an Apple Silicon Mac, Chromium 156.0.8078.4,
  and three profiles: `desktop`, `desktop-4g` and `mobile`.
- **Options:** the 11 options the public bench still runs.
  - `frames`, `atlas`, `atlas+`: as GAMES-417 built them;
  - `.oxi`: each image as a palette PNG, then oxipng -o6 with metadata stripped and zopfli
    at 15 iterations;
  - `.webp`: `cwebp -lossless -z 9 -metadata none`, from Homebrew cwebp 1.6.0;
  - `render` (`.px`, brotli) and `render.gzip` (`.px` served gzip only).

  Every optimised image was decoded and compared with the original's RGBA, byte for byte. All
  6,334 were identical.
- **Runs:** 3 cold-cache runs each, 297 page loads, none failed. Each run also records the
  bytes the browser received.

## Files

- `bench.jsonl`: one line per page load. The first line is the browser version.
- `sizes.json`: bytes on the wire per option, computed from the files served.
- `optimize.jsonl`: the optimiser's per-option file counts, bytes and RGBA checks.
- `bench-summary.md`: one table per profile and scenario.
