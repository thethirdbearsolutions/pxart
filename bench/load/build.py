"""Build one scenario's cast into the four ways a game can ship it, with pxart.py and Pillow only.

    python3 bench/load/build.py SCENARIO_DIR

Reads SCENARIO_DIR/cast/*.px and writes, next to it, one directory per option:
- out-frames/:  one PNG per frame per palette (base, then each variant), as Pillow saves an RGBA
                image by default: what a per-frame export ships.
- out-atlas/:   one sheet per character per palette (shelf-packed, 1 px gaps), saved as a palette
                PNG when the sheet has 256 colors or fewer; each entry points at its rect.
- out-atlas+/:  the base sheets only; a variant entry draws its base rect recolored through
                pack.recolor[variant] ({base #rrggbbaa: variant #rrggbbaa}), built at load.
- out-render/:  the .px sources (comment lines dropped); the page draws them with js/px.ts.

Each has manifest.json ({"pack": {...}, "sprites": [...]}, entries in the same order in every
option) and build.json (timings and the files a game fetches). optimize.py adds the optimised
image options and .px served gzip-only.
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import pxart  # noqa: E402

ATLAS_WIDTH = 1024
GAP = 1
MODES = ("frames", "atlas", "atlas+", "render")


def shelf_pack(sizes: dict[str, tuple[int, int]], width: int = ATLAS_WIDTH) -> tuple[dict, tuple[int, int]]:
    """{key: (x, y)} placing each (w, h) in rows, tallest first; and the sheet's size."""
    order = sorted(sizes, key=lambda k: (-sizes[k][1], -sizes[k][0], k))
    x = y = row_h = used_w = 0
    at = {}
    for k in order:
        w, h = sizes[k]
        if x and x + w > width:
            y, x, row_h = y + row_h + GAP, 0, 0
        at[k] = (x, y)
        x += w + GAP
        row_h = max(row_h, h)
        used_w = max(used_w, x - GAP)
    return at, (used_w, y + row_h)


def save_png(img: Image.Image, out: Path) -> None:
    """Lossless: a palette PNG (tRNS alpha) when the image has <= 256 RGBA colors, else RGBA."""
    out.parent.mkdir(parents=True, exist_ok=True)
    colors = img.getcolors(256)
    if colors is None:
        img.save(out, format="PNG", optimize=True)
        return
    pal_img = Image.new("P", img.size)
    lut = {c: i for i, (_, c) in enumerate(colors)}
    pixels = img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata()
    pal_img.putdata([lut[p] for p in pixels])
    flat = []
    for _, (r, g, b, a) in colors:
        flat += [r, g, b]
    pal_img.putpalette(flat)
    alpha = bytes(c[3] for _, c in colors)
    pal_img.save(out, format="PNG", optimize=True, transparency=alpha)


def hex8(c) -> str:
    return "#" + "".join(f"{x:02x}" for x in c)


def load_cast(cast: Path) -> tuple[dict, list[str], list[str]]:
    """({stem: Doc} for the character files, the variants, every .px file name)."""
    names = sorted(p.name for p in cast.glob("*.px"))
    docs = {}
    for name in names:
        if pxart._has_grid(cast / name):
            docs[name[:-3]] = pxart.parse(cast / name)
    variants = sorted({v for d in docs.values() for v in pxart.variant_names(d)})
    return docs, variants, names


def render_all(docs: dict, variants: list[str]) -> list[tuple[str, str, object, Image.Image]]:
    """[(variant or '', stem, frame, image)] for every frame in every palette, base first."""
    out = []
    for v in ["", *variants]:
        for stem, doc in docs.items():
            for f in doc.frames:
                out.append((v, stem, f, doc.image(f, v or None)))
    return out


def entry(v: str, stem: str, f) -> dict:
    parts = f.id.split("/")
    return {
        "path": f"{v + '/' if v else ''}{stem}/{f.id}.png",
        "character": stem,
        "animation": parts[0],
        "direction": parts[1] if len(parts) > 2 else None,
        "frame": f.id,
        "variant": v or None,
        "px": list(f.size),
    }


