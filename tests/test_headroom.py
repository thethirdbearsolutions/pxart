"""check --headroom N and anim's vertical travel (PX-13): a standing frame that fills its canvas leaves a jump nowhere
to go, and a 3-row jump should show as a number."""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pxart  # noqa: E402

# the fox: a standing frame that fills its 8-row canvas, and a jump that can only rise 2 rows before it hits the top
FOX = """pxart 1
k #000000
o #ff8800
h transparent

@variant night
h #ffe08080

@anim jump ms=100

@frame stand/0
..kk..
.kook.
.kook.
.kook.
.kook.
.kook.
.kook.
..kk..

@frame jump/0
..kk..
.kook.
.kook.
.kook.
.kook.
.kook.
.kook.
..kk..
@frame jump/1
.kook.
.kook.
.kook.
.kook.
.kook.
..kk..
......
......
@frame jump/2
..kk..
.kook.
.kook.
.kook.
.kook.
.kook.
..kk..
......

@frame roomy
h.....
......
......
..kk..
.kook.
..kk..
......
......
"""


def run(*argv):
    try:
        pxart.main([str(a) for a in argv])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    return 0


def fox(tmp_path):
    p = tmp_path / "fox.px"
    p.write_text(FOX)
    return p


def test_check_headroom_notes_the_frames_that_fill_the_canvas(tmp_path, capsys):
    p = fox(tmp_path)
    assert run("check", f"{p}:stand", "--headroom", 2) == 0  # a note, not a failure
    out = capsys.readouterr().out
    assert f"note: {p}: 0 rows of headroom (want 2)" in out or f"note: {p}:stand/0: 0 rows of headroom (want 2)" in out


def test_each_frame_under_n_rows_gets_a_line(tmp_path, capsys):
    p = fox(tmp_path)
    run("check", p, "--headroom", 4)
    out = capsys.readouterr().out
    assert f"{p}:stand/0: 0 rows of headroom (want 4)" in out
    assert f"{p}:jump/1: 0 rows of headroom (want 4)" in out
    assert f"{p}:roomy: 0 rows of headroom" in out  # its night halo sits in row 0


def test_a_key_drawn_only_in_a_variant_counts(tmp_path, capsys):
    p = fox(tmp_path)
    run("check", f"{p}:roomy", "--headroom", 2)
    assert "0 rows of headroom (want 2)" in capsys.readouterr().out  # the night halo sits in row 0


def test_enough_headroom_is_silent(tmp_path, capsys):
    p = tmp_path / "small.px"
    p.write_text("k #000000\n......\n......\n..kk..\n")
    assert run("check", p, "--headroom", 2) == 0
    assert "rows of headroom" not in capsys.readouterr().out


def test_more_than_eight_frames_are_cut_short_unless_v(tmp_path, capsys):
    rows = "kk\n" * 2
    p = tmp_path / "many.px"
    p.write_text("k #000000\n@anim a ms=100\n" + "".join(f"@frame a/{i}\n{rows}" for i in range(10)))
    run("check", p, "--headroom", 1)
    out = capsys.readouterr().out
    assert out.count("rows of headroom (want 1)") == 8 and "and 2 more frames under 1 rows of headroom" in out
    run("check", p, "--headroom", 1, "-v")
    assert capsys.readouterr().out.count("rows of headroom (want 1)") == 10


def test_a_headroom_under_one_is_an_error(tmp_path):
    p = fox(tmp_path)
    with pytest.raises(SystemExit) as e:
        pxart.main(["check", str(p), "--headroom", "0"])
    assert "E_BAD_ARG" in str(e.value.code)


def test_anim_says_how_far_the_jump_rises_and_the_room_left(tmp_path, capsys):
    p = fox(tmp_path)
    assert run("anim", f"{p}:jump") == 0
    out = capsys.readouterr().out
    assert "  vertical travel: 2 rows (the bottom edge from row 7 up to 5); 0 rows of headroom at its highest" in out


def test_anim_says_nothing_of_travel_when_the_feet_stay(tmp_path, capsys):
    p = tmp_path / "walk.px"
    p.write_text("k #000000\n@anim w ms=100\n@frame w/0\n.k\nkk\n@frame w/1\nk.\nkk\n")
    assert run("anim", p) == 0
    assert "vertical travel" not in capsys.readouterr().out
