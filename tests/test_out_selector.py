"""-o FILE.px:FRAME no longer makes a file or folder named 'FILE.px:FRAME' (PX-23): an edit that writes a whole file
says to give the file (or dup first), and from-png adds the frame to FILE under that id."""
import pathlib
import sys

import pytest
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import pxart  # noqa: E402
from test_pxart import run, run_err, write  # noqa: E402

W = "k #000000\ng #43e1b3\n@frame walk/0\n....\n.gg.\n.gg.\n....\n"


def nothing_named_with_a_colon(tmp_path):
    return not [p for p in tmp_path.rglob("*") if ":" in p.name]


@pytest.mark.parametrize("argv", [["outline", "{f}", "--key", "k", "-o", "{f}:walk/9"],
                                  ["outline", "{f}:walk/0", "--key", "k", "-o", "{f}:walk/9"],
                                  ["fill", "{f}:walk/0", "g", "-o", "{f}:walk/9"],
                                  ["shade", "{f}:walk/0", "--ramp", "kg", "--keys", "g", "-o", "{f}:x"],
                                  ["fill", "{f}:walk/0", "g", "-o", "{o}:x"]])
def test_an_edit_into_a_frame_says_to_give_the_file(tmp_path, argv):
    f = write(tmp_path, "w.px", W)
    err = run_err(*[x.format(f=f, o=tmp_path / "other.px") for x in argv])
    assert "but this edit writes a whole file, so -o takes a file" in err
    assert f.read_text() == W and nothing_named_with_a_colon(tmp_path)


def test_the_dup_route_it_prints_works(tmp_path):
    f = write(tmp_path, "w.px", W)
    err = run_err("outline", f"{f}:walk/0", "--key", "k", "-o", f"{f}:walk/9")
    assert f"copy it first: pxart dup {f}:walk/0 walk/9, then edit {f}:walk/9" in err
    assert run("dup", f"{f}:walk/0", "walk/9") == 0
    assert run("outline", f"{f}:walk/9", "--key", "k") == 0
    doc = pxart.parse(f)
    assert doc.get("walk/0").grid != doc.get("walk/9").grid  # walk/9 outlined, walk/0 as it was


def png(tmp_path, name="p.png", color=(255, 0, 0, 255)):
    p = tmp_path / name
    Image.new("RGBA", (2, 2), color).save(p)
    return p


def test_from_png_into_a_frame_adds_it_under_that_id(tmp_path):
    f = write(tmp_path, "into.px", W)
    assert run("from-png", png(tmp_path), "-o", f"{f}:walk/9") == 0
    assert [fr.id for fr in pxart.parse(f).frames] == ["walk/0", "walk/9"]
    assert nothing_named_with_a_colon(tmp_path)


def test_from_png_several_into_a_frame_is_a_prefix(tmp_path):
    f = write(tmp_path, "into.px", W)
    assert run("from-png", png(tmp_path), png(tmp_path, "q.png", (0, 0, 255, 255)), "-o", f"{f}:extra") == 0
    assert [fr.id for fr in pxart.parse(f).frames] == ["walk/0", "extra/p", "extra/q"]


def test_from_png_a_frame_and_id_both_is_an_error(tmp_path):
    f = write(tmp_path, "into.px", W)
    assert "both name the frames; give one" in run_err("from-png", png(tmp_path), "-o", f"{f}:a", "--id", "b")


def test_write_doc_never_makes_a_file_named_with_a_selector(tmp_path):
    doc = pxart.parse(write(tmp_path, "w.px", W))
    with pytest.raises(pxart.PxError) as e:
        pxart.write_doc(doc, tmp_path / "w.px:walk/9")
    assert e.value.issues[0].code == "E_BAD_ARG" and "-o takes a file" in str(e.value)
    assert nothing_named_with_a_colon(tmp_path)


# ---------------------------------------------------------------- the private loop's cases


ANIM = ("k #000000\ng #43e1b3\n@anim walk ms=100\n@frame walk/0\n....\n.gg.\n.gg.\n....\n"
        "@frame walk/1\n....\n.gg.\n.g..\n....\n")


def test_a_new_frame_in_an_animation_says_it_joins_it(tmp_path):
    f = write(tmp_path, "w.px", ANIM)
    err = run_err("outline", f"{f}:walk/0", "--key", "k", "-o", f"{f}:walk/9")
    assert "(walk/9 joins the walk animation; another group or a top-level id keeps it out)" in err


