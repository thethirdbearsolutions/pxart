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
    with pytest.raises(pxart.PxError):
        pxart.write_doc(doc, tmp_path / "w.px:walk/9")
    assert nothing_named_with_a_colon(tmp_path)
