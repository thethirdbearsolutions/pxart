"""bench.jsonl + sizes.json -> markdown: one table per profile x scenario, options in order of median
first draw, with bytes on the wire and requests beside the timings.

    python3 bench/load/summarize.py bench.jsonl sizes.json > bench-summary.md

Timings are median [min-max] over the runs, in ms. "wire KB (bench)" is the median of the pack's
response body bytes the browser received (pack files only, /sc/...); "wire KB (sizes)" is
sizes.py's figure for the same files: they agree to within HTTP/2 framing, about 31 bytes per
response, which shows on the per-frame options' many small files. "main thread ms" is Chrome's task time
on the page's main thread from navigation to the end of the run (a worker's time isn't in it);
"heap MB" is the page's main-thread JS heap at full load, before garbage collection (a worker's
heap isn't in it); "bitmaps MB" is the decoded images or canvases, 4 bytes a pixel.
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict

LABEL = {
    "frames": "per-frame PNG, Pillow defaults",
    "frames.oxi": "per-frame PNG, oxipng -o6 + zopfli",
    "frames.webp": "per-frame WebP lossless",
    "atlas": "sheets, Pillow palette PNG",
    "atlas.oxi": "sheets, oxipng -o6 + zopfli",
    "atlas.webp": "sheets, WebP lossless",
    "atlas+": "sheets + recolour, Pillow palette PNG",
    "atlas+.oxi": "sheets + recolour, oxipng -o6 + zopfli",
    "atlas+.webp": "sheets + recolour, WebP lossless",
    "render": ".px, brotli",
    "render.gzip": ".px, gzip",
    "pxc": "PXC1, brotli, worker",
    "pxc.gzip": "PXC1, gzip, worker",
    "pxc.main": "PXC1, brotli, main thread",
}
PROFILE_ORDER = ["desktop", "desktop-100mbps", "desktop-20mbps", "desktop-4g", "mobile"]


def cell(vals: list[float]) -> str:
    med, lo, hi = statistics.median(vals), min(vals), max(vals)
    return f"{med:.0f}" if round(lo) == round(hi) else f"{med:.0f} [{lo:.0f}–{hi:.0f}]"


def main(bench: str, sizes: str) -> None:
    size = {(r["scenario"], r["option"]): r for r in json.load(open(sizes))}
    runs = defaultdict(list)
    errors = []
    browser = None
    for line in open(bench):
        d = json.loads(line)
        if "browser" in d:
            browser = d["browser"]
        elif "error" in d:
            errors.append(d)
        elif "profile" in d:
            runs[(d["profile"], d["sc"], d["opt"])].append(d)
    if not runs:
        sys.exit(f"no successful runs in {bench}; {len(errors)} failed")
    print(f"Chromium {browser}. Median [min–max] of {max(len(v) for v in runs.values())} cold-cache runs, ms."
          f" {len(errors)} runs failed.\n")
    groups = defaultdict(dict)
    for (prof, sc, opt), rs in runs.items():
        groups[(prof, sc)][opt] = rs
    order = sorted(groups, key=lambda k: (PROFILE_ORDER.index(k[0]) if k[0] in PROFILE_ORDER else 99, k[1]))
    for prof, sc in order:
        opts = groups[(prof, sc)]
        print(f"\n### {prof}, {sc}\n")
        print("| option | wire KB (bench) | wire KB (sizes) | pack requests | first draw ms | full load ms "
              "| main thread ms | heap MB | bitmaps MB | n |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        for opt, rs in sorted(opts.items(), key=lambda kv: statistics.median(r["firstDraw"] for r in kv[1])):
            s = size.get((sc, opt), {})
            print(f"| {LABEL.get(opt, opt)} | {statistics.median(r['packBytes'] for r in rs) / 1000:.0f} | "
                  f"{s.get('wire_bytes', 0) / 1000:.0f} | {rs[0]['packRequests']} | "
                  f"{cell([r['firstDraw'] for r in rs])} | {cell([r['full'] for r in rs])} | "
                  f"{cell([r.get('mainThreadTaskMs', 0) for r in rs])} | {statistics.median((r.get('jsHeap') or 0) for r in rs) / 1e6:.1f} | "
                  f"{statistics.median(r.get('bitmapBytes', 0) for r in rs) / 1e6:.1f} | {len(rs)} |")
    for e in errors:
        print(f"\nERROR {e.get('profile')} {e.get('sc')} {e.get('opt')}: {e['error'][:300]}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
