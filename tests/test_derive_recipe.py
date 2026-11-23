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
    return [l for l in p.read_text().splitlines() if l.startswith("# derived by:")]


def test_the_derive_writes_its_command_above_the_variant(tmp_path):
    p = pal(tmp_path)
    assert run("palette", p, *DERIVE) == 0
    lines = p.read_text().splitlines()
    at = lines.index("@variant night")
    assert lines[at - 1] == ("# derived by: pxart palette pal.px --variant night --derive-from base --darken 0.55 "
                             "--tint '#18204880' --keep-lit y --lamplit f@0.6")


def test_running_the_line_again_gives_the_same_file(tmp_path, monkeypatch):
    p = pal(tmp_path)
    assert run("palette", p, *DERIVE, "--lift-darks", "--add", "g=#000000") == 0
    first = p.read_text()
    cmd = shlex.split(recipe_lines(p)[0][len("# derived by: pxart "):])
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
                                "# derived by: pxart palette pal.px --variant night --derive-from base --darken 0.3"]
    assert len(recipe_lines(p)) == 1


def test_the_listing_names_keys_by_role(tmp_path, capsys):
    p = pal(tmp_path)
    assert run("palette", p, *DERIVE, "--lamplit", "b@0.2") == 0
    capsys.readouterr()
    assert run("palette", p) == 0
    out = capsys.readouterr().out
    assert "  night: recolors (darker) k g; kept lit: y; lamplit: f (0.6); lamplit: b (0.2); inherits: nothing" in out
    assert "    # derived by: pxart palette pal.px" in out


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
    assert "'# derived by:' line doesn't include this --add" in capsys.readouterr().out
    assert run("palette", p, "--variant", "night", "--comment", "g", "by hand") == 0
    assert "derived by" not in capsys.readouterr().out


def test_dry_run_shows_the_line_and_writes_nothing(tmp_path, capsys):
    p = pal(tmp_path)
    assert run("palette", p, *DERIVE, "--dry-run") == 0
    assert "+# derived by: pxart palette pal.px" in capsys.readouterr().out
    assert p.read_text() == PAL
    assert run("palette", p, "--variant", "night", "--derive-from", "base") == 0  # DRY reset for later tests


def test_the_line_is_a_comment_to_every_reader(tmp_path):
    p = pal(tmp_path)
    assert run("palette", p, *DERIVE) == 0
    doc = pxart.parse(p, palette_only=True)
    assert set(doc.variants) == {"night"} and run("check", p) == 0
