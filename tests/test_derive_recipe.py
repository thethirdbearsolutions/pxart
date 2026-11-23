"""palette --derive-from writes how the variant was made (PX-53): a '# derived by: pxart palette ...' line right above
'@variant NAME', which a re-derive replaces and --comment keeps, and the listing names kept-lit and lamplit keys by
role."""
import pathlib
import shlex
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pxart  # noqa: E402

PAL = """pxart 1
k #1b1420
b #6b4a2e
f #6c4a2e
y #fee761
g #5a8a3a
"""

DERIVE = ["--variant", "night", "--derive-from", "base", "--darken", "0.55", "--tint", "#18204880", "--keep-lit", "y",
          "--lamplit", "f@0.6"]


def run(*argv):
    try:
        pxart.main([str(a) for a in argv])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    return 0


def pal(tmp_path):
    p = tmp_path / "pal.px"
    p.write_text(PAL)
    return p


def recipe_lines(p):
    return [l for l in p.read_text().splitlines() if l.startswith("# derived by")]


def test_the_derive_writes_its_command_above_the_variant(tmp_path):
    p = pal(tmp_path)
    assert run("palette", p, *DERIVE) == 0
    lines = p.read_text().splitlines()
    at = lines.index("@variant night")
    assert lines[at - 1] == ("# derived by (from this file's folder): pxart palette pal.px --variant night --derive-from base --darken 0.55 "
                             "--tint '#18204880' --keep-lit y --lamplit f@0.6")


def test_running_the_line_again_gives_the_same_file(tmp_path, monkeypatch):
    p = pal(tmp_path)
    assert run("palette", p, *DERIVE, "--lift-darks", "--add", "g=#000000") == 0
    first = p.read_text()
    cmd = shlex.split(recipe_lines(p)[0].split(": pxart ", 1)[1])
    assert cmd[-3:] == ["--lift-darks", "--add", "g=#000000"]
    monkeypatch.chdir(tmp_path)
    assert run(*cmd) == 0
    assert p.read_text() == first


def test_a_rederive_replaces_the_line_and_keeps_other_comments(tmp_path):
    p = pal(tmp_path)
    assert run("palette", p, *DERIVE) == 0
    assert run("palette", p, "--comment", "@variant", "night", "the night") == 0
    assert run("palette", p, "--variant", "night", "--derive-from", "base", "--darken", "0.3") == 0
    lines = p.read_text().splitlines()
    at = lines.index("@variant night")
    assert lines[at - 2:at] == ["# the night",
                                "# derived by (from this file's folder): pxart palette pal.px --variant night "
                                "--derive-from base --darken 0.3"]
    assert len(recipe_lines(p)) == 1


def test_the_listing_names_keys_by_role(tmp_path, capsys):
    p = pal(tmp_path)
    assert run("palette", p, *DERIVE, "--lamplit", "b@0.2") == 0
    capsys.readouterr()
    assert run("palette", p) == 0
    out = capsys.readouterr().out
    assert "  night: recolors (darker) k g; kept lit: y; lamplit: f (0.6); lamplit: b (0.2); inherits: nothing" in out
    assert "    # derived by (from this file's folder): pxart palette pal.px" in out


def test_a_variant_by_hand_lists_as_before(tmp_path, capsys):
    p = pal(tmp_path)
    assert run("palette", p, "--variant", "night", "--add", "k=#000000", "y=#fee761") == 0
    capsys.readouterr()
    assert run("palette", p) == 0
    assert "night: recolors (darker) k; relists unchanged: y; inherits: b f g" in capsys.readouterr().out
    assert not recipe_lines(p)


def test_a_later_add_is_noted(tmp_path, capsys):
    p = pal(tmp_path)
    assert run("palette", p, *DERIVE) == 0
    capsys.readouterr()
    assert run("palette", p, "--variant", "night", "--add", "g=#000000") == 0
    assert "'# derived by' line doesn't make g so" in capsys.readouterr().out
    assert run("palette", p, "--variant", "night", "--comment", "g", "by hand") == 0
    assert "derived by" not in capsys.readouterr().out


def test_dry_run_shows_the_line_and_writes_nothing(tmp_path, capsys):
    p = pal(tmp_path)
    assert run("palette", p, *DERIVE, "--dry-run") == 0
    assert "+# derived by (from this file's folder): pxart palette pal.px" in capsys.readouterr().out
    assert p.read_text() == PAL
    assert run("palette", p, "--variant", "night", "--derive-from", "base") == 0  # DRY reset for later tests


def test_the_line_is_a_comment_to_every_reader(tmp_path):
    p = pal(tmp_path)
    assert run("palette", p, *DERIVE) == 0
    doc = pxart.parse(p, palette_only=True)
    assert set(doc.variants) == {"night"} and run("check", p) == 0


def test_the_listing_names_a_key_set_since_apart(tmp_path, capsys):
    p = pal(tmp_path)
    assert run("palette", p, *DERIVE) == 0
    p.write_text(p.read_text().replace("f #4f2e20", "f #ff00ff"))  # by hand, or a later --add
    capsys.readouterr()
    assert run("palette", p) == 0
    out = capsys.readouterr().out
    assert "lamplit: f" not in out and "kept lit: y" in out
    assert "not what its '# derived by' line makes now: f (running the line again changes it)" in out


