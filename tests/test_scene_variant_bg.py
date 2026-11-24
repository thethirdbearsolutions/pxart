"""scene: --variant leaves the default --bg alone, and says so; --anchor's note stands in for the crop notes; a
map's crop count says its layers add up; @still takes one group a line (PX-48)."""
import pathlib
import sys

import pytest
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import pxart  # noqa: E402
from test_pxart import run, run_err, write  # noqa: E402

LAMP = "k #3f2631\ny #fee761\n@variant night\nk #101020\n\nk.k\nkyk\n"


def test_variant_on_the_default_bg_notes_the_backdrop(tmp_path, capsys):
    lamp = write(tmp_path, "lamp.px", LAMP)
    assert run("scene", "--size", "4x2", "--variant", "night", "-o", tmp_path / "s.png", f"{lamp}@0,0") == 0
    out = capsys.readouterr().out
    # 1 px inside the lamp (its '.') and the right-hand column (2 px) show the backdrop
    assert ("note: --variant night doesn't recolor the backdrop: 3 px show the default --bg #472d3c, a day color; "
            "give --bg a night color (or --bg transparent)") in out
    assert Image.open(tmp_path / "s.png").convert("RGBA").getpixel((3 * 4, 0)) == (0x47, 0x2d, 0x3c, 255)


def test_no_backdrop_note_when_bg_is_given_or_covered_or_no_variant(tmp_path, capsys):
    lamp = write(tmp_path, "lamp.px", LAMP)
    for extra in (["--bg", "#101018"], ["--bg", "#472d3c"]):  # an explicit --bg is the artist's, even the default
        assert run("scene", "--size", "4x2", "--variant", "night", *extra, "-o", tmp_path / "s.png", f"{lamp}@0,0") == 0
        assert "recolor the backdrop" not in capsys.readouterr().out
    assert run("scene", "--size", "4x2", "-o", tmp_path / "s.png", f"{lamp}@0,0") == 0
    assert "recolor the backdrop" not in capsys.readouterr().out
    solid = write(tmp_path, "solid.px", "k #3f2631\n@variant night\nk #101020\n\nkk\nkk\n")
    assert run("scene", "--size", "2x2", "--variant", "night", "-o", tmp_path / "s.png", f"{solid}@0,0") == 0
    assert "recolor the backdrop" not in capsys.readouterr().out


def test_anchor_leaves_out_the_crop_notes(tmp_path, capsys):
    t = write(tmp_path, "t.px", "g #43e1b3\n\ngggg\ngggg\ngggg\ngggg\n")
    m = write(tmp_path, "m.map", "t t.px\n\ntttt\ntttt\n")
    assert run("scene", "--map", m, "--tile", "4x4", "--size", "8x4", "--anchor", "center", "-o", tmp_path / "s.png") == 0
    out = capsys.readouterr().out
    assert "--anchor center: the 8x4 scene shows 4,2 to 11,5" in out
    assert "were cropped" not in out
    assert run("scene", "--map", m, "--tile", "4x4", "--size", "8x4", "-o", tmp_path / "s.png") == 0
    assert "note: 96 px of the map fall outside the 8x4 scene (size from --size) and were cropped" in capsys.readouterr().out


def test_a_layered_map_counts_each_pixel_once(tmp_path, capsys):
    t = write(tmp_path, "t.px", "g #43e1b3\n\ngggg\ngggg\ngggg\ngggg\n")
    m = write(tmp_path, "m.map", "t t.px\n\ntttt\n---\n..tt\n")  # layer 2 covers layer 1's cropped cells
    assert run("scene", "--map", m, "--tile", "4x4", "--size", "8x4", "-o", tmp_path / "s.png") == 0
    assert "note: 32 px of the map fall outside the 8x4 scene (size from --size)" in capsys.readouterr().out
    m2 = write(tmp_path, "m2.map", "t t.px\n\ntttt\n---\nt...\n")  # layer 2 wholly inside
    assert run("scene", "--map", m2, "--tile", "4x4", "--size", "8x4", "-o", tmp_path / "s.png") == 0
    assert "note: 32 px of the map fall outside" in capsys.readouterr().out


