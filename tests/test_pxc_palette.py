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


def test_an_empty_missing_or_nested_cast_is_an_error(tmp_path):
    with pytest.raises(SystemExit, match="has no character .px files"):
        pxc.encode(tmp_path, None)
    with pytest.raises(SystemExit, match="isn't a folder"):
        pxc.encode(tmp_path / "nope", None)
    (tmp_path / "chars").mkdir()
    (tmp_path / "chars" / "fox.px").write_text("k #1b1420\n\nkk\n")
    with pytest.raises(SystemExit, match=r"subfolders aren't read, and hold chars/fox.px"):
        pxc.encode(tmp_path, None)


def test_two_files_lacking_a_variant_have(tmp_path):
    c = cast(tmp_path, {"fox.px": "k #1b1420\n@variant dusk\nk #000010\n\nkk\n", "owl.px": "k #1b1420\n\nkk\n",
                        "rat.px": "k #1b1420\n\nkk\n"})
    with pytest.raises(SystemExit, match="owl.px, rat.px have no @variant dusk"):
        pxc.encode(c, None)


def test_a_malformed_file_is_a_message_not_a_traceback(tmp_path):
    c = cast(tmp_path, {"fox.px": "k #1b1420\n\nkk\nk\n"})
    with pytest.raises(SystemExit, match="E_ROW_WIDTH"):
        pxc.encode(c, None)


GOLD = {"palette.px": "k #1b1420\ng #43e1b3\nf #e0ac69 | #f5cfa0\nh #ffffff80\n@variant night\nk #000010\ng #10304080\n",
        "fox.px": "@palette palette.px\n@anim idle ms=200\n@frame idle/0\n.kk.\nkgfk\nkhhk\n"
                  "@frame idle/1\n.kk.\nkfgk\nkhhk\n",
        "owl.px": "@palette palette.px\n@frame stand\nkgk\nfhf\n"}


@pytest.mark.parametrize("orient,coding,digest", [
    ("cols", "raw", "22eb630767279f0c5cb7f61aba2ded716d1d6c6d5aa6d2da3171d35ab487be4b"),
    ("rows", "raw", "3841ed068ef605caa4ad99148a37776e1f4510e07201fe3841eef234a413ae6e"),
    ("cols", "ops", "bdb52b4ae722f77b4b99b9d9a6b1bafcb1c5dc36af6bcbecb5fdc9f3e1b90ac8"),
    ("rows", "ops", "cc7f9ea149e1d963b474c049443e46a85b604d210bf1eb6a09170e2e89570c12")])
def test_a_cast_that_encoded_before_gives_the_same_bytes(tmp_path, orient, coding, digest):
    # digests from the encoder before PX-46 (main e892dbb), on a cast with a slot, alpha and a variant
    import hashlib
    data, _ = pxc.encode(cast(tmp_path, GOLD), None, cols=orient == "cols", coding=coding)
    assert hashlib.sha256(data).hexdigest() == digest


def test_slots_that_differ_in_their_alternatives_differ(tmp_path):
    c = cast(tmp_path, {"fox.px": "f #e0ac69 | #f5cfa0\n\nff\n", "owl.px": "f #e0ac69\n\nff\n"})
    with pytest.raises(SystemExit, match=r"key 'f' in the base differs between files \(fox.px #e0ac69 \| #f5cfa0, "
                                         r"owl.px #e0ac69\)"):
        pxc.encode(c, None)


def test_alpha_counts_and_an_imported_color_says_so(tmp_path):
    c = cast(tmp_path, {"pal.px": "h #ffffff80\n", "fox.px": "@palette pal.px\n\nhh\n", "owl.px": "h #ffffff\n\nhh\n"})
    with pytest.raises(SystemExit, match=r"fox.px \(from its @palette\) #ffffff80, owl.px #ffffff\)"):
        pxc.encode(c, None)


def test_a_directory_or_undecodable_file_is_a_message(tmp_path):
    (tmp_path / "old.px").mkdir()  # a folder named like a file is skipped
    cast(tmp_path, {"fox.px": "k #1b1420\n\nkk\n"})
    assert pxc.encode(tmp_path, None)[0].startswith(b"PXC1")
    (tmp_path / "bad.px").write_bytes(b"k #1b1420\n\n\xff\xfe\n")
    with pytest.raises(SystemExit, match="doesn't read"):
        pxc.encode(tmp_path, None)


def layers(chars):
    return {"axes": {"order": []}, "damage": ["ok"], "expression": ["calm"], "characters": chars}


ANCHOR = {"head": [0, 0], "body": [0, 1], "mirror": False}


def test_layered_cast_errors_name_what_is_missing(tmp_path):
    c = cast(tmp_path, {"fox.px": "k #1b1420\n@frame ok-calm/idle/0\nkk\n", "owl.px": "k #1b1420\n@frame ok-calm/a\nk\n"})
    fox = {"overlays": {}, "anchors": {"idle/0": ANCHOR}}
    with pytest.raises(SystemExit, match="owl.px has no entry under \"characters\""):
        pxc.encode(c, layers({"fox": fox}))
    with pytest.raises(SystemExit, match="owl's frames a have no anchors"):
        pxc.encode(c, layers({"fox": fox, "owl": {"overlays": {}, "anchors": {}}}))
    data, _ = pxc.encode(c, layers({"fox": fox, "owl": {"overlays": {}, "anchors": {"a": ANCHOR}}}))
    assert data.startswith(b"PXC1")
    (c / "rat.px").write_text("k #1b1420\n\nkk\n")  # an unnamed grid: no ok-calm/ frame
    with pytest.raises(SystemExit, match="rat.px has no frame under ok-calm/"):
        pxc.encode(c, layers({"fox": fox, "owl": {"overlays": {}, "anchors": {"a": ANCHOR}}}))


def test_an_overlay_only_key_missing_from_every_palette_points_at_layers(tmp_path):
    c = cast(tmp_path, {"fox.px": "k #1b1420\n@frame ok-calm/idle/0\nkk\n"})
    fox = {"overlays": {"scar": {"rows": ["z"], "at": "head", "dx": 0, "dy": 0}}, "anchors": {"idle/0": ANCHOR}}
    with pytest.raises(SystemExit, match=r"key 'z' is drawn \(by a frame, or by an overlay in layers.json\)"):
        pxc.encode(c, layers({"fox": fox}))
