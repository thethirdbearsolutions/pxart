"""PXC1, a whole-cast container for the compression spike: every character's frames as raw palette
indices in one plane, with palettes (or palette axes) as data and, for a layered cast, overlays and
anchors instead of baked combinations. Decoded by web/pxc.js, in a Web Worker (web/pxc-worker.js).

    python3 bench/cast/pxc.py CAST_DIR OUT.pxc [--layers layers.json] [--orient cols|rows] [--coding raw|ops]

CAST_DIR is a flat folder of .px files, one per character, each named after its character (fox.px is
"fox"); subfolders aren't read, and a palette-only file (no grid, like a shared palette.px the others
@palette-import) is skipped; a file of one unnamed grid names its frame after the file. A cast has one
palette: every key the cast draws has one color (slot alternatives included) in every file that has it,
in the base and in each variant, and every file has every variant (its own, or through @palette). A file
needn't list keys it doesn't draw, so `pxart check`'s unused-key advice is safe to follow. A key colored
two ways, or a variant one file lacks, is an error naming the key and the files. With --layers only the
base palette is encoded (the axes make the rest), so only the base is held to that rule.

The file is meant to be served brotli-compressed, like .px. Brotli finds what repeats between rows,
frames and characters by itself; the format only makes those repeats long and aligned: one byte per
pixel, one index space for the whole cast, headers apart from pixels, frames stored column by
column (--orient). --coding ops (row ops against the row above and the previous frame's row, the
first idea tried) is kept to measure it: web/pxc.js reads only raw.

Layout (integers are LEB128 varints, s-varints zigzag; strings are a varint length and UTF-8):

    "PXC1"  flags(byte: 1 layered, 2 columns, 4 ops coding)
    palettes: n, then n names (the base is "")
    axes (layered): n axes, each: name, n values, each: name, 3 x (mul*1000 varint, add s-varint)
    keys: n, then per palette n x RGBA (layered: the base only; the axes make the rest)
    characters: n, each: name, nframes, each: id, w, h
        layered: noverlays, each: name, at(byte 0 head 1 body), dx, dy (s-varints), w, h;
                 per frame: head x, y, body x, y, mirror(byte)
    layered: n damage names, n expression names
    plane: every frame's w*h indices, then every overlay's, in file order (column-major if flagged)

Index 0 is transparent; keys are 1..n.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import pxart  # noqa: E402

BLANK, SAME_PREV, SAME_ABOVE, RUNS, DELTA_PREV, DELTA_ABOVE = range(6)


def varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def svarint(n: int) -> bytes:
    return varint((n << 1) ^ (n >> 63) if n < 0 else n << 1)


def string(s: str) -> bytes:
    b = s.encode()
    return varint(len(b)) + b


def runs(line: list[int]) -> bytes:
    out = bytearray()
    i = 0
    while i < len(line):
        j = i
        while j < len(line) and line[j] == line[i]:
            j += 1
        out += varint(j - i) + bytes([line[i]])
        i = j
    return bytes(out)


def spans(line: list[int], ref: list[int]) -> bytes:
    out = bytearray()
    i, n = 0, len(line)
    while i < n:
        j = i
        while j < n and line[j] == ref[j]:
            j += 1
        out += varint(j - i)
        if j >= n:
            break
        k = j
        # a changed span ends at 3 unchanged in a row (shorter gaps are cheaper to send as literals)
        while k < n and not (line[k] == ref[k] and k + 2 < n and line[k + 1] == ref[k + 1] and line[k + 2] == ref[k + 2]):
            k += 1
        out += varint(k - j) + bytes(line[j:k])
        i = k
    return bytes(out)


def code_lines(lines: list[list[int]], prev: list[list[int]] | None, delta: bool) -> bytes:
    out = bytearray()
    for y, line in enumerate(lines):
        options = []
        if not any(line):
            options.append(bytes([BLANK]))
        if delta and prev is not None and prev[y] == line:
            options.append(bytes([SAME_PREV]))
        if y and lines[y - 1] == line:
            options.append(bytes([SAME_ABOVE]))
        options.append(bytes([RUNS]) + runs(line))
        if delta and prev is not None:
            options.append(bytes([DELTA_PREV]) + spans(line, prev[y]))
        if y:
            options.append(bytes([DELTA_ABOVE]) + spans(line, lines[y - 1]))
        out += min(options, key=len)
    return bytes(out)


def transpose(lines: list[list[int]]) -> list[list[int]]:
    return [list(c) for c in zip(*lines)] if lines else []


def grid_indices(rows, index: dict[str, int]) -> list[list[int]]:
    return [[index[c] for c in r] for r in rows]


def rgba_table(pal: dict, keys: list[str]) -> bytes:
    return b"".join(bytes(pal[k]) for k in keys)


def plane(g: list[list[int]], cols: bool) -> bytes:
    return bytes(v for line in (transpose(g) if cols else g) for v in line)


def cast_palette(docs: dict, keys: list[str], variant: str | None) -> dict:
    """The cast's one palette in variant (None the base): each key's color, the same in every file that has the key.
    A file needn't list keys it doesn't draw. A key two files color differently, a variant a file lacks, or a key no
    file has is a SystemExit naming the key, the variant and the files."""
    where = f" in @variant {variant}" if variant else " in the base"
    if variant:
        lacking = [f"{stem}.px" for stem, d in docs.items() if variant not in pxart.variant_names(d)]
        if lacking:
            raise SystemExit(f"PXC1 needs one palette for the whole cast: {', '.join(lacking)} "
                             f"{'has' if len(lacking) == 1 else 'have'} no @variant "
                             f"{variant}, which other files have; every file needs every variant (give it one, or "
                             f"import a palette file that has it)")
    pal = {}
    for k in keys:
        seen = {f"{stem}.px" + ("" if k in d.palette else " (from its @palette)"): d.resolved(variant)[k]
                for stem, d in docs.items() if k in d.resolved(variant)}
        if not seen:
            raise SystemExit(f"PXC1: key {k!r} is drawn (by a frame, or by an overlay in layers.json) but no file of "
                             "the cast has it in its palette")
        if len(set(seen.values())) > 1:  # a Slot hashes with its alternatives, so slots that differ there differ
            said = ", ".join(f"{f} {pxart.fmt_color(c)}" for f, c in seen.items())
            raise SystemExit(f"PXC1 needs one palette for the whole cast: key {k!r}{where} differs between files "
                             f"({said}); give it one color in every file that has it")
        pal[k] = next(iter(seen.values()))
    return pal


def encode(cast: Path, layers: dict | None, cols: bool = True, coding: str = "raw") -> tuple[bytes, dict]:
    if not cast.is_dir():
        raise SystemExit(f"PXC1: {cast} isn't a folder; give the folder that holds the cast's .px files")
    try:
        names = sorted(p.name for p in cast.glob("*.px") if p.is_file() and pxart._has_grid(p))
        docs = {n[:-3]: pxart.parse(cast / n) for n in names}
    except pxart.PxError as e:
        raise SystemExit(f"PXC1: a file of the cast doesn't read (run pxart check on it):\n{e}")
    except (OSError, UnicodeDecodeError) as e:
        raise SystemExit(f"PXC1: a file of the cast doesn't read: {e}")
    if not docs:
        deeper = sorted(str(p.relative_to(cast)) for p in cast.glob("*/**/*.px"))
        more = " ..." if len(deeper) > 4 else ""
        raise SystemExit(f"PXC1: {cast} has no character .px files (a file with frames, directly in it)"
                         + (f"; subfolders aren't read, and hold {', '.join(deeper[:4])}{more}" if deeper else ""))
    variants = sorted({v for d in docs.values() for v in pxart.variant_names(d)})
    head = bytearray(b"PXC1" + bytes([(1 if layers else 0) | (2 if cols else 0) | (4 if coding == "ops" else 0)]))
    head += varint(1 + len(variants)) + string("") + b"".join(string(v) for v in variants)
    if layers:
        axes = layers["axes"]
        head += varint(len(axes["order"]))
        for name in axes["order"]:
            head += string(name) + varint(len(axes[name]))
            for vname, (mul, add) in axes[name].items():
                head += string(vname) + b"".join(varint(round(m * 1000)) + svarint(a) for m, a in zip(mul, add))
    keys = sorted({c for d in docs.values() for f in d.frames for r in f.grid for c in r} - {"."})
    if layers:
        for info in layers["characters"].values():
            keys = sorted(set(keys) | {c for ov in info["overlays"].values() if ov for r in ov["rows"] for c in r} - {"."})
    index = {".": 0, **{k: i + 1 for i, k in enumerate(keys)}}
    head += varint(len(keys))
    for v in ([None] if layers else [None, *variants]):
        head += rgba_table(cast_palette(docs, keys, v), keys)
    pix = bytearray()
    prefix = f"{layers['damage'][0]}-{layers['expression'][0]}/" if layers else ""
    head += varint(len(docs))
    overlays_pix = bytearray()
    for stem, doc in docs.items():
        ids = [(f.id or stem, f) for f in doc.frames]  # one unnamed grid goes by the file's name, as in pxart
        frames = [(fid[len(prefix):], grid_indices(f.grid, index)) for fid, f in ids if fid.startswith(prefix)]
        head += string(stem) + varint(len(frames))
        prev = None
        for fid, g in frames:
            head += string(fid) + varint(len(g[0]) if g else 0) + varint(len(g))
            if coding == "ops":
                same = prev is not None and len(prev) == len(g) and len(prev[0]) == len(g[0])
                pix += code_lines(transpose(g) if cols else g, (transpose(prev) if cols else prev) if same else None, True)
            else:
                pix += plane(g, cols)
            prev = g
        if layers and not frames:
            raise SystemExit(f"PXC1 --layers: {stem}.px has no frame under {prefix} (a layered cast's frames are "
                             f"DAMAGE-EXPRESSION/ID, the first damage and expression's)")
        if layers:
            if stem not in layers["characters"]:
                raise SystemExit(f"PXC1 --layers: {stem}.px has no entry under \"characters\" in the layers file")
            info = layers["characters"][stem]
            lost = [fid for fid, _ in frames if fid not in info["anchors"]]
            if lost:
                raise SystemExit(f"PXC1 --layers: {stem}'s frames {', '.join(lost[:4])} have no anchors in the layers "
                                 "file")
            ovs = [(k, v) for k, v in info["overlays"].items() if v is not None]
            head += varint(len(ovs))
            for name, ov in ovs:
                g = grid_indices(ov["rows"], index)
                head += string(name) + bytes([0 if ov["at"] == "head" else 1]) + svarint(ov["dx"]) + svarint(ov["dy"])
                head += varint(len(g[0])) + varint(len(g))
                overlays_pix += plane(g, cols)
            for fid, _ in frames:
                a = info["anchors"][fid]
                head += varint(a["head"][0]) + varint(a["head"][1]) + varint(a["body"][0]) + varint(a["body"][1])
                head += bytes([1 if a["mirror"] else 0])
    if layers:
        head += varint(len(layers["damage"])) + b"".join(string(d) for d in layers["damage"])
        head += varint(len(layers["expression"])) + b"".join(string(e) for e in layers["expression"])
    return bytes(head + pix + overlays_pix), {"header_bytes": len(head), "pixel_bytes": len(pix) + len(overlays_pix), "keys": len(keys)}


def main() -> None:
    ap = argparse.ArgumentParser(description="Encode a cast as PXC1.")
    ap.add_argument("cast", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--layers", type=Path)
    ap.add_argument("--orient", choices=("cols", "rows"), default="cols")
    ap.add_argument("--coding", choices=("raw", "ops"), default="raw", help="ops: the row-op coding, for measuring only")
    a = ap.parse_args()
    layers = json.loads(a.layers.read_text()) if a.layers else None
    data, stats = encode(a.cast, layers, cols=a.orient == "cols", coding=a.coding)
    a.out.write_bytes(data)
    print(json.dumps({"out": a.out.name, "bytes": len(data), **stats}))


if __name__ == "__main__":
    main()
