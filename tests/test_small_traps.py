"""Four small traps from a private loop (PX-24): an empty .px passing check; dup and frames --rename refusing an
unnamed grid; no word when the art has its own dark line; and the restore-from-git advice losing a palette --add."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import pxart  # noqa: E402
from test_pxart import run, run_err, write  # noqa: E402

GRID = "k #000000\ng #43e1b3\n\n.gg.\ngggg\n.gg.\n"


def test_an_empty_px_is_a_warning(tmp_path, capsys):
    f = tmp_path / "portrait.px"
    f.write_text("")
    assert run("check", f) == 0
    out = capsys.readouterr().out
    assert "empty: no keys, no frames, nothing in it" in out


def test_a_palette_file_is_not_empty(tmp_path, capsys):
    f = write(tmp_path, "pal.px", "k #000000\n")
    assert run("check", f) == 0
    assert "empty" not in capsys.readouterr().out


def test_dup_promotes_an_unnamed_grid(tmp_path, capsys):
    f = write(tmp_path, "walker.px", GRID)
    assert run("dup", f"{f}:walker", "idle/0") == 0
    assert "unnamed grid is now '@frame walker'" in capsys.readouterr().out
    doc = pxart.parse(f)
    assert [fr.id for fr in doc.frames] == ["walker", "idle/0"] and doc.frames[0].grid == doc.frames[1].grid


def test_rename_promotes_an_unnamed_grid(tmp_path):
    f = write(tmp_path, "walker.px", GRID)
    assert run("frames", f, "--rename", "walker", "hero/w") == 0
    assert [fr.id for fr in pxart.parse(f).frames] == ["hero/w"]


def test_rename_of_another_name_says_what_the_grid_goes_by(tmp_path):
    f = write(tmp_path, "walker.px", GRID)
    err = run_err("frames", f, "--rename", "x", "y")
    assert f"one unnamed grid, which goes by 'walker'; rename that: pxart frames {f} --rename walker y" in err


DARK = "k #000000\nd #101010\ng #43e1b3\n\n......\n.dddd.\n.dggd.\n.dggd.\n.dddd.\n......\n"


def test_outline_notes_the_arts_own_dark_line(tmp_path, capsys):
    f = write(tmp_path, "m.px", DARK)
    assert run("outline", f, "--key", "k", "--dry-run") == 0
    assert "12 of the shape's 12 edge px are already as dark as k (d)" in capsys.readouterr().out


def test_no_dark_line_note_on_light_art(tmp_path, capsys):
    f = write(tmp_path, "m.px", DARK.replace("d #101010", "d #c0c0c0"))
    assert run("outline", f, "--key", "k", "--dry-run") == 0
    assert "as dark as" not in capsys.readouterr().out


def test_the_restore_note_says_to_add_the_key_again(tmp_path, capsys):
    f = write(tmp_path, "e.px", "k #000000\ng #43e1b3\n\ngg\ngg\n")
    assert run("outline", f, "--key", "k") == 0
    assert "a palette --add of k since then goes with it, so add it again" in capsys.readouterr().out


def test_strict_fails_an_empty_px(tmp_path, capsys):  # PX-24 loop: 'ok' and exit 0 read as fine
    f = tmp_path / "portrait.px"
    f.write_text("")
    assert run("check", f, "--strict") == 1
    assert "--strict fails it" in capsys.readouterr().out
