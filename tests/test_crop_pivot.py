"""crop FILE:frame -o OTHER:frame keeps the frame's pivot, moved with the crop (PX-72): written on its @frame line when
OUT's @anim would give another, and a note when the source has none and OUT's @anim lends it one."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pxart  # noqa: E402


def walker():
    """A 16x24 frame, feet on row 23 at x 5 and 9, its pivot 7,23 on the @anim line."""
    rows = []
    for y in range(24):
        r = ["."] * 16
        if y >= 4:
            r[5:10] = "ggggg"
        if y == 23:
            r[5] = r[9] = "k"
        rows.append("".join(r))
    return "pxart 1\nk #222222\ng #44aa44\n@anim walk pivot=7,23\n@frame walk/0\n" + "\n".join(rows) + "\n"


def run(*argv):
    try:
        pxart.main([str(a) for a in argv])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    return 0


def frame_line(path, fid):
    return next(l for l in path.read_text().splitlines() if l.startswith(f"@frame {fid}"))


def test_a_cut_into_a_new_file_carries_the_pivot_moved(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    pathlib.Path("c.px").write_text(walker())
    assert run("crop", "c.px:walk/0", "0,-2,16,26", "-o", "other5.px:walk/0") == 0
    assert frame_line(pathlib.Path("other5.px"), "walk/0") == "@frame walk/0 pivot=7,25"
    doc = pxart.parse(pathlib.Path("other5.px"))
    f = doc.get("walk/0")
    assert f.size == (16, 26) and f.grid[25][5] == "k"  # the pivot's row is still the feet's
    assert run("export", "other5.px", "--frames", "fr") == 0
    assert json.loads(pathlib.Path("fr/pivots.json").read_text()) == {"walk/0": {"x": 7, "y": 25}}


def test_a_cut_into_a_file_whose_anim_has_another_pivot_writes_its_own(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    pathlib.Path("c.px").write_text(walker())
    pathlib.Path("other4.px").write_text(walker())
    assert run("crop", "c.px:walk/0", "0,-2,16,26", "-o", "other4.px:walk/1") == 0
    assert frame_line(pathlib.Path("other4.px"), "walk/1") == "@frame walk/1 pivot=7,25"
    assert frame_line(pathlib.Path("other4.px"), "walk/0") == "@frame walk/0"  # the rest as it was
    capsys.readouterr()
    assert run("anim", "other4.px:walk") == 0
    out = capsys.readouterr().out
    assert "shift +0,+0 then 0px" in out and "+2" not in out  # the feet never moved


def test_a_pivot_the_anim_already_gives_is_not_repeated(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    pathlib.Path("c.px").write_text(walker())
    assert run("crop", "c.px:walk/0", "0,0,16,24", "-o", "c.px:walk/1") == 0
    assert frame_line(pathlib.Path("c.px"), "walk/1") == "@frame walk/1"
    assert pxart.parse(pathlib.Path("c.px")).pivot(pxart.parse(pathlib.Path("c.px")).get("walk/1")) == (7, 23)


def test_a_frame_s_own_pivot_moves_too(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    pathlib.Path("c.px").write_text(walker().replace("@anim walk pivot=7,23\n", "").replace(
        "@frame walk/0", "@frame walk/0 pivot=7,23"))
    assert run("crop", "c.px:walk/0", "2,4,12,20", "-o", "c.px:walk/1") == 0
    assert frame_line(pathlib.Path("c.px"), "walk/1") == "@frame walk/1 pivot=5,19"


def test_no_pivot_but_the_anim_lends_one_says_so(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    pathlib.Path("bare.px").write_text(walker().replace("@anim walk pivot=7,23\n", ""))
    pathlib.Path("other4.px").write_text(walker())
    assert run("crop", "bare.px:walk/0", "0,-2,16,26", "-o", "other4.px:walk/1") == 0
    out = capsys.readouterr().out
    assert "bare.px:walk/0 has no pivot" in out and "@anim walk pivot 7,23" in out
    assert frame_line(pathlib.Path("other4.px"), "walk/1") == "@frame walk/1"


def test_no_pivot_drops_the_replaced_frame_s_own(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    pathlib.Path("bare.px").write_text(walker().replace("@anim walk pivot=7,23\n", ""))
    pathlib.Path("o.px").write_text(walker().replace("@anim walk pivot=7,23\n", "").replace(
        "@frame walk/0", "@frame walk/0 pivot=3,3"))
    assert run("crop", "bare.px:walk/0", "0,0,16,24", "-o", "o.px:walk/0") == 0
    assert "own, 3,3, goes" in capsys.readouterr().out
    assert frame_line(pathlib.Path("o.px"), "walk/0") == "@frame walk/0"


def test_an_unnamed_grid_out_says_the_pivot_is_not_kept(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    pathlib.Path("c.px").write_text(walker())
    assert run("crop", "c.px:walk/0", "0,-2,16,26", "-o", "plain.px") == 0
    out = capsys.readouterr().out
    assert "pivot 7,25" in out and "plain.px:plain as -o keeps it" in out
    assert run("crop", "c.px:walk/0", "0,-2,16,26", "-o", "plain.px:plain") == 0  # as the note says: one frame
    doc = pxart.parse(pathlib.Path("plain.px"))
    assert [f.id for f in doc.frames] == ["plain"] and doc.pivot(doc.frames[0]) == (7, 25)
    pathlib.Path("my art.px").write_text("pxart 1\no #2b1d32\n\n....\n.oo.\n")
    capsys.readouterr()
    assert run("crop", "c.px:walk/0", "0,-2,16,26", "-o", "my art.px") == 0
    out = capsys.readouterr().out
    assert "isn't kept" in out and "as -o" not in out  # no id to suggest
    pathlib.Path("p3.px").write_text("pxart 1\no #2b1d32\n\n....\n.oo.\n")
    assert run("crop", "c.px:walk/0", "0,-2,16,26", "-o", "p3.px") == 0
    assert "p3.px:p3 as -o keeps it" in capsys.readouterr().out
    capsys.readouterr()
    assert run("crop", "c.px:walk/0", "0,-2,16,26", "-o", "plain2.px:walk/0") == 0
    assert frame_line(pathlib.Path("plain2.px"), "walk/0") == "@frame walk/0 pivot=7,25"


def test_a_pivot_off_the_cut_canvas_is_said(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    pathlib.Path("c.px").write_text(walker())
    assert run("crop", "c.px:walk/0", "0,0,16,12", "-o", "top.px:top/0") == 0
    assert "top/0's pivot 7,23 lies outside its 16x12 canvas" in capsys.readouterr().out


def test_a_cut_into_a_new_file_keeps_the_timing(tmp_path, monkeypatch, capsys):
    """PX-75: the @anim's ms=140 comes along on the frame line, so the cut walk plays at 140 ms."""
    monkeypatch.chdir(tmp_path)
    pathlib.Path("c.px").write_text(walker().replace("@anim walk pivot=7,23", "@anim walk ms=140 pivot=7,23"))
    assert run("crop", "c.px:walk/0", "0,-2,16,26", "-o", "tall.px:walk/0") == 0
    assert run("crop", "c.px:walk/0", "0,-2,16,26", "-o", "tall.px:walk/1") == 0
    assert frame_line(pathlib.Path("tall.px"), "walk/0") == "@frame walk/0 ms=140 pivot=7,25"
    capsys.readouterr()
    assert run("anim", "tall.px:walk") == 0
    assert "140ms" in capsys.readouterr().out