def test_an_existing_frame_gets_replace(tmp_path):
    f = write(tmp_path, "w.px", ANIM)
    err = run_err("outline", f"{f}:walk/0", "--key", "k", "-o", f"{f}:walk/1")
    assert f"pxart dup {f}:walk/0 walk/1 --replace, then edit {f}:walk/1" in err and "joins" not in err
    assert run("dup", f"{f}:walk/0", "walk/1", "--replace") == 0


def test_a_group_gets_the_group_dup(tmp_path):
    f = write(tmp_path, "w.px", ANIM)
    err = run_err("shift", f"{f}:walk", "0", "-1", "-o", f"{f}:up")
    assert f"copy it first: pxart dup {f}:walk up, then edit {f}:up" in err
    assert run("dup", f"{f}:walk", "up") == 0 and run("shift", f"{f}:up", "0", "-1") == 0


# ---------------------------------------------------------------- the PR #33 review's findings

R = ANIM + "@frame idle\n....\n.gg.\n.gg.\n....\n"


@pytest.mark.parametrize("argv,want", [
    (["outline", "{f}:walk/0", "--key", "k", "-o", "{f}:walk"], "walk is a group of"),  # 1
    (["shift", "{f}:walk", "0", "-1", "-o", "{f}:idle"], "idle is a frame of"),  # 1
    (["outline", "{f}:walk/0", "--key", "k", "-o", "{f}:walk/0"], "is what is being edited: leave -o off"),  # 2
    (["shift", "{f}:walk", "0", "-1", "-o", "{f}:walk"], "is what is being edited: leave -o off"),  # 2
    (["outline", "{f}:*", "--key", "k", "-o", "{f}:x"], "so -o takes a file (or leave it off"),  # 3
    (["outline", "{f}:walk/0", "--key", "k", "-o", "{f}:x%night"], "an output is a file, not a variant")])  # 6
def test_review_routes_never_suggest_a_dup_that_fails(tmp_path, argv, want):
    f = write(tmp_path, "r.px", R)
    err = run_err(*[x.format(f=f) for x in argv])
    assert want in err and "pxart dup" not in err


def test_review_the_printed_dup_route_runs(tmp_path):
    import shlex
    f = write(tmp_path, "r.px", R)
    err = run_err("outline", f"{f}:walk/0", "--key", "k", "-o", f"{f}:walk/1")
    dup = shlex.split(err.split("copy it first: ")[1].split(", then edit")[0])
    assert dup[-1] == "--replace" and run(*dup[1:]) == 0


@pytest.mark.parametrize("extra,want", [(["--prefix-dir"], "and --prefix-dir both name the frames"),
                                        (["--labels", "l.csv"], "and --labels both name the frames")])
def test_review_from_png_frame_with_another_namer_is_an_error(tmp_path, extra, want):
    f = write(tmp_path, "g.px", W)
    assert want in run_err("from-png", png(tmp_path), *extra, "-o", f"{f}:x")


@pytest.mark.parametrize("bad,want", [("a,b", "E_BAD_ID"), ("x%night", "a variant")])
def test_review_from_png_bad_ids(tmp_path, bad, want):
    f = write(tmp_path, "g.px", W)
    assert want in run_err("from-png", png(tmp_path), "-o", f"{f}:{bad}")


def test_review_from_png_grid_into_a_frame_is_a_prefix(tmp_path):
    f = write(tmp_path, "g.px", W)
    p = tmp_path / "s.png"
    Image.new("RGBA", (4, 2), (255, 0, 0, 255)).save(p)
    assert run("from-png", p, "--grid", "2x2", "-o", f"{f}:cell") == 0
    assert [fr.id for fr in pxart.parse(f).frames][1].startswith("cell/")


def test_review_a_folder_with_a_colon_is_a_folder(tmp_path):
    f = write(tmp_path, "w.px", W)
    (tmp_path / "v.px:2").mkdir()
    assert run("outline", f, "--key", "k", "-o", tmp_path / "v.px:2" / "out.px") == 0
    assert (tmp_path / "v.px:2" / "out.px").exists()


def test_review_an_existing_file_with_a_colon_edits_in_place(tmp_path):
    f = tmp_path / "c.px:walk"
    f.write_text(W)
    assert run("outline", f, "--key", "k") == 0 and "k" in "".join(pxart.parse(f).frames[0].grid)
