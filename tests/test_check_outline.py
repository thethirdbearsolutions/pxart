"""check --outline K: gaps in a sprite's outline (PX-11). Edge pixels of the shape not drawn in an outline key are
notes, with coordinates; a frame that 'outline --key K' just drew always passes."""
import pathlib
import shutil
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pxart  # noqa: E402

# A 16x16 sprite in PICO-8 colours, drawn the way the palette post's was: outlined by hand, with three holes in the
# outline (the cap's right side at (11,4), the left shoulder at (3,9), and the right foot at (10,14)). The post's file
# isn't in this repo; this stands in for it.
PICO = """pxart 1
k #000000
r #ff004d
o #ffa300
w #fff1e8
s #ffccaa
b #29adff

@frame idle/0
................
................
.....kkkkkk.....
....krrrrrrk....
...krrrrrrrr....
...kkkkkkkkkk...
....ksswsswk....
....kssssssk....
.....kssssk.....
...bkkkkkkkkk...
...kbbbbbbbbk...
...kbbbbbbbbk...
....kbbkkbbk....
....kok..kok....
....kok..ko.....
....kkk..kkk....
"""


def run(*argv):
    try:
        pxart.main([str(a) for a in argv])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    return 0


def check(*argv, capsys):
    code = run("check", *argv)
    return code, capsys.readouterr().out


def test_the_pico_sprite_shows_its_three_gaps(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "hero.px").write_text(PICO)
    code, out = check("hero.px", "--outline", "k", capsys=capsys)
    assert code == 0  # a note, as the ticket asks
    assert "     note: hero.px:idle/0: outline 'k' has 3 gaps at (11,4) (3,9) (10,14)" in out.splitlines()
    assert out.splitlines()[-1].startswith("     note:")
    code, out = check("hero.px", capsys=capsys)  # opt-in: nothing without --outline
    assert "gap" not in out


def test_two_files_count_the_notes_as_warnings(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "hero.px").write_text(PICO)
    (tmp_path / "plain.px").write_text("g #00ff00\ngg\n")
    _, out = check("hero.px", "plain.px", "--outline", "k", capsys=capsys)
    assert out.splitlines()[-1] == "2 files, 2 frames, 1 warning"


BARE = """pxart 1
k #1a1c2c
l #5d275d
g #38b764
d #1e6b40

@frame blob/0
............
....gggg....
...gggggg...
..gggddggg..
..ggg..ggg..
..gggddggg..
...gggggg...
....gg.gg...
............
@frame blob/1
............
............
...gggggg...
..gggddgggg.
..gggddggg..
...gggggg...
....g...g...
....g...g...
............
"""


@pytest.mark.parametrize("mode", [
    ["--outside"], ["--inside"], ["--outside", "--corners"], ["--inside", "--corners"],
    ["--lit", "l", "--light", "nw"], ["--lit", "l", "--selective", "--inside"], ["--min-alpha", "1"],
])
def test_a_frame_outline_just_drew_passes(tmp_path, monkeypatch, capsys, mode):
    # every outline mode, on a shape with a hole and a split foot: no gaps after
    monkeypatch.chdir(tmp_path)
    (tmp_path / "b.px").write_text(BARE)
    assert run("outline", "b.px:*", "--key", "k", *mode) == 0
    keys = "kl" if "--lit" in mode else "k"
    _, out = check("b.px", "--outline", keys, capsys=capsys)
    assert "gap" not in out, out


def test_pad_grows_the_frame_and_still_passes(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "e.px").write_text("pxart 1\nk #000000\ng #00ff00\n\n@frame a\ngg..\ngg..\n")
    assert run("outline", "e.px", "--key", "k", "--pad") == 0
    _, out = check("e.px", "--outline", "k", capsys=capsys)
    assert "gap" not in out


def test_the_frame_border_is_no_gap(tmp_path, monkeypatch, capsys):
    # a shape cut by the frame's edge: outline --outside can't draw there, so check doesn't ask for it
    monkeypatch.chdir(tmp_path)
    (tmp_path / "c.px").write_text("pxart 1\nk #000000\ng #00ff00\n\n@frame a\ngggk.\ngggk.\nkkkk.\n.....\n")
    _, out = check("c.px", "--outline", "k", capsys=capsys)
    assert "gap" not in out


