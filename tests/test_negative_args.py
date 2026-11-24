"""Negative coordinates after a flag, or as a positional, are values, not options (PX-52)."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import pxart  # noqa: E402
from test_pxart import run, write  # noqa: E402

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
