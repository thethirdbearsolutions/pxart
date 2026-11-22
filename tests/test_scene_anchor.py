"""scene --anchor: which part of a bigger scene a smaller --size keeps (PX-36). The default stays the top-left, x,y as
typed; an agent expecting the centre can say so."""
import pathlib
import sys

import pytest
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import pxart  # noqa: E402

BOX = "k #000000\nr #ff0000\n\nkkkk\nkrrk\nkrrk\nkkkk\n"
RED, BLACK, BG = (255, 0, 0, 255), (0, 0, 0, 255), (0x47, 0x2d, 0x3c, 255)


def run(*argv):
    try:
        pxart.main([str(a) for a in argv])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    return 0


@pytest.fixture
def box(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "box.px").write_text(BOX)
    return tmp_path


def px(path, *xy):
    img = Image.open(path).convert("RGBA")
    return [img.getpixel(p) for p in xy]


def test_default_keeps_the_top_left(box, capsys):
    assert run("scene", "--size", "4x4", "--scale", "1", "-o", "a.png", "box.px@0,0", "box.px@8,8") == 0
    assert px("a.png", (0, 0), (1, 1)) == [BLACK, RED]
    assert "--anchor" not in capsys.readouterr().out


@pytest.mark.parametrize("anchor, at, want", [
    ("center", (4, 4), [BG, BG]),             # the gap between the boxes: 4..7 of 0..11
    ("bottom-right", (8, 8), [BLACK, RED]),   # the second box
    ("right", (8, 4), [BG, BG]),
    ("bottom", (4, 8), [BG, BG]),
])
def test_anchor_picks_the_window(box, capsys, anchor, at, want):
    assert run("scene", "--size", "4x4", "--scale", "1", "-o", "a.png", "box.px@0,0", "box.px@8,8",
               "--anchor", anchor) == 0
    out = capsys.readouterr().out
    assert f"note: --anchor {anchor}: the 4x4 scene shows {at[0]},{at[1]} to {at[0] + 3},{at[1] + 3} of the 12x12 " \
           "the items fill" in out
    assert px("a.png", (0, 0), (1, 1)) == want


def test_center_on_a_map(box, capsys):
    (box / "room.map").write_text("b box.px\n\nbbb\nbbb\nbbb\n")
    assert run("scene", "--map", "room.map", "--tile", "4", "--size", "4x4", "--scale", "1", "-o", "m.png",
               "--anchor", "center") == 0
    assert "shows 4,4 to 7,7 of the 12x12 the map and items fill" in capsys.readouterr().out
    assert px("m.png", (0, 0), (1, 1)) == [BLACK, RED]


def test_a_bigger_size_centres_the_scene_in_it(box):
    assert run("scene", "--size", "8x8", "--scale", "1", "-o", "a.png", "box.px@0,0", "--anchor", "center") == 0
    assert px("a.png", (0, 0), (2, 2), (3, 3)) == [BG, BLACK, RED]  # the 4x4 box sits at 2,2


def test_bad_anchor(box, capsys):
    assert run("scene", "--size", "4x4", "-o", "a.png", "box.px@0,0", "--anchor", "middle") == 2
    assert "argument --anchor: invalid choice: 'middle'" in capsys.readouterr().err
