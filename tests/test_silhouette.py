"""render and sheet --silhouette (PX-31): every pixel that draws in one flat color, at its own alpha; a transparent
pixel stays transparent; with --variant, that variant's shape."""
import pathlib
import sys

import pytest
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pxart  # noqa: E402

SPRITE = """pxart 1
k #3f2631
g #43e1b3
h transparent
f #ff000080

@variant night
h #f6e45a

@frame a
.kk.
kggk
.ff.
h..h
"""


def run(*argv):
    try:
        pxart.main([str(a) for a in argv])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    return 0


def plain(tmp_path, *extra):
    src = tmp_path / "s.px"
    src.write_text(SPRITE)
    out = tmp_path / "o.png"
    assert run("render", f"{src}:a", "--plain", "-o", out, *extra) == 0
    return Image.open(out).convert("RGBA")


def test_opaque_pixels_take_the_default_color_and_transparent_ones_stay(tmp_path):
    img = plain(tmp_path, "--silhouette")
    assert img.getpixel((1, 0)) == (0x2b, 0x1d, 0x32, 255)   # k
    assert img.getpixel((1, 1)) == (0x2b, 0x1d, 0x32, 255)   # g: another color, the same silhouette
    assert img.getpixel((0, 0))[3] == 0                      # '.'
    assert img.getpixel((0, 3))[3] == 0                      # h, transparent in the base


def test_a_pixel_keeps_its_own_alpha(tmp_path):
    assert plain(tmp_path, "--silhouette").getpixel((1, 2)) == (0x2b, 0x1d, 0x32, 0x80)


def test_a_color_of_its_own_and_one_with_alpha(tmp_path):
    assert plain(tmp_path, "--silhouette", "#ffffff").getpixel((1, 0)) == (255, 255, 255, 255)
    assert plain(tmp_path, "--silhouette", "#ffffff80").getpixel((1, 0)) == (255, 255, 255, 0x80)


def test_with_a_variant_its_shape(tmp_path):
    img = plain(tmp_path, "--silhouette", "--variant", "night")
    assert img.getpixel((0, 3)) == (0x2b, 0x1d, 0x32, 255)   # h is lit at night


def test_a_bad_color_is_an_error(tmp_path):
    src = tmp_path / "s.px"
    src.write_text(SPRITE)
    with pytest.raises(SystemExit) as e:
        pxart.main(["render", str(src), "--silhouette", "nope", "-o", str(tmp_path / "o.png")])
    assert "E_BAD_COLOR" in str(e.value.code) and "--silhouette" in str(e.value.code)


def test_sheet_draws_silhouettes_and_says_so(tmp_path, capsys):
    src = tmp_path / "s.px"
    src.write_text(SPRITE)
    plain_out, color_out = tmp_path / "p.png", tmp_path / "c.png"
    assert run("sheet", src, "--plain", "--bg", "transparent", "--silhouette", "-o", plain_out) == 0
    assert run("sheet", src, "--plain", "--bg", "transparent", "-o", color_out) == 0
    sil, col = Image.open(plain_out).convert("RGBA"), Image.open(color_out).convert("RGBA")
    assert sil.size == col.size
    changed = [(s, c) for s, c in zip(sil.getdata(), col.getdata()) if s != c]
    assert changed  # the frame's pixels, and nothing else of the sheet (its gutter is the same)
    assert {s[:3] for s, _ in changed} == {(0x2b, 0x1d, 0x32)}
    assert all(s[3] == c[3] for s, c in changed)  # drawn where the colored sheet draws, at its alpha
    capsys.readouterr()
    assert run("sheet", src, "--silhouette", "-o", tmp_path / "l.png", "--dry-run") == 0
    assert not (tmp_path / "l.png").exists()
    assert run("render", src, "--silhouette", "-o", tmp_path / "r.png") == 0  # a real run after: DRY is reset


def test_the_label_says_silhouette(tmp_path):
    src = tmp_path / "s.px"
    src.write_text(SPRITE)
    its = pxart.silhouetted(pxart.all_items([str(src)], "night"), None)
    assert its[0].label == "a%night silhouette"