def recolor_maps(docs: dict, variants: list[str]) -> tuple[dict, list[str]]:
    """{variant: {base rgba hex: variant rgba hex}} over every character, and the base colors two
    keys share but a variant splits (a color map can't recolor those)."""
    maps: dict[str, dict[str, str]] = {v: {} for v in variants}
    clashes = []
    for doc in docs.values():
        base = doc.resolved()
        used = {c for f in doc.frames for row in f.grid for c in row}
        for v in variants:
            pal = doc.resolved(v)
            for k in used:
                if base[k][3] == 0:
                    continue
                b, c = hex8(base[k]), hex8(pal[k])
                if maps[v].setdefault(b, c) != c:
                    clashes.append(f"{v}: {b} -> {maps[v][b]} and {c}")
    return maps, clashes


def build(scenario: Path, mode: str) -> dict:
    cast = scenario / "cast"
    out = scenario / f"out-{mode}"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    t: dict = {}
    t0 = time.perf_counter()
    docs, variants, names = load_cast(cast)
    images = render_all(docs, variants) if mode != "render" else []
    if mode == "render":  # the manifest still needs every frame's size: read them, render nothing
        images = [(v, s, f, None) for v in ["", *variants] for s, d in docs.items() for f in d.frames]
    t["render"] = time.perf_counter() - t0
    sprites = [entry(v, s, f) for v, s, f, _ in images]
    pack: dict = {"variants": variants}
    files: list[str] = []
    t1 = time.perf_counter()
    if mode == "frames":
        for e, (_, _, _, img) in zip(sprites, images):
            p = out / "frames" / e["path"]
            p.parent.mkdir(parents=True, exist_ok=True)
            img.save(p, format="PNG")
            files.append(f"frames/{e['path']}")
    elif mode in ("atlas", "atlas+"):
        groups: dict[tuple[str, str], list[int]] = {}
        for i, (v, s, _, _) in enumerate(images):
            groups.setdefault((v, s), []).append(i)
        base_rect: dict[tuple[str, str], tuple[str, list[int]]] = {}
        for (v, s), idx in groups.items():
            if mode == "atlas+" and v:
                continue
            at, size = shelf_pack({str(i): images[i][3].size for i in idx})
            sheet = Image.new("RGBA", size)
            for i in idx:
                sheet.paste(images[i][3], at[str(i)])
            rel = f"atlas/{v + '/' if v else ''}{s}.png"
            save_png(sheet, out / rel)
            files.append(rel)
            for i in idx:
                rect = [*at[str(i)], *images[i][3].size]
                sprites[i]["path"], sprites[i]["src"] = rel, {"rect": rect}
                base_rect[(s, images[i][2].id)] = (rel, rect)
        if mode == "atlas+":
            for i, (v, s, f, _) in enumerate(images):
                if v:
                    rel, rect = base_rect[(s, f.id)]
                    sprites[i]["path"], sprites[i]["src"] = rel, {"rect": rect, "recolor": v}
            if variants:
                pack["recolor"], t["recolor_clashes"] = recolor_maps(docs, variants)
    else:
        pack["sources"] = names
        (out / "pxart").mkdir()
        for n in names:
            text = (cast / n).read_text()
            (out / "pxart" / n).write_text("".join(x for x in text.splitlines(True) if not x.lstrip().startswith("#")))
            files.append(f"pxart/{n}")
    t["encode"] = time.perf_counter() - t1
    (out / "manifest.json").write_text(json.dumps({"pack": pack, "sprites": sprites}, separators=(",", ":")))
    files.append("manifest.json")
    t["total"] = time.perf_counter() - t0
    t["frames"] = len(sprites)
    t["files"] = files
    (out / "build.json").write_text(json.dumps(t, indent=1))
    return t


def main(scenario: Path, modes: list[str]) -> None:
    for mode in modes:
        t = build(scenario, mode)
        print(f"{scenario.name} {mode}: {t['frames']} entries, {len(t['files'])} files, {t['total']:.1f}s", flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2:] or list(MODES))