def test_a_hole_inside_the_shape_has_an_edge_too(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "h.px").write_text("pxart 1\nk #000000\ng #00ff00\n\n@frame a\n.....\n.kkk.\n.kgk.\n.k.k.\n.kkk.\n.....\n")
    _, out = check("h.px", "--outline", "k", capsys=capsys)
    assert "outline 'k' has 1 gap at (2,2)" in out


def test_silent_without_the_key(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "n.px").write_text("pxart 1\ng #00ff00\n\n@frame a\n.gg.\n.gg.\n")  # no k at all
    (tmp_path / "u.px").write_text("pxart 1\nk #000000\ng #00ff00\n\n@frame a\n.gg.\n.gg.\n")  # k, never drawn
    _, out = check("n.px", "u.px", "--outline", "k", capsys=capsys)
    assert "gap" not in out


def test_several_keys_and_their_spelling(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "s.px").write_text("pxart 1\nk #000000\nl #333333\ng #00ff00\n\n@frame a\n....\n.kl.\n.gk.\n.kk.\n....\n")
    for arg in ("kl", "k,l"):
        _, out = check("s.px", "--outline", arg, capsys=capsys)
        assert "outline 'k' or 'l' has 1 gap at (1,2)" in out
    _, out = check("s.px", "--outline", "lk", capsys=capsys)  # named in the order typed
    assert "outline 'l' or 'k' has 1 gap at (1,2)" in out
    _, out = check("s.px", "--outline", "k", capsys=capsys)
    assert "outline 'k' has 2 gaps at (2,1) (1,2)" in out
    assert pxart.outline_keys(",") == [","]


def test_many_gaps_are_counted_not_all_listed(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    rows = ["." * 12] + ["." + "kg" * 5 + "."] * 4 + ["." * 12]
    (tmp_path / "m.px").write_text("pxart 1\nk #000000\ng #00ff00\n\n@frame a\n" + "\n".join(rows) + "\n")
    _, out = check("m.px", "--outline", "k", capsys=capsys)
    line = next(l for l in out.splitlines() if "gaps" in l)
    assert line.endswith("more (-v lists them all)") and line.count("(") == 9
    _, out = check("m.px", "--outline", "k", "-v", capsys=capsys)
    line = next(l for l in out.splitlines() if "gaps" in l)
    n = int(line.split(" has ")[1].split()[0])
    assert "more" not in line and line.count("(") == n > 8


def test_a_selection_and_a_single_grid(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "hero.px").write_text(PICO + "@frame idle/1\n" + "\n".join(["." * 16] * 16) + "\n")
    _, out = check("hero.px:idle/1", "--outline", "k", capsys=capsys)
    assert "gap" not in out
    (tmp_path / "one.px").write_text("k #000000\ng #00ff00\n...\n.g.\n.k.\n...\n")
    _, out = check("one.px", "--outline", "k", capsys=capsys)
    assert "     note: one.px: outline 'k' has 1 gap at (1,1)" in out.splitlines()


def test_the_drawing_tutorials_outlined_chest_passes(capsys):
    # 04-drawing's step 11 is 'outline chest.px --key k --lit B': its chest has no gaps in k and B, and plenty in k alone
    chest = ROOT / "examples" / "04-drawing" / "steps" / "11-outline.px"
    code, out = check(chest, "--outline", "kB", capsys=capsys)
    assert code == 0 and "gap" not in out
    _, out = check(chest, "--outline", "k", capsys=capsys)
    assert "outline 'k' has" in out


def test_help_and_readme_say_it():
    doc = " ".join(pxart.__doc__.split())
    assert "[--outline K]" in doc and "A frame just outlined by outline --key K passes" in doc
    assert "--outline K" in " ".join((ROOT / "README.md").read_text().split())


def test_a_key_no_file_has_says_so(tmp_path, monkeypatch, capsys):
    # a typo in K would otherwise look like a clean pass
    monkeypatch.chdir(tmp_path)
    (tmp_path / "hero.px").write_text(PICO)
    code, out = check("hero.px", "--outline", "x", capsys=capsys)
    assert code == 0 and out.splitlines()[-1] == "note: --outline x: no file checked has a key 'x', so no outline was checked"
    _, out = check("hero.px", "--outline", "kx", capsys=capsys)  # one of them is there: checked, no such note
    assert "no file checked" not in out and "outline 'k' or 'x' has 3 gaps" in out
