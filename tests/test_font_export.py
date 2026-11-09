"""export --font (CZY-2550): a .px of glyph frames to a pixel font (.woff2, .woff, .ttf). The frame id is the glyph's
name, @font sets the metrics, @kern or --kern the kerning; ink is every pixel that isn't transparent, traced into
union outlines, 1 px = unit font units."""
import io
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pxart  # noqa: E402

pytest.importorskip("fontTools")
from fontTools.pens.boundsPen import BoundsPen  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402

TINY = """pxart 1
X #2b1e2f
o #2b1e2f80

@frame H
XX..XX.
XX..XX.
XXXXXX.
XX..XX.
XX..XX.
.......
.......

@frame x
.......
.......
XX..XX.
.XXXX..
XX..XX.
.......
.......

@frame j
...
...
.X.
.X.
.X.
.X.
X..

@frame period
...
...
...
...
Xo.
...
...

@frame space
...
...
...
...
...
...
...

@frame underscore
....
....
....
....
....
XXX.
....

@frame dot
....
....
....
.X..
....
....
....

@font
family Tiny Sans
weight 700
baseline 5
ascent 6
descent 2
map dot U+2022 U+00B7

@kern
x j -1
"""


def run(*argv):
    """0, or the error lines main exits with (sys.exit prints them to stderr)."""
    try:
        pxart.main([str(a) for a in argv])
    except SystemExit as e:
        if not isinstance(e.code, int):
            sys.stderr.write(f"{e.code}\n")
            return 1
        return e.code
    return 0


def line_of(text, line):
    """The 1-based number of the line of text that is line."""
    return text.splitlines().index(line) + 1


def write(tmp_path, text, name="tiny.px"):
    p = tmp_path / name
    p.write_text(text)
    return p


def export(tmp_path, capsys, src, out="tiny.ttf", *extra):
    code = run("export", src, "--font", tmp_path / out, *extra)
    return code, capsys.readouterr()


def test_round_trip_cmap_advances_and_outlines(tmp_path, capsys):
    code, got = export(tmp_path, capsys, write(tmp_path, TINY))
    assert code == 0, got.err
    assert "wrote" in got.out and "7 glyphs, 1 kerning pair," in got.out
    font = TTFont(str(tmp_path / "tiny.ttf"))
    assert font.getGlyphOrder() == [".notdef", "H", "x", "j", "period", "space", "underscore", "dot"]
    assert font.getBestCmap() == {0x48: "H", 0x78: "x", 0x6A: "j", 0x2E: "period", 0x20: "space", 0x5F: "underscore", 0x2022: "dot",
                                  0xB7: "dot"}
    assert font["head"].unitsPerEm == 700  # 7 rows of 100 units
    hmtx = font["hmtx"]
    assert {g: hmtx[g][0] for g in ["H", "x", "j", "period", "space", "dot"]} == \
        {"H": 700, "x": 700, "j": 300, "period": 300, "space": 300, "dot": 400}
    gs = font.getGlyphSet()

    def bounds(name):
        pen = BoundsPen(gs)
        gs[name].draw(pen)
        return pen.bounds
    # rows 0-4 sit above the baseline (row 4 on it), rows 5-6 below; 1 px = 100 units
    assert bounds("H") == (0, 0, 600, 500)
    assert bounds("x") == (0, 0, 600, 300)
    assert bounds("j") == (0, -200, 200, 300)
    assert bounds("period") == (0, 0, 200, 100)  # the half-transparent 'o' is ink too
    assert bounds("space") is None
    assert bounds("dot") == (100, 100, 200, 200)
    # one union outline per connected run of ink: H is one contour with no seams between its pixels
    assert font["glyf"]["H"].numberOfContours == 1 and len(font["glyf"]["H"].coordinates) == 12
    assert font["OS/2"].sCapHeight == 500 and font["OS/2"].sxHeight == 300 and font["OS/2"].usWeightClass == 700
    assert (font["hhea"].ascent, font["hhea"].descent) == (600, -200)
    names = font["name"]
    assert names.getDebugName(1) == "Tiny Sans" and names.getDebugName(2) == "Bold"
    assert names.getDebugName(6) == "TinySans-Bold"
    gpos = font["GPOS"].table.LookupList.Lookup[0].SubTable[0]
    assert gpos.Coverage.glyphs == ["x"]
    assert gpos.PairSet[0].PairValueRecord[0].SecondGlyph == "j"
    assert gpos.PairSet[0].PairValueRecord[0].Value1.XAdvance == -100


def test_kern_file_and_woff2(tmp_path, capsys):
    pytest.importorskip("brotli")
    src = write(tmp_path, TINY.replace("@kern\nx j -1\n", ""))
    kern = tmp_path / "tiny.kern"
    kern.write_text("# a comment\n\nx jj -1\nx j 0\n")
    code, got = export(tmp_path, capsys, src, "web/tiny.woff2", "--kern", kern)
    assert code == 0, got.err
    assert "1 kerning pair," in got.out  # a later line wins a pair
    font = TTFont(str(tmp_path / "web" / "tiny.woff2"))
    assert font.flavor == "woff2" and font.getBestCmap()[0x48] == "H"