def test_tiles_bigger_than_their_cell_count_each_pixel_once(tmp_path, capsys):
    write(tmp_path, "t.px", "g #43e1b3\n\n" + "gggg\n" * 8)  # 4x8 in 4x4 cells: hangs into the row below
    m = write(tmp_path, "m.map", "t t.px\n\ntttt\ntttt\n")
    assert run("scene", "--map", m, "--tile", "4x4", "--size", "8x4", "-o", tmp_path / "s.png") == 0
    # the scene spans 16x12; the window keeps 8x4 of it: 192 - 32 = 160 distinct px outside
    assert "note: 160 px of the map fall outside the 8x4 scene" in capsys.readouterr().out


def test_an_empty_bg_is_still_refused(tmp_path, capsys):
    lamp = write(tmp_path, "lamp.px", LAMP)
    assert run("scene", "--bg", "", "-o", tmp_path / "s.png", f"{lamp}@0,0") == 1


def test_anchor_names_an_item_it_misses(tmp_path, capsys):
    solid = write(tmp_path, "solid.px", "k #3f2631\n\nkk\nkk\n")
    assert run("scene", "--size", "4x4", "--anchor", "0,0", "-o", tmp_path / "s.png", f"{solid}@0,0",
               f"{solid}@40,40") == 0
    out = capsys.readouterr().out
    assert f"note: item 2 ({solid}) is wholly outside the window, so the scene doesn't show it" in out
    assert "item 1" not in out and "were cropped" not in out


def test_an_opaque_tint_hides_the_backdrop_and_a_clear_one_isnt_named(tmp_path, capsys):
    lamp = write(tmp_path, "lamp.px", LAMP)
    assert run("scene", "--size", "4x2", "--variant", "night", "--tint", "#101830ff", "-o", tmp_path / "s.png",
               f"{lamp}@0,0") == 0
    assert "recolor the backdrop" not in capsys.readouterr().out
    assert run("scene", "--size", "4x2", "--variant", "night", "--tint", "transparent", "-o", tmp_path / "s.png",
               f"{lamp}@0,0") == 0
    out = capsys.readouterr().out
    assert "a day color; give --bg" in out and "under the --tint" not in out


@pytest.mark.parametrize("line", ["@still grass # the lawn", "@still ms=1,2", "@still a!b  # one, two"])
def test_the_list_hint_is_only_for_lists(tmp_path, capsys, line):
    f = write(tmp_path, "t.px", f"g #43e1b3\n{line}\n@frame grass/0\ng\n")
    assert run("check", f) == 1
    cap = capsys.readouterr()
    assert "E_BAD_ID" in cap.out + cap.err and "line per group" not in cap.out + cap.err


def test_still_with_a_list_says_a_line_per_group(tmp_path, capsys):
    f = write(tmp_path, "t.px", "g #43e1b3\n@still grass,path\n@frame grass/0\ng\n@frame path/0\ng\n")
    assert run("check", f) == 1
    cap = capsys.readouterr()
    err = cap.out + cap.err
    assert "@still needs one group path like ui/life" in err and "(a @still line per group)" in err


def test_help_says_bg_and_still():
    text = " ".join(pxart.__doc__.split())
    assert "--variant doesn't recolor --bg" in text and "top-level frames need none" in text


def test_under_tint_the_note_says_so(tmp_path, capsys):
    lamp = write(tmp_path, "lamp.px", LAMP)
    assert run("scene", "--size", "4x2", "--variant", "night", "--tint", "#10183080", "-o", tmp_path / "s.png",
               f"{lamp}@0,0") == 0
    assert "the default --bg #472d3c, a day color under the --tint; give --bg a night color" in capsys.readouterr().out
