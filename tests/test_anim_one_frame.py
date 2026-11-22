"""anim on a single frame: a note, not the frame compared with itself (PX-41)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import pxart  # noqa: E402

MUSHROOM = "k #2b1d32\nr #c4473a\nw #f4f4f4\n\n.rrr.\nrwrwr\n.kwk.\n.kwk.\n"


def run(*argv):
    try:
        pxart.main([str(a) for a in argv])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    return 0


def test_one_frame_file_is_a_note_and_still_writes(tmp_path, capsys):
    p = tmp_path / "mushroom.px"
    p.write_text(MUSHROOM)
    assert run("anim", p, "-o", tmp_path / "m.gif") == 0
    out = capsys.readouterr().out
    assert "note: mushroom: 1 frame, nothing to compare" in out and " vs " not in out
    assert (tmp_path / "m.gif").exists() and (tmp_path / "m.strip.png").exists()


def test_one_frame_group_among_others(tmp_path, capsys):
    p = tmp_path / "g.px"
    p.write_text("k #000000\n@anim a ms=80\n@frame a/0\nk.\n@frame b/0\n.k\n@frame b/1\nk.\n")
    assert run("anim", p) == 0
    out = capsys.readouterr().out
    assert "note: a/0: 1 frame, nothing to compare" in out
    assert "b/0" in out and "vs b/1" in out  # a group of two still compares
