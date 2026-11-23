"""export writes nothing when one of its outputs fails its checks (PX-44): --indexed's palette merge and --tiled's one
size run before --frames and --aseprite write."""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pxart  # noqa: E402


def fails(*argv):
    with pytest.raises(SystemExit) as e:
        pxart.main([str(a) for a in argv])
    return str(e.value.code)


def test_a_key_conflict_for_indexed_writes_nothing(tmp_path, capsys):
    (tmp_path / "a.px").write_text("w #ffffff\nw\n")
    (tmp_path / "b.px").write_text("w #000000\nw\n")
    o = tmp_path / "o"
    err = fails("export", tmp_path / "a.px", tmp_path / "b.px", "--indexed", o / "k.json", "--frames", o / "f",
                "--aseprite", o / "s.json")
    assert "E_KEY_CONFLICT" in err
    assert not o.exists()
    assert "created" not in capsys.readouterr().out


def test_frames_of_two_sizes_for_tiled_write_nothing(tmp_path):
    (tmp_path / "a.px").write_text("k #000000\n@frame a\nk\n@frame b\nkk\n")
    o = tmp_path / "o"
    err = fails("export", tmp_path / "a.px", "--frames", o / "f", "--aseprite", o / "s.json", "--tiled", o / "t.tsj")
    assert "E_TILE_SIZE" in err and not o.exists()


def test_a_good_export_still_writes_all_four(tmp_path):
    (tmp_path / "a.px").write_text("k #000000\n@anim w ms=100\n@frame w/0\nk.\n@frame w/1\n.k\n")
    o = tmp_path / "o"
    pxart.main(["export", str(tmp_path / "a.px"), "--frames", str(o / "f"), "--aseprite", str(o / "s.json"),
                "--tiled", str(o / "t.tsj"), "--indexed", str(o / "k.json")])
    for f in ("f/w/0.png", "s.json", "s.png", "t.tsj", "t.png", "k.json"):
        assert (o / f).exists(), f


def test_an_output_path_under_a_file_fails_before_anything_is_written(tmp_path):
    (tmp_path / "a.px").write_text("k #000000\n@anim w ms=100\n@frame w/0\nk.\n@frame w/1\n.k\n")
    (tmp_path / "blocker").write_text("a file")
    o = tmp_path / "o"
    err = fails("export", tmp_path / "a.px", "--frames", o / "f", "--aseprite", o / "s.json",
                "--indexed", tmp_path / "blocker" / "k.json")
    assert "E_FILE" in err and "blocker is a file" in err and not o.exists()


def test_the_conflict_hint_pastes_into_a_shell(tmp_path):
    (tmp_path / "a.px").write_text("w #ffffff\nw\n")
    (tmp_path / "b.px").write_text("w #000000\nw\n")
    err = fails("export", tmp_path / "a.px", tmp_path / "b.px", "--indexed", tmp_path / "k.json")
    assert f": pxart recolor {tmp_path / 'b.px'} 'w>K'" in err and "('pxart" not in err


def test_a_variant_conflict_names_both_files(tmp_path):
    (tmp_path / "a.px").write_text("w #ffffff\n\n@variant night\nw #101010\n\nw\n")
    (tmp_path / "b.px").write_text("w #ffffff\n\n@variant night\nw #202020\n\nw\n")
    err = fails("export", tmp_path / "a.px", tmp_path / "b.px", "--indexed", tmp_path / "k.json")
    assert f"#101010 in {tmp_path / 'a.px'}, #202020 in {tmp_path / 'b.px'}" in err


KIT = "k #000000\n@anim w ms=100\n@frame w/0 pivot=0,0\nk.\n@frame w/1\n.k\n"


def kit(tmp_path):
    (tmp_path / "a.px").write_text(KIT)
    return tmp_path / "a.px"


@pytest.mark.parametrize("block", ["o/f/w", "o/f/w/1.png/", "o/f/pivots.json/", "o/x.png/"])
def test_any_path_export_writes_is_checked_first(tmp_path, block):
    a = kit(tmp_path)
    target = tmp_path / block.rstrip("/")
    target.parent.mkdir(parents=True, exist_ok=True)
    if block.endswith("/"):
        target.mkdir()
    else:
        target.write_text("a file")
    before = sorted(str(p) for p in tmp_path.rglob("*"))
    err = fails("export", a, "--frames", tmp_path / "o/f", "--aseprite", tmp_path / "o/x.png")
    assert "E_FILE" in err or "Is a directory" in err
    assert sorted(str(p) for p in tmp_path.rglob("*")) == before


def test_an_unwritten_png_beside_indexed_is_not_checked(tmp_path):
    a = kit(tmp_path)
    (tmp_path / "o").mkdir()
    (tmp_path / "o/k.png").mkdir()  # nothing writes k.png
    pxart.main(["export", str(a), "--aseprite", str(tmp_path / "o/s.json"), "--indexed", str(tmp_path / "o/k.json")])
    assert (tmp_path / "o/k.json").exists()


@pytest.mark.parametrize("argv", [["--aseprite", "s.png"], ["--aseprite", "s.json", "--indexed", "s.json"],
                                  ["--tiled", "s.json", "--aseprite", "s.json"]])  # one shared s.png stays allowed
def test_two_outputs_onto_one_file_are_refused(tmp_path, argv):
    a = kit(tmp_path)
    err = fails("export", a, *[str(tmp_path / x) if x.startswith("s.") else x for x in argv])
    assert "E_BAD_ARG" in err and "would both write" in err
    assert not list(tmp_path.glob("s.*"))
