"""render --png DIR: when several skipped .px files would export into one folder, each file's routes name a
subfolder of its own, so running every route as printed overwrites nothing (no PNG, no pivots.json), and a
FILE%variant keeps its colors on both routes (PX-67)."""
import json
import pathlib
import shlex
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from test_pxart import run  # noqa: E402

TWO = "k #000000\ng #00ff00\n@anim a pivot=0,0\n@frame a/0\nk\n@frame a/1\ng\n"


def routes(out):
    """Each note's (export argv, render argv), as printed."""
    got = []
    for line in out.splitlines():
        if line.startswith("note: --png skips"):
            inner = line.split("('", 1)[1].rsplit(" one)", 1)[0].rsplit(" that frame)", 1)[0]
            export, render = inner.split("' writes ", 1)[0], inner.rsplit(", '", 1)[1].rstrip("'")
            got.append((shlex.split(export)[1:], shlex.split(render)[1:]))
    return got


def run_all(got):
    for export, render in got:
        assert run(*export) == 0
        assert run(*render) == 0


def test_files_sharing_a_folder_get_a_subfolder_each(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "x.px").write_text(TWO)
    (tmp_path / "y.px").write_text(TWO.replace("#00ff00", "#ff0000"))
    (tmp_path / "bat.px").write_text(TWO.replace("a/", "fly/").replace("@anim a", "@anim fly"))
    assert run("render", "x.px", "y.px", "bat.px", "--png", "o", "-o", "p.png") == 0
    got = routes(capsys.readouterr().out)
    assert [e for e, _ in got] == [["export", n, "--frames", f"o/{n[:-3]}"] for n in ("x.px", "y.px", "bat.px")]
    assert got[0][1] == ["render", "x.px:a/0", "--plain", "-o", "o/x/a/0.png"]
    run_all(got)
    files = sorted(p.relative_to(tmp_path / "o").as_posix() for p in (tmp_path / "o").rglob("*") if p.is_file())
    assert files == ["bat/fly/0.png", "bat/fly/1.png", "bat/pivots.json", "x/a/0.png", "x/a/1.png", "x/pivots.json",
                     "y/a/0.png", "y/a/1.png", "y/pivots.json"]
    assert set(json.loads((tmp_path / "o" / "x" / "pivots.json").read_text())) == {"a/0", "a/1"}


def test_one_skipped_file_keeps_the_folder(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "x.px").write_text(TWO)
    assert run("render", "x.px", "--png", "o", "-o", "p.png") == 0
    assert routes(capsys.readouterr().out)[0][0] == ["export", "x.px", "--frames", "o"]


def test_a_skipped_file_beside_pngs_png_writes_gets_a_subfolder(tmp_path, monkeypatch, capsys):
    # review finding 6: export x.px --frames o would overwrite o/a.png, which --png writes for a.px
    monkeypatch.chdir(tmp_path)
    (tmp_path / "x.px").write_text(TWO)
    (tmp_path / "a.px").write_text("k #000000\nk\n")
    assert run("render", "x.px", "a.px", "--png", "o", "-o", "p.png") == 0
    got = routes(capsys.readouterr().out)
    assert got[0][0] == ["export", "x.px", "--frames", "o/x"]
    before = (tmp_path / "o" / "a.png").read_bytes()
    run_all(got)
    assert (tmp_path / "o" / "a.png").read_bytes() == before


def test_a_variant_file_keeps_its_colors_on_both_routes(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "x.px").write_text(TWO)
    (tmp_path / "s.px").write_text(TWO + "@variant night\ng #003300\n")
    assert run("render", "x.px", "s.px%night", "--png", "o", "-o", "p.png") == 0
    got = routes(capsys.readouterr().out)
    assert got[1] == (["export", "s.px%night", "--frames", "o/s"],
                      ["render", "s.px:a/0%night", "--plain", "-o", "o/s/a/0.png"])
    run_all(got)


def test_two_files_of_one_name_get_numbered_folders(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    for d in ("a", "b"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "knight.px").write_text(TWO)
    assert run("render", "a/knight.px", "b/knight.px", "--png", "o", "-o", "p.png") == 0
    got = routes(capsys.readouterr().out)
    assert [e[-1] for e, _ in got] == ["o/knight", "o/knight-2"]
    run_all(got)


def test_review_cases_never_share_a_folder(tmp_path, monkeypatch, capsys):
    # review findings 1-5, 7-8: '..', './', a suffix equal to another stem, nesting, an existing file, case, absolute
    (tmp_path / "sub").mkdir()
    monkeypatch.chdir(tmp_path / "sub")
    (tmp_path / "knight.px").write_text(TWO)
    (tmp_path / "sub" / "knight.px").write_text(TWO)
    (tmp_path / "sub" / "s.px").write_text(TWO + "@variant night\ng #003300\n")
    (tmp_path / "sub" / "s-night.px").write_text(TWO)
    (tmp_path / "sub" / "X.px").write_text(TWO)
    (tmp_path / "sub" / "x.px").write_text(TWO)
    (tmp_path / "sub" / "o").mkdir()
    (tmp_path / "sub" / "o" / "p").write_text("a file")
    (tmp_path / "sub" / "p.px").write_text(TWO)
    args = ["../knight.px", "knight.px", "s.px", "./s.px%night", "s-night.px", "X.px", "x.px", "p.px",
            str(tmp_path / "sub" / "knight.px")]
    assert run("render", *args, "--png", "o", "-o", "q.png") == 0
    got = routes(capsys.readouterr().out)
    folders = [e[-1] for e, _ in got]
    assert len({f.casefold() for f in folders}) == len(folders) and "o/p" not in folders
    assert all(f.count("/") == 1 for f in folders)  # flat names: none inside another, no absolute path copied
    run_all(got)


def test_one_file_named_twice_gets_two_folders(tmp_path, monkeypatch, capsys):
    # second private loop: slime.px and slime.px%night, or two selections of one file, wrote into one folder
    monkeypatch.chdir(tmp_path)
    (tmp_path / "s.px").write_text(TWO + "@variant night\ng #003300\n")
    assert run("render", "s.px", "s.px%night", "s.px:a/0", "--png", "o", "-o", "p.png") == 0
    got = routes(capsys.readouterr().out)
    assert [e[-1] for e, _ in got] == ["o/s", "o/s-night", "o/s-a-0"]
    run_all(got)
