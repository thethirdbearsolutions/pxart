"""FILE:GROUP/ is the group alone, beside a top-level frame whose id is GROUP (PX-73): check notes the clash and the
rename that ends it, frames --rename GROUP/ NEW/ renames only the group, and check --headroom prints commands that
run."""
import pathlib
import shlex
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pxart  # noqa: E402

TOP = """pxart 1
k #000000
@anim a ms=120
@frame a/0
kkk
kkk
kkk
kkk
@frame a/1
kkk
k.k
kkk
kkk
@frame a
kkk
kkk
kkk
kkk
"""


def run(*argv):
    try:
        pxart.main([str(a) for a in argv])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    return 0


def ids(p):
    return [f.id for f in pxart.parse(pathlib.Path(p)).frames]


def test_the_slash_picks_the_group_alone(tmp_path):
    p = tmp_path / "top.px"
    p.write_text(TOP)
    doc = pxart.parse(p)
    assert [f.id for f in doc.select("a")] == ["a/0", "a/1", "a"]
    assert [f.id for f in doc.select("a/")] == ["a/0", "a/1"]


def test_a_slash_naming_no_group_is_an_error(tmp_path, capsys):
    p = tmp_path / "top.px"
    p.write_text(TOP)
    try:
        pxart.main(["render", f"{p}:b/", "-o", str(tmp_path / "x.png")])
    except SystemExit as e:
        assert "no group 'b'" in str(e.code)
    else:
        raise AssertionError("render of a group that isn't there ran")


def test_rename_with_the_slash_leaves_the_frame(tmp_path, capsys):
    p = tmp_path / "top.px"
    p.write_text(TOP)
    assert run("frames", p, "--rename", "a/", "walk/") == 0
    assert ids(p) == ["walk/0", "walk/1", "a"]
    assert "@anim walk ms=120" in p.read_text()


def test_check_notes_the_clash_and_its_rename_runs(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    pathlib.Path("top.px").write_text(TOP)
    assert run("check", "top.px") == 0
    line = next(l for l in capsys.readouterr().out.splitlines() if "shares its id" in l)
    assert "frame a shares its id with the group a/ (a/0, a/1)" in line
    cmd = shlex.split(line[line.index("pxart frames"):])
    assert run(*cmd[1:]) == 0
    assert ids("top.px") == ["a-anim/0", "a-anim/1", "a"]
    capsys.readouterr()
    assert run("check", "top.px") == 0
    assert "shares its id" not in capsys.readouterr().out


def test_headroom_prints_commands_that_run(tmp_path, monkeypatch, capsys):
    """The ticket's test: the group's crop names a/, and the frame's crop follows the rename, which then runs."""
    monkeypatch.chdir(tmp_path)
    pathlib.Path("top.px").write_text(TOP)
    assert run("check", "top.px", "--headroom", "2") == 0
    out = capsys.readouterr().out
    group = next(l for l in out.splitlines() if "in a/0, a/1" in l)
    gcmd = shlex.split(group[group.index("pxart crop"):group.index(" (every frame)")])
    frame = next(l for l in out.splitlines() if "then pxart crop" in l)
    rename = shlex.split(frame[frame.index("pxart frames"):frame.index(" (the group")])
    crop = shlex.split(frame[frame.index("then pxart crop") + 5:])
    assert run(*gcmd[1:]) == 0
    assert [f.size for f in pxart.parse(pathlib.Path("top.px")).frames] == [(3, 6), (3, 6), (3, 4)]
    assert run(*rename[1:]) == 0 and run(*crop[1:]) == 0
    assert [f.size for f in pxart.parse(pathlib.Path("top.px")).frames] == [(3, 6), (3, 6), (3, 6)]
    capsys.readouterr()
    assert run("check", "top.px", "--headroom", "2") == 0
    assert "headroom" not in capsys.readouterr().out


def test_no_clash_no_note(tmp_path, capsys):
    p = tmp_path / "w.px"
    p.write_text(TOP.replace("@frame a\n", "@frame b\n"))
    assert run("check", p) == 0
    assert "shares its id" not in capsys.readouterr().out


def test_anim_set_dup_and_flip_take_the_slash(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    pathlib.Path("top.px").write_text(TOP)
    assert run("anim-set", "top.px:a/", "ms=150") == 0
    assert "@anim a ms=150" in pathlib.Path("top.px").read_text()
    assert run("dup", "top.px:a/", "cast") == 0
    assert run("flip", "top.px:a/", "-o", "top.px:left/") == 0
    got = ids("top.px")
    assert {"cast/0", "cast/1", "left/0", "left/1", "a"} <= set(got) and "cast" not in got


def test_dup_of_the_clashing_id_says_it_copied_the_frame(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    pathlib.Path("top.px").write_text(TOP)
    assert run("dup", "top.px:a", "b") == 0
    assert "top.px:a/ is the group" in capsys.readouterr().out


def test_copy_to_with_the_slash_carries_the_anim_line(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    pathlib.Path("top.px").write_text(TOP)
    pathlib.Path("d.px").write_text("pxart 1\nk #000000\n@frame x\nk\n")
    assert run("frames", "top.px:a/", "--copy-to", "d.px", "--rename", "a/", "cast/") == 0
    assert "@anim cast ms=120" in pathlib.Path("d.px").read_text()


def test_a_selector_of_several_frames_names_the_clash(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    pathlib.Path("top.px").write_text(TOP)
    try:
        pxart.main(["crop", "top.px:a", "0,0,3,2", "-o", "parts.px:face"])
    except SystemExit as e:
        assert "pxart frames top.px --rename a/ a-anim/" in str(e.code)
    else:
        raise AssertionError("crop of 3 frames ran")


def test_a_plain_rename_of_both_says_so(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    pathlib.Path("top.px").write_text(TOP)
    assert run("frames", "top.px", "--rename", "a", "b") == 0
    assert "--rename a/ b/ renames the group alone" in capsys.readouterr().out


def test_headroom_says_the_group_first(tmp_path, monkeypatch, capsys):
    """Run in the order printed: the group's crop names a/ before the frame's fix renames the group."""
    monkeypatch.chdir(tmp_path)
    pathlib.Path("top.px").write_text(TOP)
    assert run("check", "top.px", "--headroom", "2") == 0
    lines = [l for l in capsys.readouterr().out.splitlines() if "headroom" in l]
    assert "in a/0, a/1" in lines[0] and "then pxart crop" in lines[1]
