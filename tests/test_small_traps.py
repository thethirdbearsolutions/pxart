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
    assert "empty: nothing in it" in out and "--strict fails it" in out  # PR #34 review: names the way to fail it


def test_a_palette_file_is_not_empty(tmp_path, capsys):
    f = write(tmp_path, "pal.px", "k #000000\n")
    assert run("check", f) == 0
    assert "empty" not in capsys.readouterr().out


def test_dup_promotes_an_unnamed_grid(tmp_path, capsys):
    f = write(tmp_path, "walker.px", GRID)
    assert run("dup", f"{f}:walker", "idle/0") == 0
    assert f"note: walker, {f}'s unnamed grid, is '@frame walker' in {f} (the id it went by)" in capsys.readouterr().out
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
    assert "if you added k with palette --add since your last commit, add it again" in capsys.readouterr().out


def test_strict_fails_an_empty_px(tmp_path, capsys):  # PX-24 loop: 'ok' and exit 0 read as fine
    f = tmp_path / "portrait.px"
    f.write_text("")
    assert run("check", f, "--strict") == 1
    out = capsys.readouterr().out
    assert f"FAIL {f}: empty: nothing in it" in out and "--strict fails it" not in out


# PR #34 review fixes
def test_dup_refuses_a_stem_that_is_not_an_id(tmp_path):
    f = write(tmp_path, "my walker.px", GRID)
    err = run_err("dup", f"{f}:my walker", "idle/0")
    assert "E_MIXED_FRAMES" in err and "its name 'my walker' can't be a frame id" in err
    assert f.read_text() == GRID  # nothing written


def test_the_keys_own_line_counts(tmp_path, capsys):  # art lined with k itself still gets the note
    f = write(tmp_path, "m.px", DARK.replace("d", "k").replace("k #101010\n", ""))
    assert run("outline", f, "--key", "k", "--dry-run") == 0
    assert "12 of the shape's 12 edge px are already as dark as k (k)" in capsys.readouterr().out


def test_a_light_outline_key_says_nothing_of_dark(tmp_path, capsys):
    f = write(tmp_path, "m.px", DARK.replace("k #000000", "k #f0f0f0"))
    assert run("outline", f, "--key", "k", "--dry-run") == 0
    assert "as dark as" not in capsys.readouterr().out


def test_a_faint_line_is_not_a_line(tmp_path, capsys):
    f = write(tmp_path, "m.px", DARK.replace("d #101010", "d #10101040"))
    assert run("outline", f, "--key", "k", "--dry-run", "--min-alpha", "1") == 0
    assert "as dark as" not in capsys.readouterr().out


def test_dark_line_note_names_only_the_frames_with_it(tmp_path, capsys):
    lined = "\n".join(DARK.split("\n\n", 1)[1].splitlines())
    plain = lined.replace("d", "g")
    f = write(tmp_path, "m.px", "k #000000\nd #101010\ng #43e1b3\n@frame a\n" + lined + "\n@frame b\n" + plain + "\n")
    assert run("outline", f, "--key", "k", "--dry-run") == 0
    assert "12 of the shape's 12 edge px in a are already as dark as k (d)" in capsys.readouterr().out


def test_a_comment_only_px_is_not_called_empty(tmp_path, capsys):
    f = write(tmp_path, "c.px", "# just a comment\n")
    assert run("check", f) == 0
    assert "empty" not in capsys.readouterr().out


def test_dup_note_names_the_file_written_and_dry_run_says_would(tmp_path, capsys):
    f = write(tmp_path, "walker.px", GRID)
    o = tmp_path / "other.px"
    assert run("dup", f"{f}:walker", "idle", "-o", o) == 0
    assert f"is '@frame walker' in {o}" in capsys.readouterr().out and f.read_text() == GRID
    assert run("dup", f"{f}:walker", "idle", "--dry-run") == 0
    assert "would be '@frame walker'" in capsys.readouterr().out and f.read_text() == GRID


def test_inside_says_nothing_of_a_dark_rim(tmp_path, capsys):
    f = write(tmp_path, "m.px", DARK)
    assert run("outline", f, "--key", "k", "--inside", "--dry-run") == 0
    assert "as dark as" not in capsys.readouterr().out


# PX-63: the dark-line note reads each palette, base and every variant
NIGHT_DARK = "k #000000\nd #c0c0c0\ng #43e1b3\n@variant night\nd #101010\n\n" + DARK.split("\n\n", 1)[1]


def test_a_line_dark_only_at_night_is_noted_for_night(tmp_path, capsys):
    f = write(tmp_path, "m.px", NIGHT_DARK)
    assert run("outline", f, "--key", "k", "--dry-run") == 0
    out = capsys.readouterr().out
    assert "in night: 12 of the shape's 12 edge px are already as dark as k (d)" in out
    assert "in base:" not in out


def test_a_key_dark_only_in_a_variant_is_judged_there(tmp_path, capsys):
    f = write(tmp_path, "m.px", DARK.replace("k #000000\n", "k #f0f0f0\n").replace(
        "g #43e1b3\n", "g #43e1b3\n@variant night\nk #000000\n"))
    assert run("outline", f, "--key", "k", "--dry-run") == 0
    out = capsys.readouterr().out
    assert "in night: 12 of the shape's 12 edge px are already as dark as k (d)" in out
    assert "in base:" not in out


def test_variants_that_agree_with_base_keep_one_line(tmp_path, capsys):
    f = write(tmp_path, "m.px", DARK.replace("g #43e1b3\n", "g #43e1b3\n@variant night\ng #204030\n"))
    assert run("outline", f, "--key", "k", "--dry-run") == 0
    out = capsys.readouterr().out
    assert "12 of the shape's 12 edge px are already as dark as k (d)" in out
    assert "in night:" not in out and "in base:" not in out and out.count("as dark as") == 1


def test_a_line_lost_at_night_names_base_only(tmp_path, capsys):
    f = write(tmp_path, "m.px", DARK.replace("g #43e1b3\n", "g #43e1b3\n@variant day2\nd #f0f0f0\n"))
    assert run("outline", f, "--key", "k", "--dry-run") == 0
    out = capsys.readouterr().out
    assert "in base: 12 of the shape's 12 edge px are already as dark as k (d)" in out
    assert "in day2:" not in out


def test_variants_that_agree_with_each_other_share_one_note(tmp_path, capsys):
    f = write(tmp_path, "m.px", NIGHT_DARK.replace("@variant night\nd #101010\n",
                                                   "@variant dusk\nd #101010\n@variant night\nd #101010\n"))
    assert run("outline", f, "--key", "k", "--dry-run") == 0
    out = capsys.readouterr().out
    assert out.count("as dark as") == 1
    assert "in dusk, night: 12 of the shape's 12 edge px are already as dark as k (d)" in out
    assert "repaints that edge in every palette" in out
