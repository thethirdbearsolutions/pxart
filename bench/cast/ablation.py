"""What each coding idea is worth once brotli has had its turn: bytes after brotli (quality 11) for
one cast's frames, coded several ways. Only the pixels and the .px text are compared, so the header
a real file adds (ids, palettes) is left out of every row but the PXC1 ones.

    python3 bench/cast/ablation.py CAST_DIR

Rows (one JSON line each):
- px:            the .px files as served (comment lines dropped), each compressed on its own and
                 summed, as the bench's .px option ships them;
- px-one-file:   the same text as one file (a whole-cast bundle);
- raw-rows / raw-cols: one byte per pixel (a palette index), every frame, row or column order;
- raw-rows-local: as raw-rows, with each character's own index space instead of one for the cast;
- xor-prev:      each frame XORed with the previous frame of the same size (a frame delta);
- ops-rows / ops-cols: PXC1's row ops (blank, same as the previous frame's line, same as the line
                 above, runs, changed spans) in row or column order; ops-rows-nodelta without the
                 previous-frame ops;
- pxc / pxc-rows: the PXC1 file itself (column or row order).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import brotli

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pxart  # noqa: E402
from pxc import code_lines, encode, transpose  # noqa: E402


def br(data: bytes) -> int:
    return len(brotli.compress(bytes(data), quality=11))


def main(cast: Path) -> None:
    files = sorted(cast.glob("*.px"))
    served = ["".join(x for x in p.read_text().splitlines(True) if not x.lstrip().startswith("#")).encode() for p in files]
    docs = [pxart.parse(p) for p in files if pxart._has_grid(p)]
    keys = sorted({c for d in docs for f in d.frames for r in f.grid for c in r} - {"."})
    gidx = {".": 0, **{k: i + 1 for i, k in enumerate(keys)}}
    grids, local = [], []
    for d in docs:
        own = sorted({c for f in d.frames for r in f.grid for c in r} - {"."})
        lidx = {".": 0, **{k: i + 1 for i, k in enumerate(own)}}
        grids.append([[[gidx[c] for c in r] for r in f.grid] for f in d.frames])
        local.append([[[lidx[c] for c in r] for r in f.grid] for f in d.frames])

    def flat(gs, cols=False):
        out = bytearray()
        for ch in gs:
            for g in ch:
                for line in (transpose(g) if cols else g):
                    out += bytes(line)
        return out

    xor = bytearray()
    for ch in grids:
        prev = None
        for g in ch:
            f = bytes(v for r in g for v in r)
            xor += bytes(a ^ b for a, b in zip(f, prev)) if prev is not None and len(prev) == len(f) else f
            prev = f

    def ops(cols, delta):
        out = bytearray()
        for ch in grids:
            prev = None
            for g in ch:
                same = prev is not None and len(prev) == len(g) and len(prev[0]) == len(g[0])
                lines = transpose(g) if cols else g
                out += code_lines(lines, (transpose(prev) if cols else prev) if same else None, delta)
                prev = g
        return out

    rows = {
        "px": sum(br(t) for t in served),
        "px-one-file": br(b"".join(served)),
        "raw-rows": br(flat(grids)),
        "raw-cols": br(flat(grids, True)),
        "raw-rows-local": br(flat(local)),
        "xor-prev": br(xor),
        "ops-rows": br(ops(False, True)),
        "ops-cols": br(ops(True, True)),
        "ops-rows-nodelta": br(ops(False, False)),
        "pxc": br(encode(cast, None, cols=True)[0]),
        "pxc-rows": br(encode(cast, None, cols=False)[0]),
    }
    for k, v in rows.items():
        print(json.dumps({"cast": cast.parent.name, "coding": k, "brotli_bytes": v}), flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
