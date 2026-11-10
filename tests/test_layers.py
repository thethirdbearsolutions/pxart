"""Layered passes (CZY-2556): put --at (a typed patch at x,y), put --rows (retype a range of rows), and an erase key
for put --at and compose (a layer that removes pixels)."""
import io
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pxart  # noqa: E402

PAL = "pxart 1\na #ff0000\nb #00ff00\nz #ff00ff\n"


ERR = []


def run(*argv):
    try:
        pxart.main([str(a) for a in argv])
    except SystemExit as e:
        if not isinstance(e.code, int):
            ERR.append(str(e.code))
        return e.code if isinstance(e.code, int) else 1
    return 0


def put(monkeypatch, stdin, *argv):
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    return run("put", *argv)


def grid(path):
    return pxart.parse(str(path)).frames[0].grid


@pytest.fixture
def layers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pal.px").write_text(PAL)
    (tmp_path / "base.px").write_text("pxart 1\n@palette pal.px\n\naaaa\naaaa\naaaa\n")
    return tmp_path


def test_put_at_patches_and_dot_keeps(layers, monkeypatch, capsys):
    assert put(monkeypatch, ".b\nbb\n", "base.px", "--at", "1,1") == 0
    assert grid(layers / "base.px") == ["aaaa", "aaba", "abba"]
    assert "changed 3 px at 1,1 (2x2)" in capsys.readouterr().out


def test_put_at_erase_clears_and_needs_no_palette_key(layers, monkeypatch):
    assert put(monkeypatch, "Xb\n", "base.px", "--at", "0,0", "--erase", "X") == 0
    assert grid(layers / "base.px") == [".baa", "aaaa", "aaaa"]


def test_put_at_without_erase_draws_the_key(layers, monkeypatch):
    assert put(monkeypatch, "zz\n", "base.px", "--at", "0,2") == 0
    assert grid(layers / "base.px")[2] == "zzaa"


def test_put_at_past_the_frame_fails_and_writes_nothing(layers, monkeypatch, capsys):
    before = (layers / "base.px").read_text()
    assert put(monkeypatch, "bb\n", "base.px", "--at", "3,0") != 0
    assert "past the 4x3 frame" in ERR[-1]
    assert (layers / "base.px").read_text() == before


def test_put_at_named_frame(layers, monkeypatch):
    (layers / "m.px").write_text("pxart 1\n@palette pal.px\n\n@frame idle\naaa\naaa\n\n@frame walk\nbbb\nbbb\n")
    assert put(monkeypatch, "z\n", "m.px:walk", "--at", "2,1", "--erase", "z") == 0
    doc = pxart.parse(str(layers / "m.px"))
    assert doc.get("walk").grid == ["bbb", "bb."]
    assert doc.get("idle").grid == ["aaa", "aaa"]


def test_put_rows_replaces_a_range(layers, monkeypatch, capsys):
    assert put(monkeypatch, "bbbb\n..ab\n", "base.px", "--rows", "1-2") == 0
    assert grid(layers / "base.px") == ["aaaa", "bbbb", "..ab"]
    assert "rows 1-2" in capsys.readouterr().out


def test_put_rows_needs_full_width_and_the_right_count(layers, monkeypatch, capsys):
    assert put(monkeypatch, "bbb\n", "base.px", "--rows", "1") != 0
    assert "takes 1 row(s) of 4" in ERR[-1]
    assert put(monkeypatch, "bbbb\n", "base.px", "--rows", "1-2") != 0
    assert put(monkeypatch, "bbbb\n", "base.px", "--rows", "3") != 0


def test_erase_needs_at(layers, monkeypatch):
    assert put(monkeypatch, "zz\n", "base.px", "--erase", "z") != 0


def test_compose_erase_removes_and_is_not_copied(layers, capsys):
    (layers / "fix.px").write_text("pxart 1\n@palette pal.px\n\n....\n.zb.\n....\n")
    assert run("compose", "-o", "out.px", "base.px@0,0", "fix.px@0,0", "--erase", "z", "--replace",
               "--used-keys-only") == 0
    out = pxart.parse(str(layers / "out.px"))
    assert out.frames[0].grid == ["aaaa", "a.ba", "aaaa"]
    assert "z" not in "".join(out.frames[0].grid)


def test_compose_erase_then_a_later_layer_draws_again(layers):
    (layers / "fix.px").write_text("pxart 1\n@palette pal.px\n\nzz..\n....\n....\n")
    (layers / "top.px").write_text("pxart 1\n@palette pal.px\n\n.b..\n....\n....\n")
    assert run("compose", "-o", "out.px", "base.px@0,0", "fix.px@0,0", "top.px@0,0", "--erase", "z",
               "--replace") == 0
    assert grid(layers / "out.px")[0] == ".baa"


def test_compose_without_erase_draws_the_key(layers):
    (layers / "fix.px").write_text("pxart 1\n@palette pal.px\n\nz...\n....\n....\n")
    assert run("compose", "-o", "out.px", "base.px@0,0", "fix.px@0,0", "--replace") == 0
    assert grid(layers / "out.px")[0] == "zaaa"


def test_compose_erase_must_be_one_key(layers):
    assert run("compose", "-o", "out.px", "base.px@0,0", "--erase", "zz") != 0
    assert run("compose", "-o", "out.px", "base.px@0,0", "--erase", ".") != 0


def test_compose_erase_key_defined_in_a_layer_stays_out_of_a_new_out(layers):
    # the erase key's own palette line in a cleanup layer isn't seeded into a new OUT (it was, as an unused key)
    (layers / "fix.px").write_text("pxart 1\n@palette pal.px\nX #ff00ff\n\nX...\n....\n....\n")
    assert run("compose", "-o", "out.px", "base.px@0,0", "fix.px@0,0", "--erase", "X", "--replace") == 0
    out = pxart.parse(str(layers / "out.px"))
    assert "X" not in out.palette and out.frames[0].grid[0] == ".aaa"
