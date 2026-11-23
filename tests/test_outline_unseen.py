"""check --outline K says when K draws nothing in the base or a variant (PX-43): keys compare as keys, so an outline
that is see-through in one render passed though that render shows no outline."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pxart  # noqa: E402

GRID = "@frame a\n.kkk.\nkgggk\nkgggk\n.kkk.\n"


def run(*argv):
    try:
        pxart.main([str(a) for a in argv])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    return 0


def out_of(tmp_path, capsys, pal, *extra):
    p = tmp_path / "o.px"
    p.write_text("pxart 1\n" + pal + GRID)
    capsys.readouterr()
    run("check", p, "--outline", "k", *extra)
    return p, capsys.readouterr().out


def test_a_night_only_outline_is_named_in_the_base(tmp_path, capsys):
    p, out = out_of(tmp_path, capsys, "k transparent\ng #43e1b3\n\n@variant night\nk #120e22\n\n")
    assert f"{p}: outline 'k' draws nothing in base (transparent there), so that render shows no outline" in out


def test_a_day_only_outline_is_named_in_the_variant(tmp_path, capsys):
    p, out = out_of(tmp_path, capsys, "k #120e22\ng #43e1b3\n\n@variant night\nk #00000000\n\n")
    assert f"{p}: outline 'k' draws nothing in night (transparent there)" in out


def test_with_min_alpha_a_faint_outline_counts_as_none(tmp_path, capsys):
    p, out = out_of(tmp_path, capsys, "k #120e2240\ng #43e1b3\n\n", "--min-alpha", 128)
    assert "draws nothing in base (alpha under 128 there)" in out


def test_an_outline_solid_everywhere_is_silent(tmp_path, capsys):
    p, out = out_of(tmp_path, capsys, "k #120e22\ng #43e1b3\n\n@variant night\nk #000000\n\n")
    assert "draws nothing" not in out and "gap" not in out


def test_a_faint_but_visible_outline_without_min_alpha_is_silent(tmp_path, capsys):
    p, out = out_of(tmp_path, capsys, "k #120e2240\ng #43e1b3\n\n")
    assert "draws nothing" not in out
