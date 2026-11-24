"""bench/cast/pxc.py: a cast has one palette, and the encoder says which key and files break it (PX-46)."""
import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("pxc", ROOT / "bench" / "cast" / "pxc.py")
pxc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pxc)


def cast(tmp_path, files):
    for name, text in files.items():
        (tmp_path / name).write_text(text)
    return tmp_path


def test_a_key_the_first_file_lacks_encodes(tmp_path):
    # aardvark.px sorts first and doesn't have 'g': this was a raw KeyError
    c = cast(tmp_path, {"aardvark.px": "k #1b1420\n\nkk\n", "zebra.px": "k #1b1420\ng #43e1b3\n\nkg\n"})
    data, stats = pxc.encode(c, None)
    assert data.startswith(b"PXC1") and stats["keys"] == 2


def test_unused_keys_needn_t_be_listed_and_shared_palette_still_works(tmp_path):
    shared = {"palette.px": "k #1b1420\ng #43e1b3\ny #fee761\n",
              "fox.px": "@palette palette.px\n\nkg\n", "owl.px": "@palette palette.px\n\nky\n"}
    trimmed = {"palette.px": "k #1b1420\ng #43e1b3\ny #fee761\n",
               "fox.px": "k #1b1420\ng #43e1b3\n\nkg\n", "owl.px": "k #1b1420\ny #fee761\n\nky\n"}
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    a = pxc.encode(cast(tmp_path / "a", shared), None)[0]
    b = pxc.encode(cast(tmp_path / "b", trimmed), None)[0]
    assert a == b


def test_a_key_colored_two_ways_names_the_key_and_files(tmp_path):
    c = cast(tmp_path, {"fox.px": "k #1b1420\n\nkk\n", "owl.px": "k #2b1d32\n\nkk\n"})
    with pytest.raises(SystemExit) as e:
        pxc.encode(c, None)
    msg = str(e.value)
    assert "key 'k' in the base differs between files" in msg
    assert "fox.px #1b1420" in msg and "owl.px #2b1d32" in msg


def test_a_variant_colored_two_ways_names_the_variant(tmp_path):
    c = cast(tmp_path, {"fox.px": "k #1b1420\n@variant night\nk #000010\n\nkk\n",
                        "owl.px": "k #1b1420\n@variant night\nk #000020\n\nkk\n"})
    with pytest.raises(SystemExit) as e:
        pxc.encode(c, None)
    assert "key 'k' in @variant night differs" in str(e.value)


def test_a_file_without_a_variant_is_named(tmp_path):
    c = cast(tmp_path, {"fox.px": "k #1b1420\n@variant night\nk #000010\n\nkk\n", "owl.px": "k #1b1420\n\nkk\n"})
    with pytest.raises(SystemExit) as e:
        pxc.encode(c, None)
    assert "owl.px has no @variant night" in str(e.value)


def test_an_unnamed_grid_goes_by_the_file_name(tmp_path):
    data, _ = pxc.encode(cast(tmp_path, {"fox.px": "k #1b1420\n\nkk\n"}), None)
    assert data.count(b"fox") == 2  # the character and its one frame


def test_palette_only_files_and_subfolders_are_skipped(tmp_path):
    c = cast(tmp_path, {"palette.px": "k #1b1420\n", "fox.px": "@palette palette.px\n\nkk\n"})
    (c / "wip").mkdir()
    (c / "wip" / "owl.px").write_text("k #ffffff\n\nkk\n")
    data, _ = pxc.encode(c, None)
    assert b"fox" in data and b"owl" not in data and b"palette" not in data