def test_a_matching_anim_ms_writes_none_and_a_frame_s_own_wins(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    text = walker().replace("@anim walk pivot=7,23", "@anim walk ms=140 pivot=7,23")
    pathlib.Path("c.px").write_text(text)
    pathlib.Path("o.px").write_text(text)
    assert run("crop", "c.px:walk/0", "0,0,16,24", "-o", "o.px:walk/1") == 0
    assert frame_line(pathlib.Path("o.px"), "walk/1") == "@frame walk/1"
    pathlib.Path("d.px").write_text(text.replace("@frame walk/0", "@frame walk/0 ms=300"))
    assert run("crop", "d.px:walk/0", "0,0,16,24", "-o", "o.px:walk/2") == 0
    assert frame_line(pathlib.Path("o.px"), "walk/2") == "@frame walk/2 ms=300"


def test_the_default_ms_writes_none_and_a_still_gets_none(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    pathlib.Path("c.px").write_text(walker())  # no ms: the default
    assert run("crop", "c.px:walk/0", "0,0,16,24", "-o", "n.px:walk/0") == 0
    assert "ms=" not in frame_line(pathlib.Path("n.px"), "walk/0")
    pathlib.Path("e.px").write_text(walker().replace("@anim walk pivot=7,23", "@anim walk ms=140 pivot=7,23"))
    assert run("crop", "e.px:walk/0", "0,0,16,24", "-o", "n.px:head") == 0  # a top-level id is a still
    assert "ms=" not in frame_line(pathlib.Path("n.px"), "head")