def test_o_names_the_file_the_line_lives_in(tmp_path):
    p = pal(tmp_path)
    (tmp_path / "alt").mkdir()
    assert run("palette", p, *DERIVE, "-o", tmp_path / "alt" / "dark.px") == 0
    assert recipe_lines(tmp_path / "alt" / "dark.px")[0].startswith(
        "# derived by (from this file's folder): pxart palette dark.px --variant night")


def test_a_derived_sprites_marks_are_not_listed_as_comments(tmp_path, capsys):
    (tmp_path / "base.px").write_text("pxart 1\nb #6b4a2e\nf #6c4a2e\n\n@variant night\nb #23202e\nf #2b2a30\n")
    s = tmp_path / "crate.px"
    s.write_text("pxart 1\n@palette base.px\nk #000000\nkf\n")
    assert run("palette", s, "--variant", "night", "--derive-from", "base", "--darken", "0.5", "--lamplit", "f@0.5") == 0
    assert "# lamplit (palette --derive-from)" in s.read_text()
    capsys.readouterr()
    assert run("palette", s) == 0
    out = capsys.readouterr().out
    assert "lamplit: f (0.5)" in out and "f: # lamplit" not in out


def rerun(p):
    """Run p's '# derived by' line from p's folder, as the line says."""
    line = recipe_lines(p)[0]
    cmd = shlex.split(line.split(": pxart ", 1)[1])
    here = pathlib.Path.cwd()
    import os
    os.chdir(p.parent)
    try:
        return run(*cmd)
    finally:
        os.chdir(here)


def test_match_is_written_from_the_files_folder(tmp_path, monkeypatch):
    (tmp_path / "ref").mkdir()
    (tmp_path / "ref" / "moss.px").write_text("pxart 1\na #808080\nb #404040\n\n@variant night\na #202040\nb #101030\n")
    (tmp_path / "art").mkdir()
    p = tmp_path / "art" / "pal.px"
    p.write_text(PAL)
    monkeypatch.chdir(tmp_path)
    assert run("palette", "art/pal.px", "--variant", "night", "--derive-from", "base", "--match", "ref/moss.px%night") == 0
    assert "--match ../ref/moss.px%night" in recipe_lines(p)[0]
    first = p.read_text()
    assert rerun(p) == 0 and p.read_text() == first


def test_a_darken_is_written_exactly(tmp_path):
    p = pal(tmp_path)
    assert run("palette", p, "--variant", "night", "--derive-from", "base", "--darken", "0.5000004") == 0
    assert "--darken 0.5000004" in recipe_lines(p)[0]
    first = p.read_text()
    assert rerun(p) == 0 and p.read_text() == first


def test_dash_values_are_written_as_argparse_reads_them(tmp_path):
    p = tmp_path / "pal.px"
    p.write_text(PAL + "- #808080\n")
    assert run("palette", p, "--variant", "night", "--derive-from", "base", "--darken", "0.5", "--keep-lit=-,k") == 0
    assert "--keep-lit=-,k" in recipe_lines(p)[0]
    first = p.read_text()
    assert rerun(p) == 0 and p.read_text() == first


def test_a_line_that_cant_run_names_no_roles(tmp_path, capsys):
    p = pal(tmp_path)
    assert run("palette", p, *DERIVE) == 0
    p.rename(tmp_path / "other.px")  # the line names pal.px, not this file
    p = tmp_path / "other.px"
    p.write_text(p.read_text().replace("y #fee761\n", "y #ff00ff\n", 2).replace("@variant night\n", "@variant night\n"))
    capsys.readouterr()
    assert run("palette", p) == 0
    out = capsys.readouterr().out
    assert "kept lit" not in out and "lamplit:" not in out and "can't be run here" in out


def test_an_authors_comment_is_not_a_recipe(tmp_path, capsys):
    p = pal(tmp_path)
    assert run("palette", p, *DERIVE) == 0
    text = p.read_text().replace("@variant night\n", "# derived by: hand, at dusk\n@variant night\n")
    p.write_text(text)
    capsys.readouterr()
    assert run("palette", p) == 0
    assert "kept lit" not in capsys.readouterr().out  # the recipe isn't the last comment line any more
    assert run("palette", p, *DERIVE) == 0
    assert "# derived by: hand, at dusk" in p.read_text()  # kept: not the line the derive writes


def test_an_add_in_the_derive_takes_its_key_out_of_the_role(tmp_path, capsys):
    p = pal(tmp_path)
    assert run("palette", p, *DERIVE, "--add", "f=#ff00ff") == 0
    capsys.readouterr()
    assert run("palette", p) == 0
    out = capsys.readouterr().out
    assert "lamplit: f" not in out and "kept lit: y" in out


def test_lamps_of_other_colors_list_apart(tmp_path, capsys):
    p = pal(tmp_path)
    assert run("palette", p, "--variant", "night", "--derive-from", "base", "--darken", "0.5", "--lamplit", "f@0.4",
               "--lamplit", "b@0.4:#80a0ff") == 0
    capsys.readouterr()
    assert run("palette", p) == 0
    assert "lamplit: f (0.4); lamplit: b (0.4, toward #80a0ff)" in capsys.readouterr().out
