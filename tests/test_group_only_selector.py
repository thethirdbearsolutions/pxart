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
