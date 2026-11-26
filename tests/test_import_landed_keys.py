"""crop and compose into an existing file import only the keys of pixels that land on OUT (and, with --under, show),
with each key line's comment, and only those keys can clash (PX-64)."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import pxart  # noqa: E402
from test_pxart import run_err  # noqa: E402
from test_rekey_tradeoff import run, setup  # noqa: E402

HOUSE = ("k #1b1420\nw #c0a080\n# roof shadow\nR #a03020\nb #502010\n\n"
         "@frame house\nRRRR\nRbbR\nkwwk\nkwwk\n")


def house(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pal.px").write_text("k #1b1420\nw #c0a080\n\n@variant night\nk #0a0810\nw #605040\n")
    (tmp_path / "tiles.px").write_text("@palette pal.px\n\n@frame a\nkk\nww\n")
    (tmp_path / "house.px").write_text(HOUSE)


def test_a_crop_without_the_roof_adds_no_roof_keys(tmp_path, monkeypatch, capsys):
    house(tmp_path, monkeypatch)
    assert run("crop", "house.px", "0,2,4,2", "-o", "tiles.px:wall") == 0
    doc = pxart.parse(tmp_path / "tiles.px")
    assert "R" not in doc.palette and "b" not in doc.palette
    capsys.readouterr()
    assert run("check", "tiles.px") == 0
    assert "unused" not in capsys.readouterr().out


def test_the_key_brings_its_comment(tmp_path, monkeypatch):
    house(tmp_path, monkeypatch)
    assert run("crop", "house.px", "0,0,4,1", "-o", "tiles.px:roof") == 0
    text = (tmp_path / "tiles.px").read_text()
    assert "# roof shadow\nR #a03020\n" in text and "b #" not in text


def test_compose_off_the_canvas_adds_only_what_lands(tmp_path, monkeypatch):
    house(tmp_path, monkeypatch)
    # the house drawn 2 rows up into a 4x2 frame: only its walls land
    assert run("compose", "-o", "tiles.px:c", "--size", "4x2", "house.px@0,-2") == 0
    doc = pxart.parse(tmp_path / "tiles.px")
    assert "R" not in doc.palette and "b" not in doc.palette


def test_a_key_outside_the_region_raises_no_conflict(tmp_path, monkeypatch, capsys):
    setup(tmp_path, monkeypatch)
    (tmp_path / "q.px").write_text("L #3a7d44\nE #2b5f8a\nF #ffffff\n\nLE\nFF\n")  # F clashes, but isn't copied
    assert run("crop", "q.px", "0,0,2,1", "-o", "tiles.px:d") == 0
    out = capsys.readouterr().out
    assert "E_KEY_CONFLICT" not in out and "'F>" not in out


def test_a_key_in_the_region_still_conflicts(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    (tmp_path / "q.px").write_text("L #3a7d44\nE #2b5f8a\nF #ffffff\n\nLE\nFF\n")
    assert "E_KEY_CONFLICT" in run_err("crop", "q.px", "0,0,2,2", "-o", "tiles.px:d")


def test_under_warns_only_for_pixels_that_show(tmp_path, monkeypatch, capsys):
    setup(tmp_path, monkeypatch)  # tiles.px frame a is full: LLLL/LEEL/FDDF/SSSS
    assert run("compose", "-o", "tiles.px:a", "--under", "quarter.px@0,0") == 0
    out = capsys.readouterr().out
    assert "WARNING" not in out and "--rekey" not in out


def test_under_adds_only_the_keys_that_show(tmp_path, monkeypatch):
    house(tmp_path, monkeypatch)  # tiles.px frame a: kk / ww; frame b gets one empty pixel to show through
    (tmp_path / "tiles.px").write_text("@palette pal.px\n\n@frame a\nkk\nww\n@frame b\nk.\nww\n")
    (tmp_path / "s.px").write_text("# shadow\nx #20202080\nZ #ff00ff\n\nZx\nZZ\n")  # only x lands on b's '.'
    assert run("compose", "-o", "tiles.px:b", "--under", "s.px@0,0") == 0
    text = (tmp_path / "tiles.px").read_text()
    assert "# shadow\nx #20202080" in text and "Z #" not in text


def test_a_new_out_still_conflicts_on_a_key_its_file_needs(tmp_path, monkeypatch):
    # a new OUT is seeded from the layers' whole files: a key cropped away there still clashes (review finding 1)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "l1.px").write_text("a #ff0000\n@frame x\naa\n")
    (tmp_path / "l4.px").write_text("a #0000ff\nb #00ff00\n@frame y\nbb\naa\n@frame z\na\n")
    assert "E_KEY_CONFLICT" in run_err("compose", "-o", "f.px", "--size", "2x1", "l1.px:x@0,0", "l4.px:y@0,0")


def test_two_layers_of_one_file_carry_its_comment_once(tmp_path, monkeypatch):
    house(tmp_path, monkeypatch)
    (tmp_path / "w.px").write_text("# walls\nX #c0b090\nx #a09070\n\n@frame a\nx\n@frame b\nX\n")
    assert run("compose", "-o", "tiles.px:c", "--size", "2x1", "w.px:a@0,0", "w.px:b@1,0") == 0
    text = (tmp_path / "tiles.px").read_text()
    assert text.count("# walls") == 1


def test_variant_lines_follow_the_new_keys_order(tmp_path, monkeypatch):
    house(tmp_path, monkeypatch)
    (tmp_path / "n.px").write_text("z #101010\na #202020\n\n@variant night\nz #000000\na #010101\n\nza\n")
    assert run("compose", "-o", "tiles.px:c", "--size", "2x1", "n.px@0,0") == 0
    doc = pxart.parse(tmp_path / "tiles.px")
    assert [k for k in doc.palette if k in "za"] == ["z", "a"] == [k for k in doc.variants["night"] if k in "za"]


@pytest.mark.parametrize("cmd", [["crop", "house.px", "0,2,4,2", "-o", "tiles.px:wall"],
                                 ["compose", "-o", "tiles.px:c", "--size", "4x2", "house.px@0,-2"]])
def test_check_is_quiet_after(tmp_path, monkeypatch, capsys, cmd):
    house(tmp_path, monkeypatch)
    assert run(*cmd) == 0
    capsys.readouterr()
    assert run("check", "tiles.px", "--strict") == 0


LAMP = ("# lamp glass, lit\nl #ffe080\nm #ffc040\n# walls\nX #c0b090\nx #a09070\n# window glass\nG #80c0e0\n"
        "g #4080a0\n\n@frame lamp\nmXx\ngGX\n")


def test_keys_keep_their_source_order_under_their_comments(tmp_path, monkeypatch):
    house(tmp_path, monkeypatch)
    (tmp_path / "lamp.px").write_text(LAMP)
    assert run("compose", "-o", "tiles.px:l", "--size", "3x2", "lamp.px@0,0") == 0
    text = (tmp_path / "tiles.px").read_text()
    # l isn't copied: its comment goes to m, the first of its block that is; X x and G g stay under theirs
    assert "# lamp glass, lit\nm #ffc040\n# walls\nX #c0b090\nx #a09070\n# window glass\nG #80c0e0\ng #4080a0\n" in text


def test_a_top_level_frame_names_where_its_size_came_from(tmp_path, monkeypatch, capsys):
    house(tmp_path, monkeypatch)
    assert run("compose", "-o", "tiles.px:c", "house.px@0,-1") == 0
    out = capsys.readouterr().out
    assert "the rest of ''" not in out and "size from the file's other top-level frames" in out