def test_touching_kern_pair_is_refused(tmp_path, capsys):
    text = TINY.replace("x j -1", "x j -1\nH H -2")
    src = write(tmp_path, text)
    code, got = export(tmp_path, capsys, src)
    assert code != 0 and not (tmp_path / "tiny.ttf").exists()
    lines = [l for l in got.err.splitlines() if "E_" in l]
    assert len(lines) == 1, got.err
    assert f"{src}:{line_of(text, 'H H -2')}: E_KERN: H H -2: the glyphs touch at row 0" in lines[0]


def test_corner_touch_is_refused_from_a_kern_file(tmp_path, capsys):
    # a period kerned -1 against an underscore: their pixels meet only at a corner, still a touch
    kern = tmp_path / "k.kern"
    kern.write_text("# ok\n. _ -1\n")
    code, got = export(tmp_path, capsys, write(tmp_path, TINY), "tiny.ttf", "--kern", kern)
    assert code != 0 and f"{kern}:2: E_KERN: period underscore -1: the glyphs touch at row 4" in got.err


def test_same_bytes_every_time(tmp_path, capsys):
    src = write(tmp_path, TINY)
    assert export(tmp_path, capsys, src, "a.ttf")[0] == 0
    assert export(tmp_path, capsys, src, "b.ttf")[0] == 0
    assert (tmp_path / "a.ttf").read_bytes() == (tmp_path / "b.ttf").read_bytes()
    if pytest.importorskip("brotli"):
        assert export(tmp_path, capsys, src, "a.woff2")[0] == 0
        assert export(tmp_path, capsys, src, "b.woff2")[0] == 0
        assert (tmp_path / "a.woff2").read_bytes() == (tmp_path / "b.woff2").read_bytes()


def test_missing_mapping_is_reported_cleanly(tmp_path, capsys):
    text = TINY.replace("map dot U+2022 U+00B7\n", "").replace("@frame space", "@frame gap")
    text = text.replace("weight 700", "wieght 700")
    src = write(tmp_path, text)
    code, got = export(tmp_path, capsys, src)
    assert code != 0 and not (tmp_path / "tiny.ttf").exists()
    err = [l for l in got.err.splitlines() if "E_" in l]
    assert any(f"{src}:{line_of(text, '@frame gap')}: E_GLYPH (frame gap): no character for 'gap'" in l
               and "map gap U+XXXX" in l
               for l in err), got.err
    assert any(f"{src}:{line_of(text, '@frame dot')}: E_GLYPH (frame dot): no character for 'dot'" in l for l in err), got.err
    assert any(f"{src}:{line_of(text, 'wieght 700')}: E_FONT: @font has no 'wieght'" in l and "did you mean 'weight'?" in l for l in err), got.err
    assert len(err) == 3  # every problem at once


def test_glyph_errors_heights_and_claims(tmp_path, capsys):
    text = TINY.replace("@frame j\n...\n", "@frame j\n").replace("@frame dot", "@frame uni0048")
    code, got = export(tmp_path, capsys, write(tmp_path, text))
    assert code != 0
    assert "E_GLYPH (frame j): 6 rows; every glyph is the font's height, 7" in got.err
    assert "E_GLYPH (frame uni0048): U+0048 is H's already" in got.err
    assert "E_FONT" in got.err and "map dot: no frame 'dot'" in got.err


def test_select_and_bad_args(tmp_path, capsys):
    src = write(tmp_path, TINY.replace("@kern\nx j -1\n", ""))
    code, got = export(tmp_path, capsys, f"{src}:H,x")
    assert code == 0 and "2 glyphs" in got.out
    for argv, want in [((src, "--font", tmp_path / "a.otf"), "name a .woff2"),
                       ((src, "--font", tmp_path / "a.ttf", "--frames", tmp_path / "f"), "--font writes a font alone"),
                       ((src, "--kern", tmp_path / "k.kern"), "--kern goes with --font"),
                       ((src, src, "--font", tmp_path / "a.ttf"), None)]:
        code = run("export", *argv)
        err = capsys.readouterr().err
        if want:
            assert code != 0 and want in err, err
        else:
            assert code == 0  # one file named twice is one file


def test_missing_fonttools_says_how_to_install(tmp_path, capsys, monkeypatch):
    import builtins
    real = builtins.__import__

    def no_fonttools(name, *a, **k):
        if name.split(".")[0] in ("fontTools", "brotli"):
            raise ImportError(name)
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", no_fonttools)
    code, got = export(tmp_path, capsys, write(tmp_path, TINY))
    assert code != 0 and 'E_FONT: export --font needs fontTools: pip install "pxart[font]"' in got.err


def test_font_sections_pass_check_strict(tmp_path, capsys):
    src = write(tmp_path, TINY)
    assert run("check", "--strict", src) == 0
    doc = pxart.parse(src)
    assert "@font" in doc.text() and "x j -1" in doc.text()


def test_help_fonts_and_pyproject():
    assert pxart.FONTS.startswith("FONTS (pxart help fonts)")
    assert "--font" in pxart.__doc__ and "help fonts" in pxart.__doc__
    assert 'font = ["fonttools", "brotli"]' in (ROOT / "pyproject.toml").read_text()
