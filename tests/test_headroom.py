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
    # jump's three frames share one size: one crop grows them all (PX-69)
    assert f"{p}:jump: 0 rows of headroom (want 4) in jump/0; to grow the canvas 4 rows up: pxart crop {p}:jump " \
        f"0,-4,6,12 -o {p}:jump (every frame)" in out
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
    assert f"pxart crop {p}:a 0,-1,4,5 -o {p}:a (every frame, pivots moving with the art)" in out
    assert "anim-set" not in out


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


# PX-69: crop FILE:GROUP grows a whole group's canvas in one command, its pivots moving with the art

WALK = """pxart 1
k #000000
o #ff8800

@anim walk ms=100 pivot=2,3

@frame walk/0
.kk.
.oo.
.oo.
.kk.
@frame walk/1
.kk.
.oo.
.oo.
k..k
@frame walk/2
.kk.
.oo.
.oo.
.kk.
@frame walk/3
.kk.
.oo.
.oo.
k..k
"""


def walk(tmp_path):
    p = tmp_path / "walk.px"
    p.write_text(WALK)
    return p


def test_the_group_crop_check_prints_fixes_the_whole_walk(tmp_path, capsys):
    p = walk(tmp_path)
    out = check_out(capsys, p, "--headroom", 3)
    fix = f"pxart crop {p}:walk 0,-3,4,7 -o {p}:walk"
    assert fix in out and "anim-set" not in out and "each other" not in out
    capsys.readouterr()
    assert run(*fix.split()[1:]) == 0
    assert "cropped 4 frames to 4x7" in capsys.readouterr().out
    after = check_out(capsys, p, "--headroom", 3)
    assert "rows of headroom" not in after and "size" not in after
    doc = pxart.parse(p)
    assert doc.anims["walk"]["pivot"] == (2, 6)  # one @anim line moved, no per-frame copies
    assert all(f.pivot is None and f.size == (4, 7) for f in doc.frames)
    assert doc.frames[1].grid[-1] == "k..k" and doc.frames[1].grid[:3] == ["....", "....", "...."]


def test_anim_places_the_feet_where_they_were(tmp_path, capsys):
    p = walk(tmp_path)
    run("anim", f"{p}:walk")
    before = capsys.readouterr().out
    run("crop", f"{p}:walk", "0,-3,4,7", "-o", f"{p}:walk")
    capsys.readouterr()
    run("anim", f"{p}:walk")
    assert capsys.readouterr().out.replace("4x7", "4x4") == before.replace("4x7", "4x4")


def test_a_group_crop_keeps_frame_pivots_with_the_art(tmp_path):
    p = tmp_path / "p.px"
    p.write_text("k #000000\n@anim a ms=100\n@frame a/0 pivot=1,1\nkk\nkk\n@frame a/1\nkk\nkk\n")
    assert run("crop", f"{p}:a", "-1,-2,4,4", "-o", p) == 0  # a plain -o FILE is in place too
    doc = pxart.parse(p)
    assert doc.frames[0].pivot == (2, 3) and doc.frames[1].pivot is None
    assert doc.frames[0].grid == ["....", "....", ".kk.", ".kk."]


def test_a_group_crop_into_another_file_says_to_pick_a_frame(tmp_path):
    p = walk(tmp_path)
    with pytest.raises(SystemExit) as e:
        pxart.main(["crop", f"{p}:walk", "0,0,2,2", "-o", str(tmp_path / "parts.px:head")])
    msg = str(e.value.code)
    assert "E_SELECT" in msg and "only in place" in msg and f"{p}:walk/0" in msg


def test_a_group_crop_refuses_rekey(tmp_path):
    p = walk(tmp_path)
    with pytest.raises(SystemExit) as e:
        pxart.main(["crop", f"{p}:walk", "0,0,2,2", "-o", f"{p}:walk", "--rekey"])
    assert "E_BAD_ARG" in str(e.value.code) and "--rekey" in str(e.value.code)


def test_a_group_crop_dry_run_writes_nothing(tmp_path, capsys):
    p = walk(tmp_path)
    run("crop", f"{p}:walk", "0,-1,4,5", "-o", f"{p}:walk", "--dry-run")
    assert "would write" in capsys.readouterr().out and p.read_text() == WALK


def test_mixed_sizes_still_get_a_crop_a_frame(tmp_path, capsys):
    p = tmp_path / "s.px"
    p.write_text("k #000000\n@anim a ms=100\n@frame a/0\n....\n.kk.\n.kk.\n@frame a/1\n.kk.\n.kk.\n")
    out = check_out(capsys, p, "--headroom", 2)
    assert f"crop {p}:a/" in out and "each other a frame" in out
