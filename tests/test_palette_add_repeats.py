"""palette --add repeats add up (PX-54, PX-25): '--add f=... --add g=...' sets both, not only the last."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pxart  # noqa: E402


def run(*argv):
    try:
        pxart.main([str(a) for a in argv])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    return 0


def test_two_adds_set_both_keys(tmp_path, capsys):
    p = tmp_path / "p.px"
    p.write_text("pxart 1\nk #000000\n")
    assert run("palette", p, "--add", "f=#a07040", "--add", "g=#a07041") == 0
    doc = pxart.parse(p, palette_only=True)
    assert doc.palette["f"] == pxart.hex2rgba("#a07040") and doc.palette["g"] == pxart.hex2rgba("#a07041")
    assert "added f #a07040, g #a07041" in capsys.readouterr().out


def test_repeats_add_up_with_several_values_each_and_in_a_variant(tmp_path):
    p = tmp_path / "p.px"
    p.write_text("pxart 1\nk #000000\nf #a07040\ng #a07041\nh #ffffff\n")
    assert run("palette", p, "--variant", "night", "--add", "f=#100000", "g=#200000", "--add", "h=#300000") == 0
    night = pxart.parse(p, palette_only=True).variants["night"]
    assert set(night) == {"f", "g", "h"}


def test_a_derive_line_with_several_add_eq_values_replays(tmp_path):
    # PX-53 writes '--add=V' per value when one starts with '-'; those now add up
    p = tmp_path / "p.px"
    p.write_text("pxart 1\nk #000000\n- #808080\nf #a07040\n")
    assert run("palette", p, "--variant", "night", "--derive-from", "base", "--darken", "0.5",
               "--add=-=#101010", "--add=f=#202020") == 0
    night = pxart.parse(p, palette_only=True).variants["night"]
    assert night["-"] == pxart.hex2rgba("#101010") and night["f"] == pxart.hex2rgba("#202020")
    first = p.read_text()
    line = next(l for l in first.splitlines() if l.startswith("# derived by"))
    import os
    import shlex
    here = os.getcwd()
    os.chdir(tmp_path)
    try:
        assert run(*shlex.split(line.split(": pxart ", 1)[1])) == 0
    finally:
        os.chdir(here)
    assert p.read_text() == first


def test_one_key_twice_in_two_colors_is_refused_and_in_one_said_once(tmp_path, capsys):
    p = tmp_path / "p.px"
    p.write_text("pxart 1\nk #000000\n")
    try:
        pxart.main(["palette", str(p), "--add", "p=#9a5ad0", "--add", "p=#6a3a9a"])
        raise AssertionError("no error")
    except SystemExit as e:
        assert "--add gives 'p' two colors, p=#9a5ad0 and p=#6a3a9a: give it one" in str(e.code)
    assert "p " not in p.read_text()
    assert run("palette", p, "--variant", "night", "--add", "k=#000010", "--add", "k=#000010") == 0
    assert "sets k #000010;" in capsys.readouterr().out


def test_a_hand_add_on_a_derived_variant_names_its_keys(tmp_path, capsys):
    p = tmp_path / "p.px"
    p.write_text("pxart 1\nk #000000\nw #ffffff\nb #3050a0\n")
    assert run("palette", p, "--variant", "night", "--derive-from", "base", "--darken", "0.5", "--add", "w=#c8d0e8") == 0
    capsys.readouterr()
    assert run("palette", p, "--variant", "night", "--add", "w=#c8d0e8", "--add", "b=#5070c0") == 0
    out = capsys.readouterr().out
    assert "'# derived by' line doesn't make b so;" in out and "make w b" not in out
    assert run("palette", p, "--variant", "night", "--add", "w=#c8d0e8") == 0
    assert "derived by" not in capsys.readouterr().out  # nothing new: no note


def test_an_edited_copy_names_itself_in_its_line(tmp_path):
    p = tmp_path / "p.px"
    p.write_text("pxart 1\nk #000000\nw #ffffff\n")
    assert run("palette", p, "--variant", "night", "--derive-from", "base", "--darken", "0.5") == 0
    assert run("palette", p, "--variant", "night", "--add", "w=#c0c0ff", "-o", tmp_path / "copy.px") == 0
    line = next(l for l in (tmp_path / "copy.px").read_text().splitlines() if l.startswith("# derived by"))
    assert ": pxart palette copy.px --variant night" in line
    assert ": pxart palette p.px --variant night" in p.read_text()