def test_a_bare_silhouette_before_the_files_takes_no_file_as_its_color(tmp_path):
    src = tmp_path / "s.px"
    src.write_text(SPRITE)
    out = tmp_path / "o.png"
    assert run("render", "--silhouette", f"{src}:a", "--plain", "-o", out) == 0
    assert Image.open(out).convert("RGBA").getpixel((1, 0)) == (0x2b, 0x1d, 0x32, 255)
    assert run("sheet", "--silhouette", src, src, "--plain", "-o", tmp_path / "sh.png") == 0
    assert run("render", f"{src}:a", "--plain", "--silhouette", "ffffff", "-o", out) == 0  # a color without '#'
    assert Image.open(out).convert("RGBA").getpixel((1, 0)) == (255, 255, 255, 255)


def test_a_color_that_draws_nothing_is_an_error(tmp_path):
    src = tmp_path / "s.px"
    src.write_text(SPRITE)
    for c in ("transparent", "#ffffff00"):
        with pytest.raises(SystemExit) as e:
            pxart.main(["render", str(src), "--silhouette", c, "-o", str(tmp_path / "o.png")])
        assert "E_BAD_COLOR" in str(e.value.code) and "draws nothing" in str(e.value.code)


def test_png_with_silhouette_says_the_png_is_in_color(tmp_path, capsys):
    src = tmp_path / "s.px"
    src.write_text(SPRITE)
    assert run("render", src, "--silhouette", "--png", tmp_path, "-o", tmp_path / "o.png") == 0
    assert "--png writes each file's colors at 1x" in capsys.readouterr().out
    assert Image.open(tmp_path / "s.png").convert("RGBA").getpixel((1, 0)) == (0x3f, 0x26, 0x31, 255)


def test_a_bare_silhouette_before_a_directory(tmp_path):
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "s.px").write_text(SPRITE)
    assert run("sheet", "--silhouette", tmp_path / "d", "-o", tmp_path / "sh.png") == 0


def test_the_default_render_draws_the_silhouette_too(tmp_path):
    src = tmp_path / "s.px"
    src.write_text(SPRITE)
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    assert run("render", f"{src}:a", "--silhouette", "-o", a) == 0
    assert run("render", f"{src}:a", "-o", b) == 0
    sil, col = set(Image.open(a).convert("RGBA").getdata()), set(Image.open(b).convert("RGBA").getdata())
    assert (0x43, 0xe1, 0xb3, 255) in col and (0x43, 0xe1, 0xb3, 255) not in sil  # g is gone
    assert (0x2b, 0x1d, 0x32, 255) in sil and (0x2b, 0x1d, 0x32, 255) not in col


def test_a_png_on_a_flat_backdrop_is_not_one_rectangle(tmp_path, capsys):
    png = tmp_path / "lamp.png"
    img = Image.new("RGBA", (4, 4), (58, 58, 68, 255))
    img.putpixel((1, 1), (255, 200, 0, 255))
    img.save(png)
    out = tmp_path / "o.png"
    assert run("render", png, "--plain", "--silhouette", "-o", out) == 0
    got = Image.open(out).convert("RGBA")
    assert got.getpixel((1, 1)) == (0x2b, 0x1d, 0x32, 255) and got.getpixel((0, 0))[3] == 0
    assert "takes that color as the backdrop" in capsys.readouterr().out


def test_a_gif_or_upper_case_file_after_a_bare_flag(tmp_path):
    src = tmp_path / "S.PX"
    src.write_text(SPRITE)
    gif = tmp_path / "one.gif"
    Image.new("RGBA", (2, 2), (255, 0, 0, 255)).save(gif)
    assert run("sheet", "--silhouette", gif, src, "-o", tmp_path / "a.png") == 0
    assert run("sheet", "--silhouette", src, "-o", tmp_path / "b.png") == 0


def test_the_label_counts_alpha_levels(tmp_path):
    src = tmp_path / "s.px"
    src.write_text(SPRITE)
    its = pxart.silhouetted(pxart.all_items([f"{src}:a"]), None)
    assert len(pxart.colors(its[0].img)) == 2  # solid and the 50% f: one color, two alphas
