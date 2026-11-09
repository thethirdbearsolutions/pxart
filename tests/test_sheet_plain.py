"""sheet --plain (CZY-2504): no text, a fixed integer layout, a true 1x beside each scaled copy (--with-1x), PNG
inputs placed as they are, a JSON sidecar of every image's rect (--cells), and ticks in the gutter (--ticks)."""
import json
import pathlib
import sys

import pytest
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pxart  # noqa: E402

EX = ROOT / "examples"
GEM = EX / "01-format" / "gem.px"
BARREL = EX / "01-format" / "barrel.px"
LAMP_PNG = EX / "01-format" / "lamp.png"
HERO = EX / "02-animation" / "hero.px"


def run(*argv):
    try:
        pxart.main([str(a) for a in argv])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    return 0


def run_err(*argv):
    with pytest.raises(SystemExit) as e:
        pxart.main([str(a) for a in argv])
    assert not isinstance(e.value.code, int) or e.value.code != 0
    return str(e.value.code)


def plain(tmp_path, *inputs, extra=(), name="sheet"):
    out, cells = tmp_path / f"{name}.png", tmp_path / f"{name}.json"
    assert run("sheet", *inputs, "--plain", "--with-1x", "--scale", 4, "--bg", "transparent",
               "--cells", cells, "-o", out, *extra) == 0
    return Image.open(out).convert("RGBA"), json.loads(cells.read_text())


def crop(img, r):
    return img.crop((r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"]))


def same(a, b):
    """Two RGBA images equal pixel for pixel (a transparent pixel is transparent, whatever its RGB)."""
    def norm(im):
        im = im.convert("RGBA")
        data = im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata()
        return [p if p[3] else (0, 0, 0, 0) for p in data]
    return a.size == b.size and norm(a) == norm(b)


def rendered(tmp_path, arg, scale=1):
    out = tmp_path / f"r{abs(hash((str(arg), scale)))}.png"
    assert run("render", arg, "--plain", "--scale", scale, "-o", out) == 0
    return Image.open(out).convert("RGBA")


INPUTS = (GEM, BARREL, f"{HERO}:walk/down/0", LAMP_PNG)


def test_each_1x_rect_is_the_frame_at_its_true_size(tmp_path):
    img, data = plain(tmp_path, *INPUTS)
    pxs = [c for c in data["cells"] if c["kind"] == "px"]
    assert len(pxs) == 3
    for arg, c in zip((GEM, BARREL, f"{HERO}:walk/down/0"), pxs):
        assert same(crop(img, c["x1"]), rendered(tmp_path, arg)), c


def test_each_scaled_copy_downsamples_to_the_exact_1x(tmp_path):
    img, data = plain(tmp_path, *INPUTS)
    for c in data["cells"]:
        if c["kind"] != "px":
            continue
        big, small = crop(img, c["xN"]), crop(img, c["x1"])
        assert big.size == (small.width * 4, small.height * 4)
        assert same(big, small.resize(big.size, Image.NEAREST))
        assert same(big.resize(small.size, Image.NEAREST), small)


def test_a_png_is_placed_as_it_is(tmp_path):
    img, data = plain(tmp_path, *INPUTS)
    png = [c for c in data["cells"] if c["kind"] == "png"]
    assert len(png) == 1 and png[0]["x1"] is None and png[0]["scale"] == 1
    assert png[0]["file"] == str(LAMP_PNG)
    assert same(crop(img, png[0]["xN"]), Image.open(LAMP_PNG))


def test_no_text_anywhere_outside_the_images(tmp_path):
    img, data = plain(tmp_path, *INPUTS)
    inside = set()
    for c in data["cells"]:
        for r in (c["x1"], c["xN"]):
            if r:
                inside |= {(x, y) for x in range(r["x"], r["x"] + r["w"]) for y in range(r["y"], r["y"] + r["h"])}
    px = img.load()
    stray = [(x, y) for y in range(img.height) for x in range(img.width)
             if (x, y) not in inside and px[x, y] != pxart.PLAIN_CANVAS]
    assert stray == []


def test_ids_live_in_the_sidecar(tmp_path):
    _, data = plain(tmp_path, *INPUTS)
    assert [c["frame"] for c in data["cells"]] == [None, None, "walk/down/0", None]
    assert data["scale"] == 4 and data["with_1x"] is True and data["pad"] == pxart.PLAIN_PAD


def test_geometry_is_fixed_and_documented(tmp_path):
    img, data = plain(tmp_path, *INPUTS)
    _, again = plain(tmp_path, *INPUTS, name="again")
    for k in ("size", "cell", "cells"):
        assert data[k] == again[k]
    # every cell: the largest .px frame (hero, 24x32) as a 1x slot, PLAIN_PAD, and its 4x copy
    pad = pxart.PLAIN_PAD
    assert data["cell"] == {"w": 24 + pad + 96, "h": 128}
    assert data["size"] == {"w": pad + 4 * (data["cell"]["w"] + pad), "h": pad + 128 + pad}
    assert (img.width, img.height) == (data["size"]["w"], data["size"]["h"])
    # bottom-aligned, centered rounding left
    gem = data["cells"][0]
    assert gem["xN"] == {"x": pad + 24 + pad + (96 - 36) // 2, "y": pad + 128 - 32, "w": 36, "h": 32}


def test_rows_file_puts_each_file_on_its_own_row(tmp_path):
    _, data = plain(tmp_path, f"{HERO}:walk/down/0", f"{HERO}:walk/down/1", GEM, extra=("--rows", "file"))
    ys = [c["xN"]["y"] + c["xN"]["h"] for c in data["cells"]]  # each image's bottom: its row's
    assert ys[0] == ys[1] != ys[2]


def test_ticks_stay_in_the_gutter(tmp_path):
    img, data = plain(tmp_path, GEM, BARREL)
    ticked, data2 = plain(tmp_path, GEM, BARREL, extra=("--ticks", 8), name="ticked")
    assert data2["cells"] == data["cells"]
    for c in data["cells"]:
        for r in (c["x1"], c["xN"]):
            assert same(crop(img, r), crop(ticked, r))  # the art is untouched
    assert img.tobytes() != ticked.tobytes()  # and the ticks are there, outside it


def test_plain_only_flags_need_plain(tmp_path):
    for flag in (("--with-1x",), ("--cells", tmp_path / "c.json"), ("--ticks", 8)):
        assert "add --plain" in run_err("sheet", GEM, *flag, "-o", tmp_path / "s.png")
    assert "--fit" in run_err("sheet", GEM, "--plain", "--fit", "-o", tmp_path / "s.png")
    assert "--grid" in run_err("sheet", GEM, "--plain", "--grid", "-o", tmp_path / "s.png")
    assert "1 px or more" in run_err("sheet", GEM, "--plain", "--ticks", 0, "-o", tmp_path / "s.png")


def test_dry_run_writes_nothing(tmp_path, capsys):
    out, cells = tmp_path / "s.png", tmp_path / "s.json"
    assert run("sheet", GEM, "--plain", "--with-1x", "--cells", cells, "-o", out, "--dry-run") == 0
    assert not out.exists() and not cells.exists()
    assert "no text" in capsys.readouterr().out


def test_help_plain_is_its_own_topic(capsys):
    assert run("help", "plain") == 0
    out = capsys.readouterr().out
    assert out.startswith("PLAIN SHEETS (pxart help plain)") and "--with-1x" in out and '"xN"' in out
    doc = " ".join(pxart.__doc__.split())
    assert "[--rows cols|group|file]" in doc and "'pxart help plain'" in doc
