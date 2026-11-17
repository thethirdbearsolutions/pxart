"""The optimised image options, written next to build.py's, so the bench serves exactly the bytes
sizes.py reports.

    python3 bench/load/optimize.py SCENARIO_DIR

For each image option (frames, atlas, atlas+), from out-<option>/:
- out-<option>.oxi/:   every PNG as a lossless palette PNG (build.save_png), then oxipng level 6,
                       metadata stripped, zopfli deflate (15 iterations), per-frame files included;
- out-<option>.webp/:  every PNG as lossless WebP through Pillow's libwebp (lossless, quality 100,
                       method 6: what `cwebp -lossless -z 9` asks for; `exact` only if needed for
                       identical RGBA, and counted); manifest paths .png -> .webp.
And out-render.gzip/: a copy of out-render/, which the bench server serves gzip-only.

Every written image is decoded and checked against the original PNG's RGBA, byte for byte.
Prints one JSON line per option with file counts, bytes and encode seconds.
"""

from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import oxipng
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import save_png  # noqa: E402


def rgba(data: bytes) -> tuple[tuple[int, int], bytes]:
    im = Image.open(io.BytesIO(data))
    im.load()
    im = im.convert("RGBA")
    return im.size, im.tobytes()


def to_oxi(src: Path, dst: Path) -> tuple[int, bool]:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / "p.png"
        save_png(Image.open(src).convert("RGBA"), tmp)
        pal = tmp.read_bytes()
    best = oxipng.optimize_from_memory(pal, level=6, strip=oxipng.StripChunks.safe(), deflate=oxipng.Deflaters.zopfli(15))
    if rgba(best) != rgba(src.read_bytes()):
        raise AssertionError(f"{src}: oxipng output differs")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(best)
    return len(best), False


def to_webp(src: Path, dst: Path) -> tuple[int, bool]:
    dst.parent.mkdir(parents=True, exist_ok=True)
    im = Image.open(src).convert("RGBA")
    want = rgba(src.read_bytes())
    for exact in (False, True):
        buf = io.BytesIO()
        im.save(buf, format="WEBP", lossless=True, quality=100, method=6, exact=exact)
        if rgba(buf.getvalue()) == want:
            dst.write_bytes(buf.getvalue())
            return len(buf.getvalue()), exact
    raise AssertionError(f"{src}: lossless WebP differs even with exact")


def job(args: tuple[str, str, str]) -> tuple[int, bool]:
    kind, src, dst = args
    return (to_oxi if kind == "oxi" else to_webp)(Path(src), Path(dst))


def main(scenario: Path) -> None:
    with ProcessPoolExecutor() as pool:
        for mode in ("frames", "atlas", "atlas+"):
            src = scenario / f"out-{mode}"
            build = json.loads((src / "build.json").read_text())
            pngs = sorted((src / f) for f in build["files"] if f.endswith(".png"))
            for kind in ("oxi", "webp"):
                out = scenario / f"out-{mode}.{kind}"
                if out.exists():
                    shutil.rmtree(out)
                out.mkdir()
                ext = ".webp" if kind == "webp" else ".png"
                jobs = [(kind, str(p), str((out / p.relative_to(src)).with_suffix(ext))) for p in pngs]
                t = time.time()
                res = list(pool.map(job, jobs, chunksize=8))
                secs = time.time() - t
                man = json.loads((src / "manifest.json").read_text())
                files = build["files"]
                if kind == "webp":
                    for s in man["sprites"]:
                        s["path"] = s["path"][:-4] + ".webp" if s["path"].endswith(".png") else s["path"]
                    files = [f[:-4] + ".webp" if f.endswith(".png") else f for f in files]
                (out / "manifest.json").write_text(json.dumps(man, separators=(",", ":")))
                (out / "build.json").write_text(json.dumps({**build, "files": files, "optimise_seconds": secs, "optimiser": kind}, indent=1))
                print(json.dumps({
                    "scenario": scenario.name, "option": f"{mode}.{kind}", "images": len(res),
                    "image_bytes": sum(n for n, _ in res), "original_png_bytes": sum(p.stat().st_size for p in pngs),
                    "needed_exact": sum(1 for _, e in res if e), "rgba_identical": len(res), "seconds": round(secs, 1),
                }), flush=True)
    dst = scenario / "out-render.gzip"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(scenario / "out-render", dst)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
