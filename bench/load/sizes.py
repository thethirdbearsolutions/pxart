"""Bytes on the wire per option, from the very files the bench serves.

    python3 bench/load/sizes.py WORK_DIR > sizes.json

For each scenario and out-<option>/: the pack files a game fetches (build.json "files"), images as
they are, text (manifest, .px) as web/server.mjs serves it: brotli quality 11, or gzip level 9 for a
.gzip option. The bench's own per-run byte counts (bench.jsonl packBytes) should match wire_bytes.
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import brotli

IMAGES = (".png", ".webp")


def main(work: Path) -> None:
    rows = []
    for sc in sorted(p for p in work.iterdir() if (p / "cast").is_dir()):
        for out in sorted(sc.glob("out-*")):
            opt = out.name[4:]
            files = json.loads((out / "build.json").read_text())["files"]
            img = text_br = text_gz = text_raw = 0
            for f in files:
                data = (out / f).read_bytes()
                if f.endswith(IMAGES):
                    img += len(data)
                else:
                    text_raw += len(data)
                    text_gz += len(gzip.compress(data, 9))
                    text_br += len(brotli.compress(data, quality=11))
            served = text_gz if opt.endswith(".gzip") else text_br
            rows.append({
                "scenario": sc.name, "option": opt, "requests": len(files), "image_bytes": img,
                "text_raw": text_raw, "text_gzip": text_gz, "text_br": text_br,
                "text_served": "gzip" if opt.endswith(".gzip") else "br", "wire_bytes": img + served,
            })
    print(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
