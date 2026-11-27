"""onion -o marks the pixels its readout counts (PX-70): a second panel, pink where B differs from A after the best
shift, in the band when there is one, as anim's strip marks them."""
import pathlib
import re
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pxart  # noqa: E402

PINK = (255, 40, 200, 255)

# a walker whose right foot lifts 2 rows while the left stays down
WALKER = """pxart 1
k #000000
o #ff8800

@anim walk ms=100

@frame walk/0
..kk..
.kook.
.kook.
.kook.
.k..k.
.k..k.
.k..k.
@frame walk/1
..kk..
.kook.
.kook.
.kook.
.k..k.
.k....
.k....
"""


def run(*argv):
    try:
        pxart.main([str(a) for a in argv])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    return 0


def pink_at(png, scale, w, h):
    """The canvas pixels the right panel paints pink, {(x, y)}: sampled at each cell's centre."""
    img = Image.open(png).convert("RGBA")
    rulers = 16
    left_w = w * scale + rulers
    x0, y0 = left_w + 8 + rulers, rulers
    return {(x, y) for y in range(h) for x in range(w)
            if img.getpixel((x0 + x * scale + scale // 2, y0 + y * scale + scale // 2)) == PINK}


def pink_cells(png, scale, w, h):
    return len(pink_at(png, scale, w, h))


def counted(out):
    m = re.search(r"then (\d+)px changed(?: \((\d+) past the edge\))?|so no shift: (\d+)px changed", out)
    n = int(m.group(1) or m.group(3))
    return n - int(m.group(2) or 0)


def test_a_band_pair_marks_exactly_the_counted_pixels(tmp_path, capsys):
    p = tmp_path / "w.px"
    p.write_text(WALKER)
    o = tmp_path / "o.png"
    assert run("onion", f"{p}:walk/0", f"{p}:walk/1", "--feet", 3, "-o", o) == 0
    out = capsys.readouterr().out
    n = counted(out)
    assert n == 2  # the lifted foot: two pixels gone
    assert pink_at(o, 8, 6, 7) == {(4, 5), (4, 6)}  # the right foot, where it was


def test_the_whole_canvas_marks_what_it_counts_less_past_the_edge(tmp_path, capsys):
    p = tmp_path / "w.px"
    p.write_text(WALKER.replace("@frame walk/1\n..kk..\n", "@frame walk/1\n......\n..kk..\n").replace(
        ".k..k.\n.k....\n.k....\n", ".k..k.\n.k....\n"))  # B one row lower: a bob
    o = tmp_path / "o.png"
    assert run("onion", f"{p}:walk/0", f"{p}:walk/1", "-o", o) == 0
    out = capsys.readouterr().out
    assert pink_cells(o, 8, 6, 7) == counted(out)


def test_the_examples_onion_marks_its_count(tmp_path, capsys):
    ex = ROOT / "examples" / "02-animation"
    o = tmp_path / "o.png"
    assert run("onion", f"{ex}/hero.px:walk/down/0", f"{ex}/hero.px:walk/down/3", "--feet", 6, "-o", o) == 0
    out = capsys.readouterr().out
    assert pink_cells(o, 8, 24, 32) == counted(out) == 11


def test_the_label_gives_the_readouts_count_and_what_the_edge_hid(tmp_path, capsys):
    # the PNG's own words: the readout's count, and how many of them no pixel can show
    got = {}
    real = pxart.onion_panels

    def spy(left, right, scale, shown, total, how):
        got.update(shown=shown, total=total, how=how)
        return real(left, right, scale, shown, total, how)
    p = tmp_path / "w.px"
    p.write_text(WALKER.replace("@frame walk/1\n..kk..\n", "@frame walk/1\n......\n..kk..\n").replace(
        ".k..k.\n.k....\n.k....\n", ".k..k.\n.k....\n"))
    pxart.onion_panels = spy
    try:
        assert run("onion", f"{p}:walk/0", f"{p}:walk/1", "-o", tmp_path / "o.png", "--tint-a", "#40c0ff") == 0
    finally:
        pxart.onion_panels = real
    out = capsys.readouterr().out
    n = int(re.search(r"then (\d+)px changed", out).group(1))
    assert got["total"] == n and got["shown"] == counted(out) and got["how"] == "A tinted"


def test_two_different_sprites_get_no_counted_panel(tmp_path, capsys):
    a, b = tmp_path / "a.px", tmp_path / "b.px"
    a.write_text("k #000000\nkkkk\nkkkk\n")
    b.write_text("k #000000\n.k..\n....\n....\n")
    o = tmp_path / "o.png"
    assert run("onion", a, b, "-o", o) == 0
    assert "different sprites" in capsys.readouterr().out
    assert PINK not in set(pxart.pixels(Image.open(o).convert("RGBA")))


# a band whose best shift moves it a row: the rows it moved into count too, and so get marked, past the band
BAND = """pxart 1
k #000000
@anim a ms=100
@frame a/0
...k
k...
.k.k
....
kk..
..kk
@frame a/1
...k
...k
k...
.k.k
k...
kk..
"""


def test_a_band_shifted_a_row_marks_the_row_it_moved_into(tmp_path, capsys):
    p = tmp_path / "band.px"
    p.write_text(BAND)
    o = tmp_path / "o.png"
    assert run("onion", f"{p}:a/0", f"{p}:a/1", "--rows", "1-3", "-o", o) == 0
    out = capsys.readouterr().out
    assert "best shift +0,+1 then 1px changed" in out
    assert pink_at(o, 8, 4, 6) == {(0, 4)}


def test_bottom_edges_agree_marks_the_no_shift_count(tmp_path, capsys):
    ex = ROOT / "examples" / "02-animation"
    o = tmp_path / "o.png"
    assert run("onion", f"{ex}/hero.px:walk/down/0", f"{ex}/hero.px:walk/down/1", "--rows", "0-1", "-o", o) == 0
    out = capsys.readouterr().out
    assert "bottom edges agree, so no shift: 7px changed" in out
    got = pink_at(o, 8, 24, 32)
    assert len(got) == 7 and all(y <= 1 for _, y in got)


def test_the_label_counts_what_went_past_the_edge(tmp_path, capsys):
    ex = ROOT / "examples" / "02-animation"
    got = {}
    real = pxart.onion_panels

    def spy(left, right, scale, shown, total, how):
        got.update(shown=shown, total=total)
        return real(left, right, scale, shown, total, how)
    pxart.onion_panels = spy
    try:
        assert run("onion", f"{ex}/hero.px:walk/down/0", f"{ex}/hero.px:walk/down/1", "-o", tmp_path / "o.png") == 0
    finally:
        pxart.onion_panels = real
    assert "30px changed (4 past the edge)" in capsys.readouterr().out
    assert got == {"shown": 26, "total": 30}
