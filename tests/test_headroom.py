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
    assert f"note: {p}:stand: 0 rows of headroom (want 2) in stand/0" in out


def test_a_group_a_line_and_only_its_grounded_frames(tmp_path, capsys):
    p = fox(tmp_path)
    run("check", p, "--headroom", 4)
    out = capsys.readouterr().out
    assert f"{p}:stand: 0 rows of headroom (want 4) in stand/0; to grow the canvas 4 rows up: pxart crop " \
        f"{p}:stand/0 0,-4,6,12 -o {p}:stand/0" in out
    # jump/1 and jump/2 are airborne (their bottom edge is above jump/0's): a jump is meant to rise, so not noted
    assert f"{p}:jump: 0 rows of headroom (want 4) in jump/0; to grow the canvas 4 rows up: pxart crop {p}:jump/0 " \
        f"0,-4,6,12 -o {p}:jump/0; and each other jump frame 4 rows up the same way" in out
    assert "jump/1" not in out.split("unused")[0].split("headroom", 1)[1]


def test_the_crop_it_prints_gives_the_room(tmp_path, capsys):
    p = fox(tmp_path)
    assert run("crop", f"{p}:stand/0", "0,-4,6,12", "-o", f"{p}:stand/0") == 0
    capsys.readouterr()
    run("check", f"{p}:stand/0", "--headroom", 4)
    assert "rows of headroom" not in capsys.readouterr().out


def test_a_headroom_past_the_frame_says_so(tmp_path, capsys):
    p = fox(tmp_path)
    run("check", f"{p}:stand/0", "--headroom", 9)
    assert "the frame is only 8 rows tall" in capsys.readouterr().out


def test_a_key_drawn_only_in_a_variant_counts(tmp_path, capsys):
    p = fox(tmp_path)
    run("check", f"{p}:roomy", "--headroom", 2)
    assert "0 rows of headroom (want 2)" in capsys.readouterr().out  # the night halo sits in row 0


def test_enough_headroom_is_silent(tmp_path, capsys):
    p = tmp_path / "small.px"
    p.write_text("k #000000\n......\n......\n..kk..\n")
    assert run("check", p, "--headroom", 2) == 0
    assert "rows of headroom" not in capsys.readouterr().out


def test_one_line_for_a_group_of_many_frames(tmp_path, capsys):
    rows = "kk\n" * 2
    p = tmp_path / "many.px"
    p.write_text("k #000000\n@anim a ms=100\n" + "".join(f"@frame a/{i}\n{rows}" for i in range(10)))
    run("check", p, "--headroom", 1)
    out = capsys.readouterr().out
    assert out.count("rows of headroom (want 1)") == 1 and "in a/0, a/1, a/2, a/3 and 6 more" in out


def test_a_headroom_under_one_is_an_error(tmp_path):
    p = fox(tmp_path)
    with pytest.raises(SystemExit) as e:
        pxart.main(["check", str(p), "--headroom", "0"])
    assert "E_BAD_ARG" in str(e.value.code)


def test_anim_says_how_far_the_jump_rises_and_the_room_left(tmp_path, capsys):
    p = fox(tmp_path)
    assert run("anim", f"{p}:jump") == 0
    out = capsys.readouterr().out
    # jump/0 and jump/1 both reach row 0; jump/1 is the airborne one
    assert "  vertical travel: 2 rows (the bottom edge from row 7 up to 5); 0 rows of headroom at its highest (jump/1)" \
        in out


def test_a_faint_ground_shadow_does_not_pin_the_bottom_edge(tmp_path, capsys):
    p = tmp_path / "j.px"
    p.write_text("k #000000\ns #00000055\n@anim j ms=100\n@frame j/0\n..\nkk\nkk\nss\n@frame j/1\nkk\nkk\n..\nss\n")
    assert run("anim", p) == 0
    assert "vertical travel: 1 row (the bottom edge from row 2 up to 1)" in capsys.readouterr().out


def test_anim_says_nothing_of_travel_when_the_feet_stay(tmp_path, capsys):
    p = tmp_path / "walk.px"
    p.write_text("k #000000\n@anim w ms=100\n@frame w/0\n.k\nkk\n@frame w/1\nk.\nkk\n")
    assert run("anim", p) == 0
    assert "vertical travel" not in capsys.readouterr().out


def check_out(capsys, *argv):
    capsys.readouterr()
    run("check", *argv)
    return capsys.readouterr().out


def test_frames_of_other_sizes_stand_on_one_ground(tmp_path, capsys):
    # anim bottom-aligns a shorter frame: it stands on the same ground, and filling its canvas is a fault too
    p = tmp_path / "s.px"
    p.write_text("k #000000\n@anim a ms=100\n@frame a/0\n....\n.kk.\n.kk.\n@frame a/1\n.kk.\n.kk.\n")
    assert "in a/0, a/1;" in check_out(capsys, p, "--headroom", 2)


def test_a_pivot_says_where_the_ground_is(tmp_path, capsys):
    # same-size frames lined up by pivot: a/1's pivot is 2 rows lower, so it is airborne (the jump), not grounded
    p = tmp_path / "p.px"
    p.write_text("k #000000\n@anim a ms=100\n@frame a/0 pivot=1,3\n....\n....\n.kk.\n.kk.\n"
                 "@frame a/1 pivot=1,5\n.kk.\n.kk.\n....\n....\n")
    out = check_out(capsys, p, "--headroom", 3)
    assert "in a/0;" in out and "a/1" not in out.split("headroom")[1]
    assert "then pxart anim-set" in out and "pivot=1,4 (the feet stay put)" in out


def test_a_faint_shadow_doesnt_ground_an_airborne_frame(tmp_path, capsys):
    p = tmp_path / "f.px"
    p.write_text("k #000000\ns #00000055\n@anim a ms=100\n@frame a/0\n..\n..\nkk\nss\n"
                 "@frame a/1\nkk\n..\n..\nss\n")
    out = check_out(capsys, p, "--headroom", 1)
    assert "rows of headroom" not in out  # a/0 has 2 rows; a/1 is airborne over its shadow


def test_an_unnamed_grid_gets_a_crop_that_runs(tmp_path, capsys):
    p = tmp_path / "grid.px"
    p.write_text("k #000000\nkk\nkk\n")
    out = check_out(capsys, p, "--headroom", 2)
    assert f"pxart crop {p} 0,-2,2,4 -o {p}" in out and "None" not in out
    assert run("crop", p, "0,-2,2,4", "-o", p) == 0
    assert "rows of headroom" not in check_out(capsys, p, "--headroom", 2)


def test_the_verdict_doesnt_hang_on_the_selection(tmp_path, capsys):
    p = fox(tmp_path)
    assert "rows of headroom" not in check_out(capsys, f"{p}:jump/1", "--headroom", 4)  # airborne in its group


def test_a_top_level_frame_named_like_a_group_is_its_own(tmp_path, capsys):
    p = tmp_path / "t.px"
    p.write_text("k #000000\n@anim a ms=100\n@frame a/0\n..\nkk\n@frame a/1\nkk\n..\n@frame a\nkk\nkk\n")
    out = check_out(capsys, p, "--headroom", 1)
    assert f"{p}:a: 0 rows of headroom (want 1);" in out
