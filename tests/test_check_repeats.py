"""check: neighbour frames of an animation that draw the same (PX-10). A repeated frame reads as a stutter; a hold is one
frame with a longer ms=."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import pxart  # noqa: E402

# A four-frame slime idle in the shape of the cave run's (that file isn't in the repo): it rises, holds by drawing the
# raised frame twice, and comes down, so idle/1 and idle/2 repeat, and so do idle/3 and idle/0 when it loops back.
SLIME = """pxart 1
g #43e1b3
k #1a3a2a
@variant night
g #1f6a5a
@anim idle ms=150

@frame idle/0
..kkkk..
.kggggk.
kggggggk
kkkkkkkk
@frame idle/1
........
.kkkkkk.
kggggggk
kkkkkkkk
@frame idle/2
........
.kkkkkk.
kggggggk
kkkkkkkk
@frame idle/3
..kkkk..
.kggggk.
kggggggk
kkkkkkkk
"""

UP = ["..kkkk..", ".kggggk.", "kggggggk", "kkkkkkkk"]
DOWN = ["........", ".kkkkkk.", "kggggggk", "kkkkkkkk"]
SIDE = ["........", "..kkkk..", ".kggggk.", "kkkkkkkk"]


def run(*argv):
    try:
        pxart.main([str(a) for a in argv])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    return 0


def sprite(tmp_path, frames, anim="@anim walk ms=100", head="g #43e1b3\nk #1a3a2a", name="s.px"):
    body = "\n".join(f"@frame {fid}\n" + "\n".join(rows) for fid, rows in frames)
    p = tmp_path / name
    p.write_text(f"pxart 1\n{head}\n{anim}\n\n{body}\n")
    return p


def check(p, *extra, capsys):
    code = run("check", p, *extra)
    return code, capsys.readouterr().out


def test_slime_notes_the_repeat_and_the_loop_back(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "slime.px").write_text(SLIME)
    code, out = check("slime.px", capsys=capsys)
    assert code == 0
    assert ("slime.px: idle/1 and idle/2 are identical (0 px differ, in every variant too): a repeated frame, a "
            "stutter in an engine that draws every frame; for a hold, remove idle/2 and give idle/1 ms=300 (pxart frames slime.px --rm idle/2; pxart "
            "anim-set slime.px:idle/1 ms=300) (check --strict fails on it)") in out
    assert "idle/0 and idle/3 (where the loop comes back round) are identical" in out
    assert "remove idle/3 and give idle/0 ms=300" in out
    assert "6 files" not in out and out.count("are identical") == 2


def test_strict_fails_at_the_frame_to_remove(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "slime.px").write_text(SLIME)
    code, out = check("slime.px", "--strict", capsys=capsys)
    assert code == 1
    lines = [l for l in out.splitlines() if "E_SAME_FRAMES" in l]
    assert lines[0].startswith("FAIL slime.px:23: E_SAME_FRAMES: idle/0 and idle/3")  # idle/3's line (frame 0's run first)
    assert lines[1].startswith("FAIL slime.px:18: E_SAME_FRAMES: idle/1 and idle/2 are identical")  # idle/2's line
    assert "check --strict fails on it" not in out


def test_following_the_advice_clears_it(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "slime.px").write_text(SLIME)
    assert run("frames", "slime.px", "--rm", "idle/2") == 0
    assert run("anim-set", "slime.px:idle/1", "ms=300") == 0
    assert run("frames", "slime.px", "--rm", "idle/3") == 0
    assert run("anim-set", "slime.px:idle/0", "ms=300") == 0
    capsys.readouterr()
    code, out = check("slime.px", "--strict", capsys=capsys)
    assert code == 0 and "identical" not in out


def test_a_variant_that_tells_them_apart_is_no_repeat(tmp_path, capsys):
    # the same pixels in the base, but night lights one frame's eye: not a stutter at night
    p = sprite(tmp_path, [("walk/0", ["kgk"]), ("walk/1", ["kek"]), ("walk/2", ["kkk"])],
               head="g #43e1b3\ne #43e1b3\nk #1a3a2a\n@variant night\ne #ffee00")
    code, out = check(p, capsys=capsys)
    assert "identical" not in out
    # with no variant, two keys of one color draw alike: that is a repeat
    p = sprite(tmp_path, [("walk/0", ["kgk"]), ("walk/1", ["kek"]), ("walk/2", ["kkk"])],
               head="g #43e1b3\ne #43e1b3\nk #1a3a2a", name="t.px")
    code, out = check(p, capsys=capsys)
    assert "walk/0 and walk/1 are identical (0 px differ):" in out


def test_see_through_pixels_compare_as_see_through(tmp_path, capsys):
    p = sprite(tmp_path, [("walk/0", ["k.k"]), ("walk/1", ["kck"]), ("walk/2", ["kgk"])],
               head="g #43e1b3\nk #1a3a2a\nc #ff000000")
    _, out = check(p, capsys=capsys)
    assert "walk/0 and walk/1 are identical" in out


def test_still_groups_and_the_top_level_are_exempt(tmp_path, capsys):
    p = sprite(tmp_path, [("ui/0", UP), ("ui/1", UP)], anim="@still ui")
    _, out = check(p, capsys=capsys)
    assert "identical" not in out
    p = sprite(tmp_path, [("a", UP), ("b", UP)], anim="", name="top.px")
    _, out = check(p, capsys=capsys)
    assert "identical" not in out
    p = sprite(tmp_path, [("walk/0", UP), ("walk/1", UP)], anim="@still *", name="all.px")
    _, out = check(p, capsys=capsys)
    assert "identical" not in out


@pytest.mark.parametrize("anim, wraps", [
    ("@anim walk", True),
    ("@anim walk direction=reverse", True),
    ("@anim walk repeat=2", True),
    ("@anim walk repeat=1", False),
    ("@anim walk direction=pingpong", False),
    ("@anim walk direction=pingpong_reverse", False),
])
def test_the_wrap_only_where_the_loop_comes_back_round(tmp_path, capsys, anim, wraps):
    p = sprite(tmp_path, [("walk/0", UP), ("walk/1", DOWN), ("walk/2", SIDE), ("walk/3", UP)], anim=anim)
    _, out = check(p, capsys=capsys)
    assert ("walk/0 and walk/3 (where the loop comes back round) are identical" in out) == wraps
    assert out.count("are identical") == wraps


def test_two_frames_are_one_pair(tmp_path, capsys):
    p = sprite(tmp_path, [("walk/0", UP), ("walk/1", UP)])
    _, out = check(p, capsys=capsys)
    assert out.count("are identical") == 1 and "walk/0 and walk/1 are identical" in out


def test_a_selection_checks_only_its_groups(tmp_path, capsys):
    p = sprite(tmp_path, [("walk/0", UP), ("walk/1", UP), ("walk/2", DOWN), ("run/0", UP), ("run/1", DOWN)])
    _, out = check(f"{p}:run", capsys=capsys)
    assert "identical" not in out
    _, out = check(f"{p}:walk", capsys=capsys)
    assert "walk/0 and walk/1 are identical" in out


def test_groups_with_no_repeat_say_nothing(tmp_path, capsys):
    p = sprite(tmp_path, [("walk/0", UP), ("walk/1", DOWN), ("walk/2", SIDE)])
    code, out = check(p, "--strict", capsys=capsys)
    assert code == 0 and "identical" not in out


def test_every_example_passes(capsys):
    # the tutorials' animations have no repeated neighbours
    examples = pathlib.Path(__file__).resolve().parent.parent / "examples"
    run("check", examples)
    assert "E_SAME_FRAMES" not in capsys.readouterr().out
    for p in sorted(examples.rglob("*.px")):
        try:
            doc = pxart.parse(p)
        except pxart.PxError:
            continue
        assert pxart.repeated_frames(doc) == [], p


def test_help_says_it():
    doc = " ".join(pxart.__doc__.split())
    assert "E_SAME_FRAMES: neighbour frames of an animation that draw alike in every variant" in doc
    readme = (pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text()
    assert "E_SAME_FRAMES" in " ".join(readme.split())


def test_a_run_of_three_is_one_note_and_its_advice_works(tmp_path, monkeypatch, capsys):
    # three copies in a row: one note, both copies removed in one call, the hold all three's time
    monkeypatch.chdir(tmp_path)
    sprite(tmp_path, [("walk/0", UP), ("walk/1", DOWN), ("walk/2", DOWN), ("walk/3", DOWN), ("walk/4", SIDE)])
    _, out = check("s.px", capsys=capsys)
    assert out.count("are identical") == 1
    assert ("walk/1, walk/2 and walk/3 are identical (0 px differ): a repeated frame, a stutter in an engine that draws "
            "every frame; for a hold, remove walk/2 and walk/3 and give walk/1 ms=300 (pxart frames s.px --rm walk/2 "
            "walk/3; pxart anim-set s.px:walk/1 ms=300)") in out
    assert run("frames", "s.px", "--rm", "walk/2", "walk/3") == 0
    assert run("anim-set", "s.px:walk/1", "ms=300") == 0
    capsys.readouterr()
    code, out = check("s.px", "--strict", capsys=capsys)
    assert code == 0 and "identical" not in out


def test_a_run_round_the_loop_keeps_frame_0(tmp_path, capsys):
    # frames 3, 0 and 1 are alike: one run, kept at frame 0, the hold all three's time
    p = sprite(tmp_path, [("walk/0", UP), ("walk/1", UP), ("walk/2", DOWN), ("walk/3", UP)])
    _, out = check(p, capsys=capsys)
    assert out.count("are identical") == 1
    assert "walk/0, walk/1 and walk/3 (where the loop comes back round) are identical" in out
    assert "remove walk/1 and walk/3 and give walk/0 ms=300" in out


@pytest.mark.parametrize("frames, hold", [
    ([UP, DOWN, SIDE, SIDE], 300),   # 2 3 2 at the turn: 100 + 2 x 100
    ([UP, UP, DOWN, SIDE], 300),     # 1 0 1 at the other turn
    ([UP, DOWN, DOWN, SIDE], 200),   # mid-cycle, passed twice a cycle, each pass 200
])
def test_a_pingpong_hold_is_the_time_on_screen(tmp_path, capsys, frames, hold):
    p = sprite(tmp_path, [(f"walk/{i}", r) for i, r in enumerate(frames)], anim="@anim walk direction=pingpong ms=100")
    _, out = check(p, capsys=capsys)
    assert f"ms={hold} (" in out


def test_a_group_with_no_anim_line_may_be_icons(tmp_path, capsys):
    p = sprite(tmp_path, [("ui/heart", UP), ("ui/life", UP), ("ui/coin", DOWN)], anim="")
    _, out = check(p, capsys=capsys)
    assert f"; or, if ui is no animation (icons, parts), mark it still: pxart anim-set {p}:ui --still" in out
    p = sprite(tmp_path, [("walk/0", UP), ("walk/1", UP), ("walk/2", DOWN)], name="w.px")
    _, out = check(p, capsys=capsys)
    assert "mark it still" not in out
