"""Build an axes scenario (make_axes.py) in the four ways a game could ship it, and measure bytes.

    python3 bench/cast/build_axes.py SCENARIO_DIR [--no-sheets]

Writes, next to SCENARIO_DIR/cast and layers.json:
- out-sheets/:    one lossless WebP sheet per palette per damage x expression combination per
                  character, <palette>/<combination>/<character>.webp (what an export per variant
                  ships; a game fetches only the sheets of what it shows);
- out-recolour/:  the base palette's sheets only, per combination, plus recolour maps per palette;
- out-px/:        the .px sources, comment lines dropped (every combination baked in as frames);
- out-pxc/:       one PXC1 file: palettes as axes, combinations as overlays.
Each has manifest.json: per character, every frame's rect by its id without the combination
prefix (every combination's sheet has the same layout), the palettes and combinations. Prints a JSON line of bytes per option: as
files, brotli (quality 11) and gzip (level 9) for text and .pxc; images as they are.
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import brotli
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "load"))
sys.path.insert(0, str(HERE))
from build import hex8, load_cast, shelf_pack  # noqa: E402
from pxc import encode  # noqa: E402


def webp(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="WEBP", lossless=True, quality=100, method=6)
    return buf.getvalue()


def sheet_job(args) -> list[tuple[str, bytes]]:
    """Every combination's sheet of one character in one palette: [(path, WebP bytes)]."""
    cast, stem, variant, at, size, combos = args
    import pxart

    doc = pxart.parse(Path(cast) / f"{stem}.px")
    out = []
    for combo in combos:
        sheet = Image.new("RGBA", size)
        for f in doc.frames:
            if f.id.startswith(combo + "/"):
                sheet.paste(doc.image(f, variant or None), at[f.id[len(combo) + 1:]])
        out.append((f"{variant or 'base'}/{combo}/{stem}.webp", webp(sheet)))
    return out


def sizes_of(files: list[Path]) -> dict:
    raw = br = gz = img = 0
    for p in files:
        data = p.read_bytes()
        if p.suffix == ".webp":
            img += len(data)
        else:
            raw += len(data)
            br += len(brotli.compress(data, quality=11))
            gz += len(gzip.compress(data, 9))
    return {"files": len(files), "image_bytes": img, "text_raw": raw, "text_br": br, "text_gzip": gz,
            "wire_br": img + br, "wire_gzip": img + gz}


def main(scenario: Path, sheets: bool) -> None:
    cast = scenario / "cast"
    layers = json.loads((scenario / "layers.json").read_text())
    docs, variants, names = load_cast(cast)
    palettes = ["", *variants]
    combos = [f"{d}-{e}" for d in layers["damage"] for e in layers["expression"]]
    first = combos[0] + "/"
    layout = {}
    for stem, doc in docs.items():
        sizes = {f.id[len(first):]: f.size for f in doc.frames if f.id.startswith(first)}
        at, size = shelf_pack(sizes)
        layout[stem] = (at, size, sizes)
    manifest = {
        "palettes": palettes, "damage": layers["damage"], "expression": layers["expression"],
        "characters": {s: {"size": list(layout[s][1]), "rects": {fid: [*layout[s][0][fid], *wh] for fid, wh in layout[s][2].items()}}
                       for s in docs},
    }
    row = {"scenario": scenario.name, "frames": sum(len(d.frames) for d in docs.values()), "palettes": len(palettes),
           "combinations": len(layers["damage"]) * len(layers["expression"])}

    out = scenario / "out-px"
    shutil.rmtree(out, ignore_errors=True)
    (out / "pxart").mkdir(parents=True)
    for n in names:
        text = (cast / n).read_text()
        (out / "pxart" / n).write_text("".join(x for x in text.splitlines(True) if not x.lstrip().startswith("#")))
    (out / "manifest.json").write_text(json.dumps({**manifest, "sources": names}, separators=(",", ":")))
    row["px"] = sizes_of(sorted((out / "pxart").glob("*.px")) + [out / "manifest.json"])

    out = scenario / "out-pxc"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir()
    data, _ = encode(cast, layers)
    (out / "cast.pxc").write_bytes(data)
    (out / "manifest.json").write_text(json.dumps({**manifest, "pxc": "cast.pxc"}, separators=(",", ":")))
    row["pxc"] = sizes_of([out / "cast.pxc", out / "manifest.json"])

    if sheets:
        jobs = [(str(cast), s, v, layout[s][0], layout[s][1], combos) for s in docs for v in palettes]
        out_s, out_r = scenario / "out-sheets", scenario / "out-recolour"
        for d in (out_s, out_r):
            shutil.rmtree(d, ignore_errors=True)
            d.mkdir()
        with ProcessPoolExecutor() as pool:
            for done in pool.map(sheet_job, jobs):
                for rel, data in done:
                    (out_s / rel).parent.mkdir(parents=True, exist_ok=True)
                    (out_s / rel).write_bytes(data)
                    if rel.startswith("base/"):
                        (out_r / rel).parent.mkdir(parents=True, exist_ok=True)
                        (out_r / rel).write_bytes(data)
        (out_s / "manifest.json").write_text(json.dumps(manifest, separators=(",", ":")))
        maps: dict[str, dict[str, str]] = {v: {} for v in variants}
        for doc in docs.values():
            base = doc.resolved()
            used = {c for f in doc.frames for r in f.grid for c in r}
            for v in variants:
                pal = doc.resolved(v)
                for k in used:
                    if base[k][3]:
                        maps[v][hex8(base[k])] = hex8(pal[k])
        (out_r / "manifest.json").write_text(json.dumps({**manifest, "recolor": maps}, separators=(",", ":")))
        row["sheets"] = sizes_of(sorted(out_s.rglob("*.webp")) + [out_s / "manifest.json"])
        row["recolour"] = sizes_of(sorted(out_r.rglob("*.webp")) + [out_r / "manifest.json"])
    print(json.dumps(row), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario", type=Path)
    ap.add_argument("--no-sheets", action="store_true")
    a = ap.parse_args()
    main(a.scenario, not a.no_sheets)
