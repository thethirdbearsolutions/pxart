"""The WARNING for a variant a sprite gets only from its @palette prints a fix that runs (PX-74): --match names the
import that has the variant when there are several, and when that variant recolors too few keys to fit a derive to,
the note gives the by-hand palette --add instead."""
import pathlib
import shlex
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pxart  # noqa: E402


def run(*argv):
    pxart.WARNED.clear()
    try:
        pxart.main([str(a) for a in argv])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    return 0


def quoted(out, start):
    """The command the note prints, from `start` to its closing quote."""
    i = out.index(start)
    return shlex.split(out[i:out.index("'", i)])


def test_one_recolored_key_gives_the_by_hand_route(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    pathlib.Path("pal.px").write_text("k #3f2631\n@variant night\nk #1a1020\n")
    pathlib.Path("a.px").write_text("pxart 1\n@palette pal.px\nW #c0b090\nkW\n")
    assert run("check", "a.px") == 0
    out = capsys.readouterr().out
    assert "--derive-from" not in out
    assert "pxart palette a.px --variant night --add 'W=#rrggbb'" in out
    assert "pal.px's night recolors too few keys" in out
    assert run("palette", "a.px", "--variant", "night", "--add", "W=#504030") == 0  # the route, with a color
    capsys.readouterr()
    assert run("check", "a.px") == 0
    assert "night" not in capsys.readouterr().out


def test_a_light_goes_by_hand_in_its_base_color(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    pathlib.Path("pal.px").write_text("k #3f2631\n@variant night\nk #1a1020\n")
    pathlib.Path("a.px").write_text("pxart 1\n@palette pal.px\nW #c0b090\nM #ffe080\n@variant dusk\nW #806050\n"
                                    "kWM\n")
    assert run("check", "a.px") == 0
    out = capsys.readouterr().out
    assert "--add 'W=#rrggbb' --add 'M=#ffe080'" in out and "kept lit at base, M " in out


def test_several_imports_match_the_one_with_the_variant(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    pathlib.Path("pal3.px").write_text("q #00aaff\n")
    pathlib.Path("pal2.px").write_text("g #446644\nr #aa3322\n@variant night\ng #223322\nr #551a11\n")
    pathlib.Path("b.px").write_text("pxart 1\n@palette pal3.px\n@palette pal2.px\nW #c0b090\nY #ffee88\n"
                                    "@variant dusk\nW #806040\nWgrqY\n")
    assert run("check", "b.px") == 0
    out = capsys.readouterr().out
    assert "P.px" not in out and "which give no night" in out
    cmd = quoted(out, "pxart palette b.px")
    assert cmd[cmd.index("--match") + 1] == "pal2.px"
    assert run(*cmd[1:]) == 0  # runs as printed
    capsys.readouterr()
    assert run("check", "b.px") == 0
    assert "comes only from" not in capsys.readouterr().out


def test_render_warning_says_the_same(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    pathlib.Path("pal.px").write_text("k #3f2631\n@variant night\nk #1a1020\n")
    pathlib.Path("a.px").write_text("pxart 1\n@palette pal.px\nW #c0b090\nkW\n")
    assert run("render", "a.px", "--variant", "night", "-o", "a.png") == 0
    out = capsys.readouterr().out
    assert "WARNING: a.px:" in out and "--add 'W=#rrggbb'" in out and "--derive-from" not in out


def test_a_sub_folder_sprite_matches_from_the_current_folder(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    pathlib.Path("art").mkdir()
    pathlib.Path("art/pal3.px").write_text("q #00aaff\n")
    pathlib.Path("art/pal2.px").write_text("g #446644\nr #aa3322\n@variant night\ng #223322\nr #551a11\n")
    pathlib.Path("art/b.px").write_text("pxart 1\n@palette pal3.px\n@palette pal2.px\nW #c0b090\nWgrq\n")
    assert run("check", "art/b.px") == 0
    cmd = quoted(capsys.readouterr().out, "pxart palette art/b.px")
    assert cmd[cmd.index("--match") + 1] == "art/pal2.px"
    assert run(*cmd[1:]) == 0


def test_of_several_imports_the_one_a_derive_fits_to_is_matched(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    pathlib.Path("town.px").write_text("k #3f2631\n@variant night\nk #1a1020\n")
    pathlib.Path("wood.px").write_text("g #446644\nr #aa3322\n@variant night\ng #223322\nr #551a11\n")
    pathlib.Path("v.px").write_text("pxart 1\n@palette town.px\n@palette wood.px\nW #c0b090\nkWgr\n")
    assert run("check", "v.px") == 0
    cmd = quoted(capsys.readouterr().out, "pxart palette v.px")
    assert cmd[cmd.index("--match") + 1] == "wood.px"
    assert run(*cmd[1:]) == 0


def test_the_partly_lit_note_names_the_import_from_here(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    pathlib.Path("props").mkdir()
    pathlib.Path("town.px").write_text("k #3f2631\n@variant night\nk #1a1020\n")
    pathlib.Path("props/sign.px").write_text("pxart 1\n@palette ../town.px\np #aa3333\nd #886644\n"
                                             "@variant night\np #551111\nkpd\n")
    assert run("check", "props/sign.px") == 0
    out = capsys.readouterr().out
    assert "town.px's night recolors too few" in out and "props/../" not in out
