"""check's note on an animation of mixed frame sizes says how anim lines the frames up (PX-76): by pivot when they
have pivots, bottom-centred when none has."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pxart  # noqa: E402

WALK = """pxart 1
k #222222
{anim}
@frame walk/0
..kk..
..kk..
@frame walk/1{own}
..kk....
..kk....
"""


def run(*argv):
    try:
        pxart.main([str(a) for a in argv])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    return 0


def note(tmp_path, capsys, anim="@anim walk ms=140", own=""):
    p = tmp_path / "w.px"
    p.write_text(WALK.format(anim=anim, own=own))
    assert run("check", p) == 0
    return next(l for l in capsys.readouterr().out.splitlines() if "mixes frame sizes" in l)


def test_every_frame_with_a_pivot_lines_up_by_pivot(tmp_path, capsys):
    line = note(tmp_path, capsys, "@anim walk ms=140 pivot=2,1", " pivot=4,1")
    assert "frames line up by pivot, and Tiled" in line and "bottom-centered" not in line


def test_no_pivot_keeps_bottom_centered(tmp_path, capsys):
    assert "frames draw bottom-centered, and Tiled" in note(tmp_path, capsys)


def test_some_frames_without_a_pivot_are_named(tmp_path, capsys):
    line = note(tmp_path, capsys, own=" pivot=4,1")
    assert "frames line up by pivot (walk/0 by its bottom-centre pixel, having none)" in line
