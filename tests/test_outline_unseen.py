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
    assert f"{p}: outline 'k' draws nothing in night (transparent there), so that render shows no outline\n" in out


def test_with_min_alpha_a_faint_outline_counts_as_none(tmp_path, capsys):
    p, out = out_of(tmp_path, capsys, "k #120e2240\ng #43e1b3\n\n", "--min-alpha", 128)
    assert "is fainter than --min-alpha 128 in any render (alpha under 128 there), so no render shows an outline" in out


def test_an_outline_solid_everywhere_is_silent(tmp_path, capsys):
    p, out = out_of(tmp_path, capsys, "k #120e22\ng #43e1b3\n\n@variant night\nk #000000\n\n")
    assert "draws nothing" not in out and "gap" not in out


def test_a_faint_but_visible_outline_without_min_alpha_is_silent(tmp_path, capsys):
    p, out = out_of(tmp_path, capsys, "k #120e2240\ng #43e1b3\n\n")
    assert "draws nothing" not in out


def test_a_key_drawn_nowhere_is_said_once_without_gaps(tmp_path, capsys):
    p, out = out_of(tmp_path, capsys, "k transparent\ng #43e1b3\n\n")
    assert "outline 'k' draws nothing in any render (transparent there), so no render shows an outline" in out
    assert "has" not in out and "outline gaps not checked: 'k' draws in no render" in out


def test_one_key_of_several_says_what_the_render_loses(tmp_path, capsys):
    p = tmp_path / "kl.px"
    p.write_text("pxart 1\nk #120e22\nL #ffffff\ng #43e1b3\n\n@variant night\nL #ffffff00\n\n"
                 "@frame a\n.LLL.\nkgggk\nkgggk\n.kkk.\n")
    capsys.readouterr()
    run("check", p, "--outline", "kL")
    out = capsys.readouterr().out
    assert "outline 'L' draws nothing in night (transparent there), so that render loses the outline's 'L' pixels" \
        in out


def test_an_imported_key_names_its_file_and_a_slot_that_draws(tmp_path, capsys):
    (tmp_path / "pal.px").write_text("pxart 1\nk transparent | #ff0000\ng #43e1b3\n")
    p = tmp_path / "s.px"
    p.write_text("pxart 1\n@palette pal.px\n" + GRID)
    capsys.readouterr()
    run("check", p, "--outline", "k")
    out = capsys.readouterr().out
    assert "outline 'k' (from pal.px) draws nothing in any render" in out and "a slot color of it draws in base" in out


def test_a_variants_own_slot_list_is_read(tmp_path, capsys):
    p, out = out_of(tmp_path, capsys, "k #120e22 | #ff0000\ng #43e1b3 | #00ff00\n\n@variant night\nk transparent | transparent\n\n")
    assert "draws nothing in night" in out and "slot color" not in out


def test_a_local_variant_over_an_imported_key_names_no_file(tmp_path, capsys):
    (tmp_path / "pal.px").write_text("pxart 1\nk #120e22\ng #43e1b3\n")
    p = tmp_path / "s.px"
    p.write_text("pxart 1\n@palette pal.px\n\n@variant night\nk transparent\n\n" + GRID)
    capsys.readouterr()
    run("check", p, "--outline", "k")
    out = capsys.readouterr().out
    assert "outline 'k' draws nothing in night" in out and "(from" not in out


def test_an_imported_variant_names_its_file(tmp_path, capsys):
    (tmp_path / "pal.px").write_text("pxart 1\nk #120e22\ng #43e1b3\n\n@variant night\nk transparent\n")
    (tmp_path / "other.px").write_text("pxart 1\nz #ffffff\n")
    p = tmp_path / "s.px"
    p.write_text("pxart 1\n@palette other.px\n@palette pal.px\n" + GRID)
    capsys.readouterr()
    run("check", p, "--outline", "k")
    assert "outline 'k' (from pal.px) draws nothing in night" in capsys.readouterr().out


def test_both_keys_gone_is_no_outline_and_two_renders_read_with_and(tmp_path, capsys):
    p = tmp_path / "kl.px"
    p.write_text("pxart 1\nk transparent\nL transparent\ng #43e1b3\n\n@variant night\nk #120e22\nL #ffffff\n\n"
                 "@variant dusk\nk #120e22\nL #ffffff\n\n@variant fog\n\n"
                 "@frame a\n.LLL.\nkgggk\nkgggk\n.kkk.\n")
    capsys.readouterr()
    run("check", p, "--outline", "kL")
    out = capsys.readouterr().out
    assert "outline 'k' draws nothing in base and fog (transparent there), so those renders show no outline" in out


def test_one_key_drawn_nowhere_of_several_skips_the_gaps(tmp_path, capsys):
    p = tmp_path / "kl.px"
    p.write_text("pxart 1\nk #120e22\nL transparent\ng #43e1b3\n\n@frame a\n.LLL.\nkgggk\nkgggk\n.kkk.\n")
    capsys.readouterr()
    run("check", p, "--outline", "kL")
    out = capsys.readouterr().out
    assert "gaps at" not in out and "outline gaps not checked: 'L' draws in no render" in out
