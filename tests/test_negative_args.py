"""Negative coordinates after a flag, or as a positional, are values, not options (PX-52)."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import pxart  # noqa: E402
from test_pxart import run, run_err, write  # noqa: E402

GRID = "k #3f2631\ng #43e1b3\n\n" + "gggggggg\n" * 4


def rows(path):
    return [l for l in path.read_text().splitlines() if l and set(l) <= set("kg.")]


@pytest.mark.parametrize("typed,eq", [(["--keep-circle", "-2,-1,4"], ["--keep-circle=-2,-1,4"]),
                                      (["--keep", "-1,-1,3,3"], ["--keep=-1,-1,3,3"])])
def test_mask_takes_a_negative_value_after_the_flag(tmp_path, typed, eq):
    a, b = write(tmp_path, "a.px", GRID), write(tmp_path, "b.px", GRID)
    assert run("mask", a, *typed) == 0
    assert run("mask", b, *eq) == 0
    assert rows(a) == rows(b) and rows(a) != rows(write(tmp_path, "c.px", GRID))


def test_rect_and_line_take_negative_points(tmp_path):
    f = write(tmp_path, "a.px", GRID)
    assert run("rect", f, "k", "-2,-2,5,5", "--fill") == 0
    assert rows(f)[0] == "kkkggggg"  # x -2..2 clipped to 0..2
    g = write(tmp_path, "b.px", GRID)
    assert run("line", g, "k", "-3,0", "4,0") == 0
    assert rows(g)[0] == "kkkkkggg"


def test_scene_anchor_negative_as_typed(tmp_path, capsys):
    f = write(tmp_path, "a.px", GRID)
    assert run("scene", "--size", "8x4", "--anchor", "-2,1", "-o", tmp_path / "s.png", f"{f}@0,0") == 0
    assert "note: --anchor -2,1: the 8x4 scene shows -6,-1 to 1,2" in capsys.readouterr().out


def test_a_dash_value_that_isnt_a_number_says_to_use_equals(tmp_path, capsys):
    f = write(tmp_path, "a.px", GRID)
    with pytest.raises(SystemExit):
        pxart.main(["palette", str(f), "--variant", "night", "--derive-from", "base", "--keep-lit", "-,k"])
    assert ("argument --keep-lit: expected one argument (a value starting with '-' goes after '=': --keep-lit=-,k)"
            in capsys.readouterr().err)


def test_a_missing_value_gets_no_equals_hint(tmp_path, capsys):
    f = write(tmp_path, "a.px", GRID)
    with pytest.raises(SystemExit):
        pxart.main(["mask", str(f), "--keep-circle"])
    err = capsys.readouterr().err
    assert "expected one argument" in err and "goes after '='" not in err


def test_no_option_looks_like_a_negative_number():
    ap, sub = pxart.parser(describe=False)
    for name, p in [("pxart", ap), *sub.choices.items()]:
        opts = [o for a in p._actions for o in a.option_strings]
        assert not [o for o in opts if pxart.NEGATIVE_RE.match(o)], name


def test_shift_region_off_the_top_left_is_clipped_not_wrapped(tmp_path):
    f = write(tmp_path, "h.px", "k #ff0000\ng #00ff00\n\nkgkg\nkgkg\n")
    assert run("shift", f, "0", "0", "--region", "-2,0,3,2") == 0
    assert rows(f) == ["kgkg", "kgkg"]  # a zero shift changes nothing (it erased columns 2-3)
    assert run("shift", f, "1", "0", "--region", "-2,0,3,2") == 0  # the region is x 0..0 on the frame
    assert rows(f) == [".kkg", ".kkg"]  # its one column moves right onto x 1
    g = write(tmp_path, "g.px", "k #ff0000\ng #00ff00\n\nkkkk\ngggg\nkkkk\ngggg\n")
    assert run("shift", g, "0", "-1", "--region", "0,-3,4,5") == 0  # rows 0..1 on the frame
    assert rows(g) == ["gggg", "....", "kkkk", "gggg"]


@pytest.mark.parametrize("argv,want", [
    (["scene", "--size", "-3x-2", "-o", "s.png"], "--size wants WxH like 16x16, got '-3x-2'"),
    (["scene", "--size", "0x5", "-o", "s.png"], "--size wants WxH like 16x16, got '0x5'"),
    (["crop", "A", "0,0,-3,4", "-o", "c.px"], "x,y,w,h wants w and h of 1 or more, got '0,0,-3,4'"),
    (["mask", "A", "--keep-circle", "5,5,-3"], "--keep-circle '5,5,-3': r can't be negative"),
    (["mask", "A:*", "--keep", "0,0,-2,2"], "--keep '0,0,-2,2': w and h must be 1 or more"),
    (["check", "A", "--size", "-4x4"], "--size wants WxH like 16x16, got '-4x4'")])
def test_negative_sizes_are_refused_not_tracebacks(tmp_path, argv, want):
    f = write(tmp_path, "a.px", GRID)
    argv = [str(f) + x[1:] if x.startswith("A") else str(tmp_path / x) if x.endswith(("png", "c.px")) else x
            for x in argv]
    assert want in run_err(*argv)


def test_the_equals_hint_skips_a_missing_value_before_another_option(tmp_path, capsys):
    f = write(tmp_path, "a.px", GRID)
    with pytest.raises(SystemExit):
        pxart.main(["mask", str(f), "--keep-circle", "--dither", "3"])
    assert "goes after '='" not in capsys.readouterr().err


def test_the_equals_hint_for_a_list_option(tmp_path, capsys):
    f = write(tmp_path, "a.px", GRID)
    with pytest.raises(SystemExit):
        pxart.main(["palette", str(f), "--add", "-=#102030"])
    assert "expected at least one argument (a value starting with '-' goes after '=': --add=-=#102030, one value " \
           "to each)" in capsys.readouterr().err


def test_shift_keeps_a_bad_number_in_order(tmp_path, capsys):
    f = write(tmp_path, "a.px", GRID)
    with pytest.raises(SystemExit):
        pxart.main(["shift", str(f), "-.5", "1"])
    assert "--dx: invalid int value: '-.5'" in capsys.readouterr().err
